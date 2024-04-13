import mitsuba as mi

mi.set_variant('scalar_rgb')

scene = mi.load_dict(mi.cornell_box())

image = mi.render(scene, spp=128)

mi.util.write_bitmap('cbox.png', mi.Bitmap(image))