import sys, zipfile, io, math, re
from lxml import etree
from PIL import Image, ImageDraw
Image.MAX_IMAGE_PIXELS=None
K='{http://www.opengis.net/kml/2.2}'
def render(kmz, out, overlay_filter=None, width=1400, pad=0.12, vectors=True, bbox=None):
    z=zipfile.ZipFile(kmz)
    root=etree.fromstring(z.read('doc.kml'), etree.XMLParser(huge_tree=True))
    W0,E0,S0,N0 = bbox or (-89.6273946,-89.6223568,43.1090316,43.1120673)
    dx=(E0-W0)*pad; dy=(N0-S0)*pad; W0-=dx;E0+=dx;S0-=dy;N0+=dy
    k=math.cos(math.radians(43.11))
    H=int(width*(N0-S0)/((E0-W0)*k))
    can=Image.new('RGBA',(width,H),(200,60,200,255))
    def P(lon,lat): return ((lon-W0)/(E0-W0)*width,(N0-lat)/(N0-S0)*H)
    gos=sorted(root.iter(K+'GroundOverlay'), key=lambda g:int(g.findtext(K+'drawOrder') or 0))
    for g in gos:
        nm=g.findtext(K+'name')
        if overlay_filter and overlay_filter not in nm: continue
        b=g.find(K+'LatLonBox'); n,s,e,w=[float(b.findtext(K+t)) for t in ('north','south','east','west')]
        im=Image.open(io.BytesIO(z.read(g.find(K+'Icon/'+K+'href').text))).convert('RGBA')
        x0,y0=P(w,n); x1,y1=P(e,s)
        im=im.resize((max(1,round(x1-x0)),max(1,round(y1-y0))))
        can.alpha_composite(im,(round(x0),round(y0)))
    d=ImageDraw.Draw(can)
    if vectors:
        for pm in root.iter(K+'Placemark'):
            for ls in pm.iter(K+'LineString'):
                pts=[P(*map(float,c.split(',')[:2])) for c in ls.findtext(K+'coordinates').split()]
                d.line(pts,fill=(255,255,0,255),width=1)
            for pg in pm.iter(K+'Polygon'):
                pts=[P(*map(float,c.split(',')[:2])) for c in pg.find('.//'+K+'coordinates').text.split()]
                d.line(pts,fill=(0,255,255,255),width=1)
            for pt in pm.iter(K+'Point'):
                x,y=P(*map(float,pt.findtext(K+'coordinates').split(',')[:2])); d.ellipse((x-3,y-3,x+3,y+3),outline=(255,255,255,255))
    can.convert('RGB').save(out)
if __name__=='__main__':
    render(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv)>3 and sys.argv[3]!='-' else None, vectors=(len(sys.argv)<=4))
