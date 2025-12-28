import json
import mitsuba as mi

mi.set_variant("scalar_rgb")  # 例: scalar_rgb / llvm_ad_rgb / cuda_ad_rgb など

scene = mi.load_file("../scene/scenes/ibl_bunny.xml")
sensor = scene.sensors()[0]
film = sensor.film()

# 画像サイズ（crop を考慮）
W, H = film.crop_size()

# shape_index -> 表示名（id が空なら連番）
shapes = scene.shapes()
shape_names = []
for i, s in enumerate(shapes):
    sid = s.id()
    shape_names.append(sid if sid else f"shape_{i}")

INF = 10**9
# shapeごとの[xmin, ymin, xmax, ymax]
acc = [[INF, INF, -INF, -INF] for _ in range(len(shapes))]

time = 0.0
sample1 = 0.5              # 波長/スペクトル用（RGBなら実質ダミーでOKなことが多い）
aperture_sample = mi.Point2f(0.5, 0.5)  # 被写界深度を安定化（中心固定）

for y in range(H):
    v = (y + 0.5) / H
    for x in range(W):
        u = (x + 0.5) / W

        # ピクセル中心の主光線
        ray, _ = sensor.sample_ray(time, sample1, mi.Point2f(u, v), aperture_sample)

        # 最前面交差（高速）
        pi = scene.ray_intersect_preliminary(ray)
        if not pi.is_valid():
            continue

        idx = int(pi.shape_index)  # shape index
        b = acc[idx]
        if x < b[0]: b[0] = x
        if y < b[1]: b[1] = y
        if x > b[2]: b[2] = x
        if y > b[3]: b[3] = y

# JSON（COCO 風に近い形）
annotations = []
for idx, (xmin, ymin, xmax, ymax) in enumerate(acc):
    if xmax < 0:
        continue
    w = (xmax - xmin + 1)
    h = (ymax - ymin + 1)
    annotations.append({
        "shape_index": idx,
        "shape_id": shape_names[idx],
        "bbox_xywh": [int(xmin), int(ymin), int(w), int(h)],
        "bbox_xyxy": [int(xmin), int(ymin), int(xmax), int(ymax)],
        "area": int(w * h),
    })

out = {
    "image": {
        "width": int(W),
        "height": int(H),
        "scene": "scene.xml",
    },
    "annotations": annotations
}

with open("bboxes.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(f"wrote bboxes.json ({len(annotations)} objects)")
