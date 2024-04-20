# Scene XML file format

Mitsubaは、シンプルで一般的なXMLベースの形式を使用してシーンを表現します。

照明のない単一のメッシュとデフォルトのカメラ設定を持つシンプルなシーンは、次のようになります
```xml
<scene version="3.0.0">
    <shape type="obj">
        <string name="filename" value="dragon.obj"/>
    </shape>
</scene>
```
1行目の`version`属性は、シーンを作成するために使用されたMitsubaのリリースを示しています。この情報により、Mitsubaは将来的なシーン記述言語の変更に関係なくファイルを正しく処理できます。

この例にはすでに、フォーマットについて知っておくべき最も重要な要素が含まれています。それは、オブジェクト（`<scene>`タグや`<shape>`タグでインスタンス化されるオブジェクトなど）で構成され、さらに互いにネストできることです。各オブジェクトはオプションでプロパティ（`<string>`タグなど）を受け入れ、その動作を特徴付けます。ルートオブジェクト（`<scene>`）以外のすべてのオブジェクトは、レンダラーがディスクからプラグインを検索してロードするため、`type="…"`パラメータを使用してプラグイン名を指定する必要があります。

またオブジェクトタグは、レンダラーにどの種類のオブジェクトをインスタンス化するかを知らせます：たとえば、`<shape>`タグを使用してロードされたプラグインは、*Shape*インターフェースに準拠する必要があります。この場合、プラグインの名前は`obj`（Wavefront OBJローダーを含む）です。同様に、次のように書くこともできます：
```xml
<scene version="3.0.0">
    <shape type="sphere">
        <float name="radius" value="10"/>
    </shape>
</scene>
```
これは別のプラグイン（`sphere`）をロードします。*Shape*であることに変わりはないですが、代わりに半径10のワールド空間単位で構成された[sphere](https://mitsuba.readthedocs.io/en/latest/src/generated/plugins_shapes.html#shape-sphere)を表します。プラグインの詳細については、[Plugin reference](https://mitsuba.readthedocs.io/en/latest/src/plugin_reference.html#sec-plugins)を参照してください。

一般的なシーンのセットアップは、インテグレータ、いくつかのジオメトリ、センサー（例：カメラ）、フィルム、サンプラー、および1つ以上のエミッタを宣言することが一般的です。以下はもう少し複雑な例です：
```xml
<scene version="3.0.0">
    <integrator type="path">
        <!-- Instantiate a path tracer with a max. path length of 8 -->
        <integer name="max_depth" value="8"/>
    </integrator>

    <!-- Instantiate a perspective camera with 45 degrees field of view -->
    <sensor type="perspective">
        <!-- Rotate the camera around the Y axis by 180 degrees -->
        <transform name="to_world">
            <rotate y="1" angle="180"/>
        </transform>
        <float name="fov" value="45"/>

        <!-- Render with 32 samples per pixel using a basic
             independent sampling strategy -->
        <sampler type="independent">
            <integer name="sample_count" value="32"/>
        </sampler>

        <!-- Generate an EXR image at HD resolution -->
        <film type="hdrfilm">
            <integer name="width" value="1920"/>
            <integer name="height" value="1080"/>
        </film>
    </sensor>

    <!-- Add a dragon mesh made of rough glass (stored as OBJ file) -->
    <shape type="obj">
        <string name="filename" value="dragon.obj"/>

        <bsdf type="roughdielectric">
            <!-- Tweak the roughness parameter of the material -->
            <float name="alpha" value="0.01"/>
        </bsdf>
    </shape>

    <!-- Add another mesh, this time, stored using Mitsuba's own
         (compact) binary representation -->
    <shape type="serialized">
        <string name="filename" value="lightsource.serialized"/>
        <transform name="toWorld">
            <translate x="5" y="-3" z="1"/>
        </transform>

        <!-- This mesh is an area emitter -->
        <emitter type="area">
            <rgb name="radiance" value="100,400,100"/>
        </emitter>
    </shape>
</scene>
```
この例では、いくつかの新しいオブジェクトタイプ（`integrator`、`sensor`、`bsdf`、`sampler`、`film`、`emitter`）とプロパティタイプ（`integer`、`transform`、`rgb`）が導入されています。例で見るように、オブジェクトは通常、トップレベルで宣言されますが、他のオブジェクトと固有の関連がある場合を除いては、それが子オブジェクトとして表示されます。たとえば、BSDFは通常特定のジオメトリオブジェクトに固有であるため、shapeの子オブジェクトとして表示されます。同様に、サンプラーとフィルムは、センサーから生成される光線の方法と、それが記録する結果の輝度サンプルに影響を与えるため、それらはセンサーの内部にネストされています。以下の表は、利用可能なオブジェクトタイプの概要を提供します：

|**XML tag**|**Description**|**`type` exmaple**|
|--|--|--|
|`bsdf`|BSDF describe the manner in which light interacts with surfaces in the scene (i.e., the material)|`diffuse`, `conductor`|
|`emitter`|Emitter plugins specify light sources and their characteristic emission profiles.|`constant`, `envmap`, `point`|
|`film`|Film plugins convert measurements into the final output file that is written to disk|`hdrfilm`, `specfilm`|
|`integrator`|Integrators implement rendering techniques for solving the light transport equation|`path`, `direct`, `depth`|
|`rfilter`|Reconstruction filters control how the `film` converts a set of samples into the output image|`box`, `gaussian`|
|`sampler`|Sample generator plugins used by the `integrator`|`independent`, `multijitter`|
|`sensor`|Sensor plugins like cameras are responsible for measuring radiance|`perspective`, `orthogonal`|
|`shape`|Shape puglins define surfaces that mark transitions between different types of materials|`obj`, `ply`, `serialized`|
|`texture`|Texture plugins represent spatially varying signals on surfaces|`bitmap`, `checkerboard`|


## Properties

このサブセクションでは、オブジェクトにプロパティを指定する方法について説明します。あるプラグインがどのプロパティを受け付けるかを知りたい場合は、[プラグインのドキュメント](https://mitsuba.readthedocs.io/en/latest/src/plugin_reference.html#sec-plugins)を参照してください。

### Numbers

整数値と浮動小数点値は、以下のように渡すことができます：
```xml
<integer name="int_property" value="1234"/>
<float name="float_property" value="-1.5e3"/>
```
オブジェクトが受け付けるフォーマットに従わなければならないことに注意してください、つまり、整数プロパティを浮動小数点プロパティとして受け付けるオブジェクトに渡すことはできません。

### Booleans

ブール値は次のように渡すことができます:
```xml
<boolean name="bool_property" value="true"/>
```

### Strings

文字列の渡し方も同様に簡単です:
```xml
<string name="string_property" value="This is a string"/>
```

### Vectors, Positions

点やベクトルは次のように指定できます:
```xml
<point name="point_property" value="3, 4, 5"/>
<vector name="vector_property" value="3, 4, 5"/>
```

### RGB Colors

Mitsubaでは、色は`<rgb>`または`<spectrum>`タグを使用して指定します。RGBカラー値の解釈は、現在アクティブなレンダラーのバリアントに依存します。
```xml
<rgb name="color_property" value="0.2, 0.8, 0.4"/>
```
たとえば、`scalar_rgb`は色値を変更せずに基になるプラグインに転送します。一方、`scalar_spectral`は、RGB値が意味を持たないスペクトルドメインで動作します。悪いことに、各RGBカラーに対応するスペクトルは無限に存在します。Mitsubaは、[JakobとHanikaの方法](https://mitsuba.readthedocs.io/en/latest/zz_bibliography.html#id9)を使用して、これらの可能性のある中からもっともらしい滑らかなスペクトルを選択します。以下に例を示します:
![](https://mitsuba.readthedocs.io/en/latest/_images/upsampling.jpg)

### Color spectra

色情報をより正確に指定する方法として、`<spectrum>`タグを使用します。このタグは、ナノメートル単位で指定された複数の離散的な波長の反射率/強度値を記録します。
```xml
<spectrum name="color_property" value="400:0.56, 500:0.18, 600:0.58, 700:0.24"/>
```
結果のスペクトルは、中間の波長に対して線形補間を行い、指定された波長範囲外ではゼロになります。次の短縮記法は、波長全体で均一なスペクトルを作成します:
```xml
<spectrum name="color_property" value="0.5"/>
```
測定値からスペクトルパワーや反射率分布を取得する場合（たとえば10nmの間隔で）、それらは通常非常に扱いにくく、シーンの記述を乱雑にさせることがあります。そのため、外部ファイルからスペクトルを読み込む方法があります:
```xml
<spectrum name="color_property" filename="measured_spectrum.spd"/>         (Text)
<spectrum name="color_property" filename="measured_binary_spectrum.spb"/>  (Binary)
```
ファイルには、1行ごとに1つの測定値が含まれており、対応する波長（ナノメートル単位）と測定値がスペースで区切られています。コメントも許可されています。以下に例を示します:
```xml
# This file contains a measured spectral power/reflectance distribution
406.13 0.703313
413.88 0.744563
422.03 0.791625
430.62 0.822125
435.09 0.834000
...
```
Mitsubaには、指定された波長とその値を使用してこのようなファイルを作成するための関数（[mitsuba.spectrum_to_file()](https://mitsuba.readthedocs.io/en/latest/src/api_reference.html#mitsuba.spectrum_to_file)）が用意されています。
Mitsuba 3のスペクトル情報の詳細については、プラグインのドキュメントの[対応するセクション](https://mitsuba.readthedocs.io/en/latest/src/generated/plugins_spectra.html#sec-spectra)をご覧ください。

### Transformations

Transformationsは、単一以上のタグを必要とする唯一のプロパティです。アイデアは、単位から始めて、一連のコマンドを使用して変換を構築できるというものです。たとえば、平行移動に続いて回転を行う変換は、次のように記述できます:
```xml
<transform name="trafo_property">
    <translate value="-1, 3, 4"/>
    <rotate y="1" angle="45"/>
</transform>
```
数学的には、シーケンス内の各増分変換は現在の変換に左から乗算されます。以下の選択肢があります:
* 変換:
  ```xml
  <translate value="-1, 3, 4"/>
  ```
* 指定された軸を中心とした反時計回りの回転。角度は度単位で指定する:
  ```xml
  <rotate value="0.701, 0.701, 0" angle="180"/>
  ```
* スケーリング操作。フリップを得るために係数を負にすることもできる:
  ```xml
  <scale value="5"/>        <!-- uniform scale -->
  <scale value="2, 1, -1"/> <!-- non-uniform scale -->
  ```
* 明示的な4x4行列:
  ```xml
  <matrix value="0 -0.53 0 -1.79 0.92 0 0 8.03 0 0 0.53 0 0 0 0 1"/>
  ```
* 明示的な3x3行列（行優先順序）。内部的には、これは同じ最後の行と列を持つ4x4行列に変換されます。
  ```xml
  <matrix value="0.57 0.2 0 0.1 -1 0 0 0 1"/>
  ```
* `lookat`変換 - これは主にカメラの設定に役立ちます。`origin`座標はカメラの原点を指定し、`target`はカメラが見る点を指定し、（オプションの）`up`パラメータは最終的にレンダリングされる画像の上方向を決定します。
  ```xml
  <lookat origin="10, 50, -800" target="0, 0, 0" up="0, 1, 0"/>
  ```
