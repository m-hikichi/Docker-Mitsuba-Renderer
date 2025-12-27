# Mitsuba 3 Docker variants ガイド

このリポジトリの Dockerfile は、Mitsuba 3 をソースからビルドし、`mitsuba.conf` の `enabled` に指定した **variants（ビルドされるレンダラーの実体）** を同梱します。

本 Dockerfile は以下の設計です。

* `MI_PRESET` で **ベース（必須）variants** を選ぶ

  * `cpu`: `scalar_rgb` + `llvm_ad_rgb`
  * `gpu`: `scalar_rgb` + `cuda_ad_rgb`
* `MI_EXTRA_VARIANTS` で **追加 variants** を指定する（空白 or カンマ区切り）
* **ベース＋追加の合計が 5 を超える場合はエラーで停止**（コンパイル時間・メモリ増大を防ぐため）

> 注: どの variants が実際に有効化されているかは、ビルド後に `mi.variants()` で確認できます。

---

## 1. variants とは何か

Mitsuba 3 は「計算バックエンド」「自動微分の有無」「色の表現」「偏光」「精度」などの組み合わせを切り替えられる “retargetable renderer” で、その組み合わせの単位を **variant** と呼びます。

variant 名は概ね次の要素で構成されます。

```
<backend>[_ad]_<color>[_polarized][_double]
```

例:

* `scalar_rgb`
* `llvm_ad_spectral`
* `cuda_ad_spectral_polarized`
* `llvm_ad_rgb_double`

---

## 2. 各要素で「何ができるか」

### 2.1 backend（計算バックエンド）

* `scalar`
  CPUで通常の浮動小数点演算、1本ずつレイを処理。デバッグ・理解しやすい。
* `llvm`
  CPUで Dr.Jit/LLVM により JIT コンパイルされ、複数コア・ベクタ化で並列処理。
* `cuda`
  NVIDIA GPU 上で並列処理（JITでCUDAカーネル化）。大量のパスを同時に処理しやすい。

### 2.2 `_ad`（Automatic Differentiation: 自動微分）

* `llvm` / `cuda` に `_ad` を付けると、レンダリングを「微分可能な関数」として扱い、カメラ姿勢・形状・BSDF・テクスチャ等の入力パラメータに対する勾配を得られます。
* 逆レンダリング（最適化・推定）用途で重要です。

### 2.3 color（色表現）

* `mono`
  色概念を無効化（モノクロ）。レーザー等の単色シーンやテストで便利。入力に色があれば自動的にグレースケール化。
* `rgb`
  RGBベース。一般的な用途の既定として分かりやすい一方、物理的には近似で問題が出る場合がある。
* `spectral`
  可視域を波長として扱うスペクトルレンダリング。測定スペクトルがある場合や色再現精度を上げたい場合に有利。既定では最終出力はRGB画像（必要ならスペクトル出力対応の film を使う）。

### 2.4 `_polarized`（偏光レンダリング）

* 偏光状態（Stokes ベクトルなど）を追跡し、偏光に起因する情報を出力できます。
* 一般の見た目レンダリングでは必須でないことが多いですが、計測・材料推定・逆問題で有用です。
* 目安として **1.5〜2倍程度のレンダリング時間増**が発生し得ます。

### 2.5 `_double`（倍精度）

* 64-bit 浮動小数点で計算（デバッグや数値誤差切り分けに有用）。
* ただし、Embree/OptiX が倍精度を完全にはサポートしないため、特に GPU 系では “全面倍精度” にならない点に注意が必要です。

---

## 3. 追加できる variants 一覧（命名規則ベース）

Mitsuba 3 には多数の variants が存在します。代表的には次の組み合わせです。

### 3.1 scalar（CPU / 非JIT）

* `scalar_mono`, `scalar_rgb`, `scalar_spectral`
* それぞれに `_polarized` / `_double` あり

### 3.2 llvm（CPU / JIT）

* `llvm_mono`, `llvm_rgb`, `llvm_spectral`
* それぞれに `_polarized` / `_double` あり

### 3.3 llvm_ad（CPU / JIT + 自動微分）

* `llvm_ad_mono`, `llvm_ad_rgb`, `llvm_ad_spectral`
* それぞれに `_polarized` / `_double` あり

### 3.4 cuda（GPU / JIT）

* `cuda_mono`, `cuda_rgb`, `cuda_spectral`
* それぞれに `_polarized` / `_double` あり

### 3.5 cuda_ad（GPU / JIT + 自動微分）

* `cuda_ad_mono`, `cuda_ad_rgb`, `cuda_ad_spectral`
* それぞれに `_polarized` / `_double` あり

> 実際に「そのビルドで使える」かどうかは、必ず `mi.variants()` の出力で確認してください。

---

## 4. Docker build の使い方

### 4.1 CPU（最小構成：2 variants）

```bash
docker build -t mitsuba3:cpu \
  --build-arg MI_PRESET=cpu \
  --build-arg MI_EXTRA_VARIANTS="" \
  .
```

### 4.2 GPU（最小構成：2 variants）

```bash
docker build -t mitsuba3:gpu \
  --build-arg MI_PRESET=gpu \
  --build-arg MI_EXTRA_VARIANTS="" \
  .
```

### 4.3 追加 variants を指定する（合計 5 以内）

`MI_EXTRA_VARIANTS` は「空白」または「カンマ」で区切れます。

#### 例: CPUでスペクトル + 微分（合計4）

```bash
docker build -t mitsuba3:cpu-spectral \
  --build-arg MI_PRESET=cpu \
  --build-arg MI_EXTRA_VARIANTS="scalar_spectral llvm_ad_spectral" \
  .
```

#### 例: GPUでスペクトル + 微分（合計4）

```bash
docker build -t mitsuba3:gpu-spectral \
  --build-arg MI_PRESET=gpu \
  --build-arg MI_EXTRA_VARIANTS="scalar_spectral cuda_ad_spectral" \
  .
```

#### 例: 偏光（CPU、合計5）

```bash
docker build -t mitsuba3:cpu-polarized \
  --build-arg MI_PRESET=cpu \
  --build-arg MI_EXTRA_VARIANTS="scalar_spectral_polarized llvm_ad_spectral llvm_ad_spectral_polarized" \
  .
```

### 4.4 variants を 6 個以上にするとエラー

```bash
docker build -t mitsuba3:too-many \
  --build-arg MI_PRESET=cpu \
  --build-arg MI_EXTRA_VARIANTS="scalar_spectral llvm_ad_spectral llvm_ad_rgb_polarized scalar_rgb_polarized" \
  .
```

---

## 5. コンテナ内で variants を確認・利用する

### 5.1 利用可能 variants を列挙

```bash
docker run --rm -it mitsuba3:cpu python -c "import mitsuba as mi; print(mi.variants())"
```

### 5.2 Python で variant を選択してレンダ

```python
import mitsuba as mi
mi.set_variant('llvm_ad_rgb')  # 例: CPU JIT + AD + RGB
# scene = mi.load_file("scene.xml")
# img = mi.render(scene, spp=128)
```

---

## 6. 注意点（ビルドが失敗する場合）

* variants の組み合わせによっては、Python stub 生成の都合で「不許可な組み合わせ」と判断され、ビルドエラーになる場合があります。
  その場合はエラーメッセージの指示に従い、追加すべき variant を `MI_EXTRA_VARIANTS` に足してください。
* `MI_PRESET=cpu` のときに `cuda_*` を追加するなど、実行環境に合わない variants を入れると失敗します。

---

# 参考（根拠ドキュメント）

* variants の構成要素（backend / AD / 色表現 / 偏光 / 精度）と、mono/rgb/spectral の説明、偏光・倍精度の注意点: ([mitsuba.readthedocs.io][1])
* `mitsuba.conf` の必須条件（`scalar_rgb` 必須、AD variant 必須）と「5超は非推奨」、stub 生成の注意: ([mitsuba.readthedocs.io][2])
* backend の簡潔な説明（scalar/llvm/cuda）と variant の切り替えの考え方: ([mitsuba.readthedocs.io][3])
* pip 版が同梱する variants（参考）: ([PyPI][4])
* 偏光レンダリングの具体例（`*_polarized` の使い方）: ([mitsuba.readthedocs.io][5])

---

[1]: https://mitsuba.readthedocs.io/en/stable/src/key_topics/variants.html "Choosing variants - Mitsuba 3"
[2]: https://mitsuba.readthedocs.io/en/stable/src/developer_guide/compiling.html "Compiling the system - Mitsuba 3"
[3]: https://mitsuba.readthedocs.io/en/stable/src/quickstart/mitsuba_quickstart.html "Mitsuba quickstart - Mitsuba 3"
[4]: https://pypi.org/project/mitsuba/ "mitsuba · PyPI"
[5]: https://mitsuba.readthedocs.io/en/stable/src/rendering/polarized_rendering.html "Polarized rendering - Mitsuba 3"
