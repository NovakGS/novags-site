import sys, pikepdf
from PIL import Image
LI = '/home/claude/novags-site/hamele/li-img/'
ORIG = '/home/claude/dl/orig/'
OUT = '/home/claude/out/'
plan = {
 'essentials_report': {6:'map_overview', 8:'map_water', 10:'map_soils'},
 'dd_report': {6:'map_zoning', 10:'map_build', 12:'map_ponds'},
 'steward_report': {6:'map_steward'},
}
for name, repl in plan.items():
    pdf = pikepdf.open(ORIG + name + '.pdf')
    for objnum, img in repl.items():
        obj = pdf.get_object((objnum, 0))
        assert obj.get('/Subtype') == '/Image', (name, objnum)
        w, h = int(obj.Width), int(obj.Height)
        im = Image.open(LI + img + '.jpg')
        assert im.size == (w, h) and im.mode == 'RGB', (img, im.size, im.mode)
        data = open(LI + img + '.jpg', 'rb').read()
        obj.write(data, filter=pikepdf.Name.DCTDecode)
        obj.ColorSpace = pikepdf.Name.DeviceRGB
        obj.BitsPerComponent = 8
        print(name, objnum, '->', img, len(data))
    pdf.save(OUT + name + '.pdf')
