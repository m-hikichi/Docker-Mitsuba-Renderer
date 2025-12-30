"""
Mitsuba scene から「可視 bbox（ray-hit）」アノテーションJSONを生成する。

方式（visible bbox / ray-hit）:
- 画像の各ピクセル中心から primary ray を1本飛ばす
- 最前面でヒットした shape_index を取得
- shape ごとに (xmin, ymin, xmax, ymax) を集計して 2D bbox を作る

出力:
- bbox（xyxy, xywh）
- hits: その shape が最前面として見えたピクセル数（可視ピクセル数）
- depth_min / depth_mean: ヒットしたレイ距離 t の統計（小さいほど手前）
  ※ 深度統計は「描画順（手前ほど上）」など後処理に使用できる。

座標系:
- bbox 座標は film.crop_size() の画像座標（0..W-1, 0..H-1）で出力
- ray 生成は full film 座標へ変換して sample_ray に渡す（crop_offset 対応）

拡張ポイント:
- 追加統計（depth percentile 等）
- サブサンプリング（stride）
- マスク出力（将来）
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import mitsuba as mi


@dataclass
class FilmGeometry:
    """
    Film の幾何情報をまとめた構造体。

    Attributes:
        crop_size: 出力画像の解像度 (W, H)。bbox 座標系はこれに基づく。
        crop_offset: full film に対する crop の左上オフセット (offX, offY)。
        full_size: film.size() のフル解像度 (fullW, fullH)。
    """
    crop_size: Tuple[int, int]
    crop_offset: Tuple[int, int]
    full_size: Tuple[int, int]


@dataclass
class ShapeStats:
    """
    1つの shape に対する bbox/深度統計の累積器。

    bbox は「この shape が最前面として見えたピクセル」の集合の外接矩形。
    depth はそのピクセルでのレイ距離 t 統計（小さいほど手前）。

    Attributes:
        shape_index: Mitsuba の shape_index。
        shape_id: scene.xml の id（無ければ連番）。
        xmin,ymin,xmax,ymax: crop 画像座標系の bbox（未観測時は xmin/ymin が INF、xmax/ymax が負）。
        hits: 可視（最前面ヒット）ピクセル数。
        depth_min: t の最小値。
        depth_sum: t の合計（平均算出用）。
    """
    shape_index: int
    shape_id: str

    xmin: int
    ymin: int
    xmax: int
    ymax: int

    hits: int
    depth_min: float
    depth_sum: float

    @staticmethod
    def new(shape_index: int, shape_id: str) -> "ShapeStats":
        """
        ShapeStats を初期状態で生成する。

        bbox は未観測状態（xmin/ymin が巨大、xmax/ymax が負）で開始し、
        update() が呼ばれると観測済みへ遷移する。
        """
        INF_I = 10**9
        return ShapeStats(
            shape_index=shape_index,
            shape_id=shape_id,
            xmin=INF_I, ymin=INF_I, xmax=-INF_I, ymax=-INF_I,
            hits=0,
            depth_min=float("inf"),
            depth_sum=0.0,
        )

    def update(self, x: int, y: int, t: float) -> None:
        """
        1ピクセル分の観測結果で bbox と深度統計を更新する。

        Args:
            x, y: crop 画像座標系のピクセル位置（整数）。
            t: そのピクセル主光線の最前面ヒット距離（レイパラメータ）。
        """
        if x < self.xmin: self.xmin = x
        if y < self.ymin: self.ymin = y
        if x > self.xmax: self.xmax = x
        if y > self.ymax: self.ymax = y

        self.hits += 1
        if t < self.depth_min:
            self.depth_min = t
        self.depth_sum += t

    def has_bbox(self) -> bool:
        """
        bbox が1度でも観測されたかを返す。

        Returns:
            True: この shape が最前面として見えたピクセルが1つ以上ある
            False: 全く見えていない（最前面としてヒットしていない）
        """
        return self.xmax >= 0

    def depth_mean(self) -> Optional[float]:
        """
        深度の平均（t の平均）を返す。未観測なら None。

        Returns:
            平均 t（小さいほど手前）、または None。
        """
        if self.hits <= 0:
            return None
        return self.depth_sum / float(self.hits)

    def to_annotation(self) -> Dict[str, Any]:
        """
        JSON の annotations 要素（1物体分）へ変換する。

        Returns:
            annotation dict（bbox_xyxy/bbox_xywh/area/hits/depth_* を含む）

        Raises:
            ValueError: bbox が未観測（has_bbox() == False）の場合
        """
        if not self.has_bbox():
            raise ValueError("No bbox to serialize")

        w = (self.xmax - self.xmin + 1)
        h = (self.ymax - self.ymin + 1)
        area = int(w * h)

        dmin = None if self.depth_min == float("inf") else float(self.depth_min)
        dmean = self.depth_mean()

        return {
            "shape_index": int(self.shape_index),
            "shape_id": str(self.shape_id),
            "bbox_xyxy": [int(self.xmin), int(self.ymin), int(self.xmax), int(self.ymax)],
            "bbox_xywh": [int(self.xmin), int(self.ymin), int(w), int(h)],
            "area": area,
            "hits": int(self.hits),
            "depth_min": dmin,
            "depth_mean": float(dmean) if dmean is not None else None,
        }


def parse_args() -> argparse.Namespace:
    """
    CLI 引数を定義して parse する。

    Returns:
        argparse.Namespace: scene/out/variant/sensor-index 等を含む
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="scene.xml", help="Input scene xml")
    ap.add_argument("--out", default="bboxes.json", help="Output json path")
    ap.add_argument("--variant", default="scalar_rgb", help="Mitsuba variant (e.g., scalar_rgb)")
    ap.add_argument("--sensor-index", type=int, default=0, help="Sensor index in scene.sensors()")

    ap.add_argument("--time", type=float, default=0.0)
    ap.add_argument("--sample1", type=float, default=0.5, help="Wavelength/sample1 param for sample_ray")
    ap.add_argument("--aperture-u", type=float, default=0.5)
    ap.add_argument("--aperture-v", type=float, default=0.5)

    ap.add_argument("--stride", type=int, default=1,
                    help="Pixel stride for faster export (1 = full resolution).")
    return ap.parse_args()


def get_film_geometry(film: mi.Film) -> FilmGeometry:
    """
    Film から crop/full のジオメトリ情報を抽出する。

    Args:
        film: sensor.film()

    Returns:
        FilmGeometry: crop_size, crop_offset, full_size を格納
    """
    W, H = film.crop_size()
    offX, offY = film.crop_offset()
    fullW, fullH = film.size()
    return FilmGeometry(
        crop_size=(int(W), int(H)),
        crop_offset=(int(offX), int(offY)),
        full_size=(int(fullW), int(fullH)),
    )


def list_shape_ids(scene: mi.Scene) -> List[str]:
    """
    scene.shapes() から shape ごとの識別子（id）リストを作る。

    id が未設定の場合は "shape_{i}" のように連番で補完する。

    Args:
        scene: mi.Scene

    Returns:
        List[str]: shape_index と同じ順序の識別子リスト
    """
    ids: List[str] = []
    for i, s in enumerate(scene.shapes()):
        sid = s.id()
        ids.append(sid if sid else "shape_%d" % i)
    return ids


def crop_pixel_to_film_uv(x: int, y: int, geom: FilmGeometry) -> Tuple[float, float]:
    """
    crop 画像座標系のピクセル (x,y) を sample_ray 用の正規化 film 座標 (u,v) へ変換する。

    - ピクセル中心 (x+0.5, y+0.5) を使用
    - crop_offset で full film の座標へ戻す
    - full film size で割って 0..1 の正規化座標へ

    Args:
        x, y: crop 画像座標系
        geom: FilmGeometry（crop_offset/full_size を使用）

    Returns:
        (u, v): 正規化 film 座標
    """
    offX, offY = geom.crop_offset
    fullW, fullH = geom.full_size

    px = (x + 0.5) + offX
    py = (y + 0.5) + offY
    u = px / float(fullW)
    v = py / float(fullH)
    return u, v


def export_visible_bboxes(scene: mi.Scene,
                         sensor: mi.Sensor,
                         geom: FilmGeometry,
                         shape_ids: List[str],
                         time: float,
                         sample1: float,
                         aperture_sample: mi.Point2f,
                         stride: int) -> List[Dict[str, Any]]:
    """
    可視 bbox（primary-ray hit）方式で annotations を生成するメイン処理。

    Args:
        scene: Mitsuba scene
        sensor: 使用する sensor
        geom: film geometry（crop/full 対応）
        shape_ids: shape_index と同順の識別子
        time: sample_ray に渡す time
        sample1: sample_ray に渡す sample1（RGBでは実質ダミーでOKな場合が多い）
        aperture_sample: DOF の再現性のため固定する aperture サンプル
        stride: ピクセル間引き（1なら全ピクセル、2なら縦横2ピクセル飛ばし）

    Returns:
        List[Dict[str, Any]]: JSON の annotations 配列に入れる dict のリスト
    """
    W, H = geom.crop_size
    shapes_count = len(shape_ids)

    stats: List[ShapeStats] = [ShapeStats.new(i, shape_ids[i]) for i in range(shapes_count)]

    s = max(1, int(stride))
    for y in range(0, H, s):
        for x in range(0, W, s):
            u, v = crop_pixel_to_film_uv(x, y, geom)

            ray, _ = sensor.sample_ray(
                time,
                sample1,
                mi.Point2f(u, v),
                aperture_sample
            )

            pi = scene.ray_intersect_preliminary(ray)
            if not pi.is_valid():
                continue

            idx = int(pi.shape_index)
            if idx < 0 or idx >= shapes_count:
                continue

            t = float(pi.t)
            stats[idx].update(x, y, t)

    annotations: List[Dict[str, Any]] = []
    for st in stats:
        if st.has_bbox():
            annotations.append(st.to_annotation())

    return annotations


def main() -> None:
    """
    CLI エントリポイント。

    - variant を設定
    - scene をロード
    - film geometry と shape_id リストを作成
    - export_visible_bboxes を実行
    - スキーマ付き JSON を保存
    """
    args = parse_args()
    mi.set_variant(args.variant)

    scene = mi.load_file(args.scene)
    sensors = scene.sensors()
    if args.sensor_index < 0 or args.sensor_index >= len(sensors):
        raise SystemExit("Invalid --sensor-index: %d (available: %d)" % (args.sensor_index, len(sensors)))
    sensor = sensors[args.sensor_index]
    film = sensor.film()

    geom = get_film_geometry(film)
    shape_ids = list_shape_ids(scene)

    aperture_sample = mi.Point2f(float(args.aperture_u), float(args.aperture_v))

    annotations = export_visible_bboxes(
        scene=scene,
        sensor=sensor,
        geom=geom,
        shape_ids=shape_ids,
        time=float(args.time),
        sample1=float(args.sample1),
        aperture_sample=aperture_sample,
        stride=int(args.stride),
    )

    out: Dict[str, Any] = {
        "schema": {
            "name": "mitsuba_visible_bbox",
            "version": 1,
            "method": "primary_ray_hit",
        },
        "image": {
            "width": int(geom.crop_size[0]),
            "height": int(geom.crop_size[1]),
            "scene": args.scene,
            "variant": args.variant,
            "sensor_index": int(args.sensor_index),
            "film": {
                "full_size": [int(geom.full_size[0]), int(geom.full_size[1])],
                "crop_size": [int(geom.crop_size[0]), int(geom.crop_size[1])],
                "crop_offset": [int(geom.crop_offset[0]), int(geom.crop_offset[1])],
            }
        },
        "annotations": annotations,
        "notes": {
            "hits_meaning": "Number of pixels where this shape was the closest intersection (visible as front-most).",
            "depth_meaning": "Ray distance t statistics among visible pixels; smaller means nearer to the camera.",
            "bbox_coords": "bbox coordinates are in crop-image pixel space (0..W-1, 0..H-1).",
        }
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("wrote %s (%d objects)" % (args.out, len(annotations)))


if __name__ == "__main__":
    main()
