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
