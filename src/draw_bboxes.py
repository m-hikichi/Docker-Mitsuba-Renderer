#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
draw_bboxes.py

export_visible_bboxes.py が出力した JSON を読み込み、画像に bbox を描画して保存する。

レイヤリング（重要）:
- 大きい床 bbox の「塗り」が小物の「枠線」を消さないように、
  2パス描画を採用する:
  1) fill（塗り）を先に全部描く
  2) outline（枠線）を「遠い→近い」の順で描く（近いほど最後に描かれて上に来る）

拡張ポイント:
- 色を shape_id/shape_index で変える
- 並べ替えキーを変更（depth_min/mean/hits 等）
- ラベル内容の拡張
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont


def parse_args() -> argparse.Namespace:
    """
    CLI 引数を定義して parse する。

    Returns:
        argparse.Namespace: 入力画像/JSON/出力、描画設定、並べ替え設定など
    """
    ap = argparse.ArgumentParser(description="Draw bboxes from Mitsuba bbox JSON onto an image.")
    ap.add_argument("--image", required=True, help="Input rendered image path (e.g., cbox.png)")
    ap.add_argument("--json", required=True, help="Input bbox json path (e.g., bboxes.json)")
    ap.add_argument("--out", required=True, help="Output image path (e.g., render_bbox.png)")

    ap.add_argument("--order", choices=["near_on_top", "xml_order"], default="near_on_top",
                    help="near_on_top: draw outlines so nearer objects appear on top.")
    ap.add_argument("--depth-key", choices=["auto", "mean", "min", "none"], default="auto",
                    help="Which depth field to use when ordering outlines.")
    ap.add_argument("--tie-breaker", choices=["area", "none"], default="area",
                    help="How to break ties in ordering (area helps large floor bboxes go below).")

    ap.add_argument("--thickness", type=int, default=3, help="Outline thickness in pixels")
    ap.add_argument("--fill-alpha", type=int, default=40,
                    help="Fill alpha (0 disables fill). Keep low to avoid hiding details.")
    ap.add_argument("--label", choices=["none", "shape_id", "shape_index", "both"], default="shape_id")
    ap.add_argument("--font-size", type=int, default=14)

    ap.add_argument("--no-scale", action="store_true",
                    help="Disable auto-scaling even if JSON image size differs from input image.")
    return ap.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    """
    JSON ファイルを UTF-8 で読み込む。

    Args:
        path: bboxes.json のパス

    Returns:
        dict: JSON のトップレベル辞書
    """
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_bbox_xyxy(ann: Dict[str, Any]) -> Tuple[int, int, int, int]:
    """
    annotation から bbox を xyxy 形式で取得する。
    JSON が xywh しか持たない場合でも xyxy に変換して返す。

    Args:
        ann: annotations の1要素

    Returns:
        (xmin, ymin, xmax, ymax) の整数タプル
    """
    if "bbox_xyxy" in ann:
        xmin, ymin, xmax, ymax = ann["bbox_xyxy"]
        return int(xmin), int(ymin), int(xmax), int(ymax)
    if "bbox_xywh" in ann:
        x, y, w, h = ann["bbox_xywh"]
        xmin, ymin = int(x), int(y)
        xmax = xmin + int(w) - 1
        ymax = ymin + int(h) - 1
        return xmin, ymin, xmax, ymax
    raise KeyError("annotation must contain bbox_xyxy or bbox_xywh")


def clip_bbox(xmin: int, ymin: int, xmax: int, ymax: int, W: int, H: int) -> Tuple[int, int, int, int]:
    """
    bbox を画像範囲内にクリップする。

    Args:
        xmin,ymin,xmax,ymax: bbox
        W,H: 画像サイズ

    Returns:
        クリップ後の bbox（xmin<=xmax, ymin<=ymax を保証）
    """
    xmin = max(0, min(xmin, W - 1))
    ymin = max(0, min(ymin, H - 1))
    xmax = max(0, min(xmax, W - 1))
    ymax = max(0, min(ymax, H - 1))
    if xmax < xmin: xmax = xmin
    if ymax < ymin: ymax = ymin
    return xmin, ymin, xmax, ymax


def compute_scale(data: Dict[str, Any], image_size: Tuple[int, int], no_scale: bool) -> Tuple[float, float]:
    """
    JSON 側の width/height と、入力画像のサイズが異なる場合にスケール係数を計算する。

    Args:
        data: bboxes.json の内容
        image_size: 入力画像の (W, H)
        no_scale: True の場合は常に (1.0, 1.0)

    Returns:
        (sx, sy): bbox 座標へ掛けるスケール係数
    """
    W, H = image_size
    jW = int(data.get("image", {}).get("width", W))
    jH = int(data.get("image", {}).get("height", H))

    if no_scale or (jW == W and jH == H):
        return 1.0, 1.0

    sx = W / float(jW) if jW > 0 else 1.0
    sy = H / float(jH) if jH > 0 else 1.0
    return sx, sy


def get_depth_value(ann: Dict[str, Any], depth_key: str) -> float:
    """
    並べ替え用の深度値（小さいほど手前）を返す。

    Args:
        ann: annotation
        depth_key:
            - "mean": depth_mean を使用
            - "min": depth_min を使用
            - "auto": mean があれば mean、なければ min
            - "none": 深度を使わず inf を返す（深度順無効）

    Returns:
        float: 深度値（未設定なら inf）
    """
    if depth_key == "none":
        return float("inf")

    dmean = ann.get("depth_mean", None)
    dmin = ann.get("depth_min", None)

    if depth_key == "mean":
        return float(dmean) if dmean is not None else float("inf")
    if depth_key == "min":
        return float(dmin) if dmin is not None else float("inf")

    if dmean is not None:
        return float(dmean)
    if dmin is not None:
        return float(dmin)
    return float("inf")


def area_of(ann: Dict[str, Any]) -> int:
    """
    annotation の面積（area）を返す。無ければ bbox から計算する。

    Args:
        ann: annotation

    Returns:
        int: bbox 面積
    """
    if "area" in ann:
        return int(ann["area"])
    xmin, ymin, xmax, ymax = ensure_bbox_xyxy(ann)
    return int((xmax - xmin + 1) * (ymax - ymin + 1))


def sort_for_outline(annotations: List[Dict[str, Any]],
                     order: str,
                     depth_key: str,
                     tie_breaker: str) -> List[Dict[str, Any]]:
    """
    枠線（outline）描画のための順序を決める。

    near_on_top の場合:
      - 枠線を「遠い→近い」で描く（近いほど最後＝上に重なる）
      - tie_breaker=area の場合は面積が大きいものを先に描きやすくする
        → 床の巨大 bbox が小物を潰しにくい

    Args:
        annotations: 元の annotations
        order: "near_on_top" or "xml_order"
        depth_key: 深度の参照方法（auto/mean/min/none）
        tie_breaker: 同深度時のタイブレーク（area/none）

    Returns:
        並べ替え後の annotations
    """
    if order == "xml_order":
        return list(annotations)

    def key_fn(a: Dict[str, Any]) -> Tuple[float, int]:
        d = get_depth_value(a, depth_key)  # smaller = nearer
        tb = area_of(a) if tie_breaker == "area" else 0
        return (d, tb)

    # far -> near（depth が大きいほど遠い）なので reverse=True
    return sorted(annotations, key=key_fn, reverse=True)


def draw_rect_thick(draw: ImageDraw.ImageDraw,
                    bbox: Tuple[int, int, int, int],
                    outline_rgba: Tuple[int, int, int, int],
                    width: int) -> None:
    """
    太線の矩形を描く（Pillow の version 差異回避のため自前で反復描画）。

    Args:
        draw: ImageDraw
        bbox: (xmin,ymin,xmax,ymax)
        outline_rgba: 枠線色（RGBA）
        width: 太さ（ピクセル）
    """
    xmin, ymin, xmax, ymax = bbox
    w = max(1, int(width))
    for i in range(w):
        draw.rectangle([xmin - i, ymin - i, xmax + i, ymax + i], outline=outline_rgba)


def get_font(font_size: int) -> ImageFont.ImageFont:
    """
    フォントを取得する。DejaVuSans があればそれを使い、無ければデフォルトへフォールバック。

    Args:
        font_size: フォントサイズ

    Returns:
        ImageFont
    """
    try:
        return ImageFont.truetype("DejaVuSans.ttf", int(font_size))
    except Exception:
        return ImageFont.load_default()


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    """
    テキスト描画のサイズを取得する（Pillow の API 差異を吸収）。

    Args:
        draw: ImageDraw
        text: 文字列
        font: フォント

    Returns:
        (width, height)
    """
    if hasattr(draw, "textbbox"):
        box = draw.textbbox((0, 0), text, font=font)
        return int(box[2] - box[0]), int(box[3] - box[1])
    w, h = draw.textsize(text, font=font)  # type: ignore[attr-defined]
    return int(w), int(h)


def make_label(ann: Dict[str, Any], mode: str) -> str:
    """
    annotation からラベル文字列を生成する。

    Args:
        ann: annotation
        mode:
            - none
            - shape_id
            - shape_index
            - both

    Returns:
        描画するラベル文字列（空文字なら描画しない）
    """
    if mode == "none":
        return ""
    sid = str(ann.get("shape_id", ""))
    sidx = str(ann.get("shape_index", ""))
    if mode == "shape_id":
        return sid
    if mode == "shape_index":
        return sidx
    if sid and sidx:
        return "%s (%s)" % (sid, sidx)
    return sid or sidx


def transform_bbox(ann: Dict[str, Any], sx: float, sy: float, W: int, H: int) -> Tuple[int, int, int, int]:
    """
    JSON の bbox を入力画像座標へ変換する（スケール補正 + クリップ）。

    Args:
        ann: annotation
        sx, sy: スケール係数
        W, H: 入力画像サイズ

    Returns:
        (xmin, ymin, xmax, ymax) in input-image pixel space
    """
    xmin, ymin, xmax, ymax = ensure_bbox_xyxy(ann)
    xmin = int(round(xmin * sx))
    ymin = int(round(ymin * sy))
    xmax = int(round(xmax * sx))
    ymax = int(round(ymax * sy))
    return clip_bbox(xmin, ymin, xmax, ymax, W, H)


def main() -> None:
    """
    CLI エントリポイント。

    - JSON を読み込み
    - 必要なら bbox 座標をスケール補正
    - 枠線を「遠い→近い」で描画して “手前ほど上” を実現
    - 塗り→枠線の2パスで、床 bbox が小物の枠線を消すのを回避
    """
    args = parse_args()

    img_path = Path(args.image)
    json_path = Path(args.json)
    out_path = Path(args.out)

    data = load_json(json_path)
    annotations: List[Dict[str, Any]] = list(data.get("annotations", []))

    img = Image.open(img_path).convert("RGBA")
    W, H = img.size
    sx, sy = compute_scale(data, (W, H), bool(args.no_scale))

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = get_font(int(args.font_size))

    sorted_for_outline = sort_for_outline(
        annotations,
        order=str(args.order),
        depth_key=str(args.depth_key),
        tie_breaker=str(args.tie_breaker)
    )

    # ---- Pass 1: Fill ----
    fill_alpha = max(0, min(int(args.fill_alpha), 255))
    if fill_alpha > 0:
        fill_rgba = (255, 0, 0, fill_alpha)
        for ann in sorted_for_outline:
            bbox = transform_bbox(ann, sx, sy, W, H)
            draw.rectangle(list(bbox), fill=fill_rgba)

    # ---- Pass 2: Outline + Label ----
    outline_rgba = (255, 0, 0, 220)
    thickness = max(1, int(args.thickness))

    for ann in sorted_for_outline:
        bbox = transform_bbox(ann, sx, sy, W, H)
        draw_rect_thick(draw, bbox, outline_rgba, thickness)

        label = make_label(ann, str(args.label))
        if label:
            pad = 3
            tw, th = text_size(draw, label, font)
            xmin, ymin, _, _ = bbox

            tx = xmin
            ty = max(0, ymin - (th + pad * 2 + 2))
            bg = (0, 0, 0, 160)
            draw.rectangle([tx, ty, tx + tw + pad * 2, ty + th + pad * 2], fill=bg)
            draw.text((tx + pad, ty + pad), label, font=font, fill=(255, 255, 255, 230))

    out = Image.alpha_composite(img, overlay).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path)
    print("Wrote:", str(out_path))


if __name__ == "__main__":
    main()
