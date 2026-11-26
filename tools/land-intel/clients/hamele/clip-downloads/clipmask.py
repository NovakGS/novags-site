import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Polygon
BND = [(3540.8,2863.7),(3513.3,103.6),(65.0,43.2),(52.5,2912.4)]
OUT_DEER = [(874.2,2942.3),(3556.5,712.7),(3525.2,550.2)]  # frame units, outside the boundary
def alpha_mask(w, h, s, buf=8.0, ss=4):
    P = Polygon([(x*s, y*s) for x, y in BND]).buffer(buf*s, join_style=2)
    big = Image.new('L', (w*ss, h*ss), 0)
    ImageDraw.Draw(big).polygon([(x*ss, y*ss) for x, y in P.exterior.coords], fill=255)
    return np.asarray(big.resize((w, h), Image.BOX)).astype(np.float32)/255.0
def ring_alpha(w, h, s, src=None):
    # restore only the drawn deer ring (white band plus its dark outline) around deer outside the boundary
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = np.zeros((h, w), np.float32)
    arr = np.asarray(src.convert('RGB')).astype(np.float32)[:h]
    L = arr.mean(-1); sat = arr.max(-1)-arr.min(-1)
    white = (L > 200) & (sat < 45)
    r0, r1 = 22.3*s, 29.0*s
    outline = max(1.0, 2.0*s/0.6667)
    for X, Y in OUT_DEER:
        best = None
        for dx in np.arange(-3, 3.01, 0.25):
            for dy in np.arange(-3, 3.01, 0.25):
                cx, cy = X*s+dx, Y*s+dy
                x0, x1 = int(max(0, cx-r1-3)), int(min(w, cx+r1+4)); y0, y1 = int(max(0, cy-r1-3)), int(min(h, cy+r1+4))
                d = np.hypot(xx[y0:y1, x0:x1]+0.5-cx, yy[y0:y1, x0:x1]+0.5-cy)
                band = (d >= r0) & (d <= r1)
                sc = (white[y0:y1, x0:x1] & band).sum() / max(1, band.sum())
                if best is None or sc > best[0]: best = (sc, cx, cy, dx, dy)
        sc, cx, cy, dx, dy = best
        d = np.hypot(xx+0.5-cx, yy+0.5-cy)
        a = np.maximum(a, np.clip(np.minimum(d-(r0+0.4), (r1+outline+0.5)-d)+0.5, 0, 1))
        print('ring', (X, Y), 'offset', dx, dy, 'white share', round(float(sc), 2))
    return a
def clip_image(im, s, fill, map_h=None, deer=False):
    im = im.convert('RGB')
    w, h = im.size
    mh = map_h or h
    a = alpha_mask(w, mh, s)
    if deer:
        a = np.maximum(a, ring_alpha(w, mh, s, im))
    arr = np.asarray(im).astype(np.float32)
    top = arr[:mh]
    f = np.array(fill, np.float32)
    arr[:mh] = top*a[..., None] + f*(1-a[..., None])
    return Image.fromarray(np.clip(arr+0.5, 0, 255).astype(np.uint8))
