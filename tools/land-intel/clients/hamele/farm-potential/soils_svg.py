"""Soils-by-productivity SVG for the Travis page coming-soon section (no aerial, no coordinates).
Planar local projection; slivers thinner than ~12 m opened out so the outline reads cleanly."""
import json, math, sys
from shapely.geometry import shape
from shapely.ops import unary_union, transform
soils_p, out_p = sys.argv[1:3]
feats = json.load(open(soils_p))['features']
BINS = [(0.40, "#C2583F"), (0.50, "#E3994A"), (0.65, "#EDCF62"), (0.80, "#A2C766"), (9.99, "#4F9A4C")]
NR = "#AEB8C1"
def color(v):
    if v is None: return NR
    for t, c in BINS:
        if v <= t: return c
g0 = [shape(f['geometry']).buffer(0) for f in feats]
c = unary_union(g0).centroid
lon0, lat0 = c.x, c.y
k = math.cos(math.radians(lat0))
def proj(x, y, z=None): return ((x - lon0) * k * 111320.0, -(y - lat0) * 110574.0)
G = [transform(proj, g) for g in g0]
D = 6.0
farm = unary_union(G).buffer(0.01).buffer(-0.01).buffer(-D, join_style=2).buffer(D, join_style=2)
soils = []
for f, g in zip(feats, G):
    h = g.intersection(farm)
    if not h.is_empty and h.area > 1: soils.append((f['properties'], h))
minx, miny, maxx, maxy = farm.bounds
W = 1000; pad = 26
s = (W - 2 * pad) / (maxx - minx); H = round((maxy - miny) * s + 2 * pad)
def polys(g):
    if g.geom_type == 'Polygon': return [g]
    return [p for p in getattr(g, 'geoms', []) if p.geom_type == 'Polygon']
def path(g):
    d = []
    for p in polys(g):
        for r in [p.exterior] + list(p.interiors):
            q = [((x - minx) * s + pad, (y - miny) * s + pad) for x, y in r.coords]
            q = [a for i, a in enumerate(q) if i == 0 or abs(a[0] - q[i-1][0]) + abs(a[1] - q[i-1][1]) > 0.3]
            d.append('M' + ' L'.join('{:.1f} {:.1f}'.format(*a) for a in q) + ' Z')
    return ' '.join(d)
o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {} {}" width="{}" height="{}">'.format(W, H, W, H)]
for pr, h in sorted(soils, key=lambda t: -t[1].area):
    o.append('<path d="{}" fill="{}" fill-rule="evenodd" stroke="#ffffff" stroke-width="2.2" stroke-linejoin="round"/>'.format(path(h), color(pr.get('index'))))
o.append('<path d="{}" fill="none" stroke="#e8711a" stroke-width="7" stroke-linejoin="round"/>'.format(path(farm)))
o.append('</svg>')
open(out_p, 'w').write('\n'.join(o))
print(W, H, round(farm.area / 4046.8564224, 1), 'ac')
