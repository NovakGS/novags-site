import sys, io, os, glob, pikepdf, zipfile
sys.path.insert(0, '/home/claude/scripts')
from clipmask import clip_image
from PIL import Image
OUT = '/home/claude/out/'
# Property Overview PDF
pdf = pikepdf.open('/home/claude/dl/orig/property_overview.pdf')
for objnum, deer in ((5, False), (7, False), (8, True)):
    obj = pdf.get_object((objnum, 0))
    pim = pikepdf.PdfImage(obj).as_pil_image()
    w, h = pim.size
    out = clip_image(pim, w/3600.0, (255,255,255), deer=deer)
    buf = io.BytesIO(); out.save(buf, 'JPEG', quality=90, optimize=True)
    obj.write(buf.getvalue(), filter=pikepdf.Name.DCTDecode)
    obj.ColorSpace = pikepdf.Name.DeviceRGB; obj.BitsPerComponent = 8
    out.save(OUT + 'po_%d.png' % objnum)
    print('PO', objnum, w, h, len(buf.getvalue()))
pdf.save(OUT + 'property_overview.pdf')
# Listing Graphics
os.makedirs(OUT + 'lg', exist_ok=True)
for f in sorted(glob.glob('/home/claude/dl/lg/*.jpg')):
    im = Image.open(f)
    w, h = im.size
    out = clip_image(im, w/3600.0, (9,12,17), map_h=round(2964*w/3600.0), deer='Thermal' in f)
    out.save(OUT + 'lg/' + os.path.basename(f), 'JPEG', quality=92, optimize=True)
    print('LG', os.path.basename(f), os.path.getsize(f), os.path.getsize(OUT + 'lg/' + os.path.basename(f)))
