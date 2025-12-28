#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from typing import Tuple, Any, Dict


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _ensure_int_bbox_xyxy(ann: Dict[str, Any]) -> Tuple[int, int, int, int]:
    """
    Accepts either bbox_xyxy or bbox_xywh.
    Returns (xmin, ymin, xmax, ymax) as ints.
    """
    if "bbox_xyxy" in ann:
        xmin, ymin, xmax, ymax = ann["bbox_xyxy"]
        return int(xmin), int(ymin), int(xmax), int(ymax)

    if "bbox_xywh" in ann:
        x, y, w, h = ann["bbox_xywh"]
        xmin, ymin = int(x), int(y)
        xmax = int(x) + int(w) - 1
        ymax = int(y) + int(h) - 1
        return xmin, ymin, xmax, ymax

    raise KeyError("annotation must contain bbox_xyxy or bbox_xywh")


def _clip_bbox(xmin: int, ymin: int, xmax: int, ymax: int, W: int, H: int) -> Tuple[int, int, int, int]:
    xmin = max(0, min(xmin, W - 1))
    ymin = max(0, min(ymin, H - 1))
    xmax = max(0, min(xmax, W - 1))
    ymax = max(0, min(ymax, H - 1))
    if xmax < xmin:
        xmax = xmin
    if ymax < ymin:
        ymax = ymin
    return xmin, ymin, xmax, ymax


def _draw_rect_thick(draw: ImageDraw.ImageDraw, bbox: Tuple[int, int, int, int], outline, width: int) -> None:
    """
    Pillow の rectangle(width=) が環境によって効かないケース向けに手動で太線化。
    """
    xmin, ymin, xmax, ymax = bbox
    for i in range(max(1, width)):
        draw.rectangle([xmin - i, ymin - i, xmax + i, ymax + i], outline=outline)


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    """
    Pillow のバージョン差異（textbbox の有無）を吸収して文字サイズを返す。
    """
    if hasattr(draw, "textbbox"):
        box = draw.textbbox((0, 0), text, font=font)
        return int(box[2] - box[0]), int(box[3] - box[1])
    # 古い Pillow
    w, h = draw.textsize(text, font=font)  # type: ignore[attr-defined]
    return int(w), int(h)


def main() -> None:
    ap = argparse.ArgumentParser(description="Draw bboxes from Mitsuba bbox JSON onto an image.")
    ap.add_argument("--image", required=True, help="Input rendered image path (e.g., cbox.png)")
    ap.add_argument("--json", required=True, help="Input bbox json path (e.g., bboxes.json)")
    ap.add_argument("--out", required=True, help="Output image path (e.g., render_bbox.png)")
    ap.add_argument("--label", choices=["none", "shape_id", "shape_index", "both"], default="shape_id",
                    help="Label to draw on bbox")
    ap.add_argument("--thickness", type=int, default=2, help="BBox outline thickness in pixels")
    ap.add_argument("--font_size", type=int, default=14, help="Font size for labels")
    ap.add_argument("--no_scale", action="store_true",
                    help="Do not auto-scale bbox coords even if JSON image size differs from input image")
    args = ap.parse_args()

    img_path = Path(args.image)
    json_path = Path(args.json)
    out_path = Path(args.out)

    data = _load_json(json_path)

    img = Image.open(img_path).convert("RGBA")
    W, H = img.size

    # JSONに記録されたサイズ（レンダリング時サイズ）との差があればスケール補正
    jW = int(data.get("image", {}).get("width", W))
    jH = int(data.get("image", {}).get("height", H))

    if args.no_scale or (jW == W and jH == H):
        sx, sy = 1.0, 1.0
    else:
        sx = W / float(jW) if jW > 0 else 1.0
        sy = H / float(jH) if jH > 0 else 1.0

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # フォント（無ければデフォルト）
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", args.font_size)
    except Exception:
        font = ImageFont.load_default()

    annotations = data.get("annotations", [])
    for ann in annotations:
        xmin, ymin, xmax, ymax = _ensure_int_bbox_xyxy(ann)

        # スケール補正
        xmin = int(round(xmin * sx))
        ymin = int(round(ymin * sy))
        xmax = int(round(xmax * sx))
        ymax = int(round(ymax * sy))

        xmin, ymin, xmax, ymax = _clip_bbox(xmin, ymin, xmax, ymax, W, H)

        # bbox 描画（可読性重視で半透明塗り + 枠線）
        fill_rgba = (255, 0, 0, 40)      # 半透明
        outline_rgba = (255, 0, 0, 200)  # 枠線

        draw.rectangle([xmin, ymin, xmax, ymax], fill=fill_rgba)
        _draw_rect_thick(draw, (xmin, ymin, xmax, ymax), outline=outline_rgba, width=args.thickness)

        # ラベル描画（任意）
        if args.label != "none":
            shape_id = str(ann.get("shape_id", ""))
            shape_index = str(ann.get("shape_index", ""))

            if args.label == "shape_id":
                text = shape_id
            elif args.label == "shape_index":
                text = shape_index
            else:  # both
                text = ("%s (%s)" % (shape_id, shape_index)) if shape_id else shape_index

            if text:
                pad = 3
                tw, th = _text_size(draw, text, font)

                tx = xmin
                ty = max(0, ymin - (th + pad * 2 + 2))

                bg = (0, 0, 0, 160)
                draw.rectangle([tx, ty, tx + tw + pad * 2, ty + th + pad * 2], fill=bg)
                draw.text((tx + pad, ty + pad), text, font=font, fill=(255, 255, 255, 230))

    # 合成して保存
    out = Image.alpha_composite(img, overlay).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path)
    print("Wrote:", str(out_path))


if __name__ == "__main__":
    main()
