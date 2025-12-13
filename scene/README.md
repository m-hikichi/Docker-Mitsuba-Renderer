<a id="sec-file-format"></a>

<!-- Source: https://mitsuba.readthedocs.io/en/latest/src/key_topics/scene_format.html -->

# Scene XML ファイル形式

Mitsuba は、シーンを表現するためにシンプルかつ汎用的な XML ベースの形式を使用します。フレームワークの思想として、機能の離散的なブロックをプラグインとして表現するため、シーンファイルは「どのプラグインを生成し、どのように組み合わせるか」を指定する **レシピ** として解釈できます。以下では、いくつかの例を通して、この形式で表現できる範囲（スコープ）の感覚を掴みます。

照明がなく、デフォルトのカメラ設定で、1 つのメッシュだけを持つシンプルなシーンは、例えば次のようになります。

```xml
<scene version="3.0.0">
    <shape type="obj">
        <string name="filename" value="dragon.obj"/>
    </shape>
</scene>
```

最初の行にある `version` 属性は、このシーンを作成した Mitsuba のリリースを表します。これにより、将来シーン記述言語が変更される可能性があっても、Mitsuba がファイルを正しく処理できるようになります。

この例には、形式を理解する上で最も重要な点がすでに含まれています。すなわち、これは `<scene>` や `<shape>` タグで生成されるような **オブジェクト** から構成され、さらにそれらは入れ子（ネスト）にできます。各オブジェクトは、挙動を特徴づける **プロパティ**（例: `<string>` タグ）を任意で受け取れます。ルートオブジェクト（`<scene>`）を除き、すべてのオブジェクトはレンダラーにディスク上からプラグインを検索して読み込ませるため、`type=".."` パラメータでプラグイン名を指定する必要があります。

また、オブジェクトタグは「どの種類のオブジェクトを生成するか」もレンダラーに伝えます。例えば、`<shape>` タグで読み込まれるプラグインは **Shape** インターフェースに準拠していなければなりません。`obj` というプラグインはこれを満たしており、`:ref:`Wavefront OBJ ローダー <shape-obj>`` を含みます。同様に、次のようにも書けます。

```xml
<scene version="3.0.0">
    <shape type="sphere">
        <float name="radius" value="10"/>
    </shape>
</scene>
```

これは別のプラグイン（`sphere`）を読み込みますが、同じく **Shape** であり、ワールド空間で半径 10 の `:ref:`球体 <shape-sphere>`` を表します。Mitsuba には多数のプラグインが同梱されています。詳細は `:ref:`プラグインリファレンス <sec-plugins>`` を参照してください。

最も一般的なシーン構成は、インテグレーター（integrator）、いくつかのジオメトリ、センサー（例: カメラ）、フィルム、サンプラー、そして 1 つ以上のエミッター（光源）を宣言することです。より複雑な例を示します。

```xml
<scene version="3.0.0">
    <integrator type="path">
        <!-- 最大パス長 8 のパストレーサーを生成 -->
        <integer name="max_depth" value="8"/>
    </integrator>

    <!-- 視野角 45 度の透視投影カメラを生成 -->
    <sensor type="perspective">
        <!-- Y 軸の周りに 180 度回転 -->
        <transform name="to_world">
            <rotate y="1" angle="180"/>
        </transform>
        <float name="fov" value="45"/>

        <!-- 基本的な独立サンプリング戦略で
             ピクセルあたり 32 サンプルでレンダリング -->
        <sampler type="independent">
            <integer name="sample_count" value="32"/>
        </sampler>

        <!-- HD 解像度で EXR 画像を生成 -->
        <film type="hdrfilm">
            <integer name="width" value="1920"/>
            <integer name="height" value="1080"/>
        </film>
    </sensor>

    <!-- 粗いガラス材質のドラゴンメッシュ（OBJ）を追加 -->
    <shape type="obj">
        <string name="filename" value="dragon.obj"/>

        <bsdf type="roughdielectric">
            <!-- マテリアルの粗さパラメータを調整 -->
            <float name="alpha" value="0.01"/>
        </bsdf>
    </shape>

    <!-- もう 1 つのメッシュを追加。今度は Mitsuba 独自の
         （コンパクトな）バイナリ形式で保存されたもの -->
    <shape type="serialized">
        <string name="filename" value="lightsource.serialized"/>
        <transform name="to_world">
            <translate x="5" y="-3" z="1"/>
        </transform>

        <!-- このメッシュはエリアエミッター（面光源） -->
        <emitter type="area">
            <rgb name="radiance" value="100,400,100"/>
        </emitter>
    </shape>
</scene>
```

この例では、いくつかの新しいオブジェクト種別（`integrator`、`sensor`、`bsdf`、`sampler`、`film`、`emitter`）と、プロパティ種別（`integer`、`transform`、`rgb`）が登場します。例から分かる通り、オブジェクトは通常トップレベルに宣言されますが、別オブジェクトと本質的な関連がある場合は子要素としてネストされます。例えば、BSDF は通常、特定の幾何形状（shape）に固有であるため、shape の子オブジェクトとして現れます。同様に、サンプラーとフィルムは、センサーからのレイ生成方法や放射輝度サンプルの記録方法に影響するため、sensor の内部にネストされます。以下の表は、利用可能なオブジェクト種別の概要です。

**表（label: table-xml-objects）:** この表は、**オブジェクト** の種類と対応するタグを列挙し、各カテゴリのプラグイン例も示します。

| XML tag | Description | `type` examples |
|---|---|---|
| `bsdf` | BSDF は、光がシーン内の表面とどのように相互作用するか（すなわち **マテリアル**）を記述します。 | `diffuse`, `conductor` |
| `emitter` | エミッタープラグインは、光源とその放射特性（エミッションプロファイル）を指定します。 | `constant`, `envmap`, `point` |
| `film` | フィルムプラグインは、測定値を最終的な出力ファイルへ変換し、ディスクに書き出します。 | `hdrfilm`, `specfilm` |
| `integrator` | インテグレーターは、光輸送方程式を解くためのレンダリング手法を実装します。 | `path`, `direct`, `depth` |
| `rfilter` | 再構成フィルターは、`film` がサンプル集合を出力画像へ変換する方法を制御します。 | `box`, `gaussian` |
| `sampler` | `integrator` で使用されるサンプル生成プラグインです。 | `independent`, `multijitter` |
| `sensor` | センサー（カメラ等）は放射輝度を測定する役割を担います。 | `perspective`, `orthogonal` |
| `shape` | shape プラグインは、シーン内で異なる種類のマテリアル間の遷移を示す表面を定義します。 | `obj`, `ply`, `serialized` |
| `texture` | テクスチャプラグインは、表面上で空間的に変化する信号を表現します。 | `bitmap`, `checkerboard` |

---

## Properties

このサブセクションでは、プロパティをオブジェクトに渡す方法をすべて説明します。特定のプラグインがどのプロパティを受け取れるかを知りたい場合は、代わりに `:ref:`プラグインドキュメント <sec-plugins>`` を参照してください。

### Numbers

整数値と浮動小数点値は次のように渡せます。

```xml
<integer name="int_property" value="1234"/>
<float name="float_property" value="-1.5e3"/>
```

なお、オブジェクトが期待する形式に従う必要があります。つまり、その名前で浮動小数点を期待しているオブジェクトに対して、整数プロパティを渡すことはできません。

### Booleans

ブール値は次のように渡せます。

```xml
<boolean name="bool_property" value="true"/>
```

### Strings

文字列の受け渡しも同様に簡単です。

```xml
<string name="string_property" value="This is a string"/>
```

### Vectors, Positions

点（point）とベクトル（vector）は次のように指定できます。

```xml
<point name="point_property" value="3, 4, 5"/>
<vector name="vector_property" value="3, 4, 5"/>
```

> **Note:**  
> Mitsuba は位置の単位（メートル、センチメートル、インチ等）を特に規定しません。要求されるのは、シーン仕様全体で 1 つの規約を一貫して使用することだけです。

### RGB Colors

Mitsuba では色は `<rgb>` または `<spectrum>` タグで指定します。例えば次の RGB 値

```xml
<rgb name="color_property" value="0.2, 0.8, 0.4"/>
```

の解釈は、現在アクティブなレンダラーのバリアントに依存します。例えば `scalar_rgb` は色値をそのまま下位プラグインへ渡します。一方 `scalar_spectral` はスペクトル領域で動作するため、RGB 値は意味を持ちません。さらに悪いことに、各 RGB 色に対応するスペクトルは無限に存在します。Mitsuba は Jakob と Hanika の手法 `:cite:`Jakob2019Spectral`` を用いて、その中から妥当で滑らかなスペクトルを選択します。例を以下に示します。

![upsampling](https://github.com/mitsuba-renderer/mitsuba-data/blob/a4addd0b991d1a0622db2ac98401fd45d8070e91/docs/images/variants/upsampling.jpg?raw=true)
<!-- width: 100%, align: center -->

<a id="color-spectra"></a>

### Color spectra

色情報をより正確に指定する方法として `<spectrum>` タグがあります。これは **ナノメートル** 単位で指定した複数の離散波長に対する反射率／強度値を記録します。

```xml
<spectrum name="color_property" value="400:0.56, 500:0.18, 600:0.58, 700:0.24"/>
```

得られるスペクトルは、指定波長の間を線形補間し、指定範囲外では 0 になります。次の短縮表記は、波長に対して一様なスペクトルを作成します。

```xml
<spectrum name="color_property" value="0.5"/>
```

スペクトルのパワー分布や反射率分布が測定データ（例: 10nm 刻み）から得られる場合、非常に扱いづらく、シーン記述を煩雑にしがちです。そのため、外部ファイルからスペクトルを読み込んで渡す方法も用意されています。

```xml
<spectrum name="color_property" filename="measured_spectrum.spd"/>         (Text)
<spectrum name="color_property" filename="measured_binary_spectrum.spb"/>  (Binary)
```

ファイルは、各行に 1 つの測定値を持ち、ナノメートル単位の波長と測定値をスペースで区切って記述します。コメントも許可されます。例は次の通りです。

```text
# This file contains a measured spectral power/reflectance distribution
406.13 0.703313
413.88 0.744563
422.03 0.791625
430.62 0.822125
435.09 0.834000
...
```

Mitsuba は、その波長と値を与えることでこの種のファイルを作成する関数（`:py:meth:`mitsuba.spectrum_to_file``）を提供しています。

Mitsuba 3 のスペクトル情報の詳細については、プラグインドキュメント内の `:ref:`該当セクション <sec-spectra>`` を参照してください。

### Transformations

トランスフォーム（変換）は、1 つのタグだけでは表せない唯一のプロパティ種別です。考え方としては、単位変換（identity）から始め、複数のコマンド列で変換を構築します。例えば、平行移動の後に回転を行う変換は次のように書けます。

```xml
<transform name="trafo_property">
    <translate value="-1, 3, 4"/>
    <rotate y="1" angle="45"/>
</transform>
```

数学的には、列の各増分変換は現在の変換に対して左から乗算（left-multiply）されます。利用可能な選択肢は次の通りです。

- 平行移動（Translation）:

  ```xml
  <translate value="-1, 3, 4"/>
  ```

- 指定軸回りの反時計回り回転。角度は度（degrees）で与えます:

  ```xml
  <rotate value="0.701, 0.701, 0" angle="180"/>
  ```

- スケーリング操作。係数は負でもよく、その場合は反転（flip）になります:

  ```xml
  <scale value="5"/>        <!-- 一様スケール -->
  <scale value="2, 1, -1"/> <!-- 非一様スケール -->
  ```

- 明示的な 4x4 行列（row-major 順）:

  ```xml
  <matrix value="0 -0.53 0 -1.79 0.92 0 0 8.03 0 0 0.53 0 0 0 0 1"/>
  ```

- 明示的な 3x3 行列（row-major 順）。内部的には、最後の行と列が単位行列と同じになるよう 4x4 行列へ変換されます。

  ```xml
  <matrix value="0.57 0.2 0 0.1 -1 0 0 0 1"/>
  ```

- `lookat` 変換 — これは主にカメラ設定に便利です。`origin` がカメラ原点、`target` がカメラが注視する点、（任意の）`up` が最終画像における **上方向** を決めます。

  ```xml
  <lookat origin="10, 50, -800" target="0, 0, 0" up="0, 1, 0"/>
  ```

---

## References

多くの場合、マテリアルなどのオブジェクトを複数箇所で使い回したくなります。毎回宣言し直すのはメモリを浪費するため、参照（reference）機能を利用できます。例を示します。

```xml
<scene version="3.0.0">
    <texture type="bitmap" id="my_image">
        <string name="filename" value="textures/my_image.jpg"/>
    </texture>

    <bsdf type="diffuse" id="my_material">
        <!-- my_image というテクスチャを参照し、
             reflectance パラメータとして BSDF に渡す -->
        <ref name="reflectance" id="my_image"/>
    </bsdf>

    <shape type="obj">
        <string name="filename" value="meshes/my_shape.obj"/>

        <!-- my_material というマテリアルを参照 -->
        <ref id="my_material"/>
    </shape>
</scene>
```

オブジェクト宣言時に一意な `id` 属性を与えると、生成時にその識別子へバインドされます。後でその識別子を参照する（`<ref id=".."/>` タグを使う）ことで、そのインスタンスが親オブジェクトに追加されます。

> **Note:**  
> この機能は、複数箇所から参照されるマテリアル、テクスチャ、参加媒質（participating media）を効率的に扱うためのものです。一方で、ジオメトリを生成する用途には使えません。その場合は `:ref:`instance <shape-instance>`` プラグインを使ってください。

<a id="sec-scene-file-format-params"></a>

---

## Default parameters

シーンには、コマンドラインから供給される名前付きパラメータを含められます。

```xml
<bsdf type="diffuse">
    <rgb name="reflectance" value="$reflectance"/>
</bsdf>
```

この場合、`-Dreflectance=...` の形式で明示的なコマンドライン引数を与えずにシーンを読み込むとエラーになります。利便性のため、コマンドライン引数が与えられない場合に優先されるデフォルト値を指定することもできます。その構文は次の通りです。

```xml
<default name="reflectance" value="something"/>
```

そして、このパラメータが XML 内で出現する箇所より前に置かなければなりません。

---

## Including external files

可読性向上のため、シーンを複数ファイルに分割できます。外部ファイルを取り込むには次のコマンドを使います。

```xml
<include filename="nested-scene.xml"/>
```

この場合、`nested-scene.xml` はルートに `<scene>` タグを持つ正しいシーンファイルである必要があります。

この機能は `mitsuba` コマンドラインレンダラーの `-D key=value` フラグと組み合わせると特に便利です。これにより、XML を編集せずにコマンドラインパラメータを変更して、別バリアントのシーン設定を切り替えて include できます。

```xml
<include filename="nested-scene-$version.xml"/>
```

---

## Aliases

オブジェクトを複数の識別子に関連付けたい場合があります。これは `alias as=".."` タグで実現できます。

```xml
<bsdf type="diffuse" id="my_material_1"/>
<alias id="my_material_1" as="my_material_2"/>
```

この記述の後、diffuse 散乱モデルは識別子 `my_material_1` と `my_material_2` の **両方** にバインドされます。

---

## External resource folders

`path` タグを使うと、検索パスのリストにパスを追加できます。これは、メッシュやテクスチャが別ディレクトリに保存されている場合（例えば他のシーンと共有している場合）に便利です。パスが相対パスの場合、Mitsuba 3 はまずシーンディレクトリからの相対として解釈し、次にすでに検索パスに入っている他のパス（例: コマンドライン引数 `-a <path1>;<path2>;..` で追加されたもの）から探します。

```xml
<path value="../../my_resources"/>
```

---

# Dictionary-based scene format

関数 `:py:func:`mitsuba.load_dict`` は、Python の辞書を使って Mitsuba オブジェクトを構築する便利な代替手段を提供します。XML と同じ高レベル構造を表現しつつ、Python のネイティブ型を利用できます。

辞書は常に、生成するプラグイン名を示す `"type"` エントリを含む必要があります。辞書キーは文字列でなければならず、プラグインに渡すプロパティ名を表します。プロパティ型は基底となる Python 型（例: `bool`、`float`、`int`、`str`、…）から自動推論されます。値として辞書を与えると、ネストされたオブジェクトになります。

以下のスニペットは、XML と Python 辞書構造の類似性を示します。また同様に、`:ref:`プラグインドキュメント <sec-plugins>`` では、参照されるすべてのプラグインについて XML スニペットと対応する Python `dict` 例の両方が提供されています。

## 対応例

### XML

```xml
<shape type="obj">
    <string name="filename" value="dragon.obj"/>
    <bsdf type="roughconductor">
        <float name="alpha" value="0.01"/>
    </bsdf>
</shape>
```

### Python

```python
{
    "type": "obj",
    "filename": "dragon.obj",
    "bsdf_id": {
        "type": "roughconductor",
        "alpha": 0.01
    }
}
```

以下は `:py:func:`mitsuba.load_dict`` の具体的な使い方の例です。

```python
sphere = mi.load_dict({
    "type": "sphere",
    "center": [0, 0, -10],
    "radius": 10.0,
    "flip_normals": False,
    "bsdf": {
        "type": "dielectric"
    }
})
```

また、この関数を複数回呼び出し、辞書をネストする代わりに、事前に構築したオブジェクトを渡すこともできます。

```python
# まず BSDF を作成（xml.load_string(..) でも可）
my_bsdf = mi.load_dict({
    "type": "roughconductor",
    "alpha": 0.14,
})

# 辞書内に BSDF オブジェクトを渡す
sphere = load_dict({
    "type": "sphere",
    "something": my_bsdf
})
```

---

## Color/spectra

利便性のため、`"type"` エントリが `"rgb"` または `"spectrum"` のネスト辞書を渡せます。XML パーサと同様に、その辞書の `"value"` エントリが適切な `Spectrum` プラグインを生成するために使用されます。（`:ref:`該当セクション <sec-spectra>`` を参照）

以下は、ネスト辞書における `"value"` の使い方の例です。

```python
# グレースケール値を渡す
"color_property": {
    "type": "rgb",
    "value": 0.44
}

# 三刺激値（tristimulus）を渡す
"color_property": {
    "type": "rgb",
    "value": [0.7, 0.1, 0.5]
}

# スペクトルファイルを指定
"color_property": {
    "type": "spectrum",
    "filename": "filename.spd"
}

# (波長, 値) のペアのリストを指定
"color_property": {
    "type": "spectrum",
    "value": [(400.0, 0.5), (500.0, 0.8), (600.0, 0.2)]
}
```

次の例は `:py:func:`mitsuba.load_dict`` を使って Mitsuba の完全なシーンを構築します。

```python
scene = mi.load_dict({
    "type": "scene",
    "myintegrator": {
        "type": "path",
    },
    "mysensor": {
        "type": "perspective",
        "near_clip": 1.0,
        "far_clip": 1000.0,
        "to_world": mi.ScalarTransform4f.look_at(origin=[1, 1, 1],
                                                 target=[0, 0, 0],
                                                 up=[0, 0, 1]),
        "myfilm": {
            "type": "hdrfilm",
            "rfilter": {
                "type": "box"
            },
            "width": 1024,
            "height": 768,
        }, "mysampler": {
            "type": "independent",
            "sample_count": 4,
        },
    },
    "myemitter": {
        "type": "constant"
    },
    "myshape": {
        "type": "sphere",
        "mybsdf": {
            "type": "diffuse",
            "reflectance": {
                "type": "rgb",
                "value": [0.8, 0.1, 0.1],
            }
        }
    }
})
```

---

## References（辞書形式）

XML パーサと同様に、シーンオブジェクトを一度宣言し、別の箇所で参照できます。

```python
{
    "type": "scene",

    "shape_1": {
        "type": "obj",
        "filename": "shape_1.obj",
        "bsdf": {
            "type": "diffuse",
            "id": "my_material"
        }
    },

    "shape_2": {
        "type": "sphere",
        "filename": "shape_2.obj",

        # shape 1 のマテリアルを再利用
        "bsdf": {
            "type": "ref",
            "id": "my_material"  # 明示的 ID 参照
        }
    }
}
```

辞書パーサ固有の機能として、辞書内のすべてのオブジェクトは「辞書内のパス（そこへ到達するためのキー列）」に基づく暗黙的 ID を自動的に受け取ります。ただし、以前宣言したオブジェクトを参照したい場合は、明示的 ID を使う必要があります。

例えば次のスニペットでは、各オブジェクトは次の暗黙的 ID を受け取ります。

- shape: `my_shape`
- material: `my_shape.my_material`
- texture: `my_shape.my_material.reflectance`

```python
{
    "type": "scene",
    "my_shape": {
        "type": "sphere",
        "my_material": {
            "type": "diffuse",
            "reflectance": {
                "type": "bitmap",
                "filename": "texture.jpg"
            }
        }
    }
}
```

**重要な注意点**:

- 辞書キーにドット（`.`）を含めることはできません。ドットはパスの区切り文字として予約されています。代わりにアンダースコアを使用してください。
- オブジェクトは、宣言の前後どちらでも参照できます。前方参照（forward references）も完全にサポートされています。

---

## Search paths

XML のシーン記述と同様に、検索パスのリストにパスを追加できます。次の例では、テクスチャファイルが `/home/username/data/textures/` フォルダ内にあるとします。追加するパスは相対でも絶対でも構いません。

```python
{
    "type": "scene",
    'foo': { 'type': 'resources', 'path': '/home/username/data/textures'},
    "bsdf": {
        "type": "diffuse",
        "reflectance": {
            "type": "bitmap",
            "filename": "my_texture.exr", # 上で定義したフォルダからの相対
        }
    }
}
```
