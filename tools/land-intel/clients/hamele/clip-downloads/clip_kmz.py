import sys, os, io, math, copy, zipfile, shutil
sys.path.insert(0, '/home/claude/scripts')
import numpy as np
from lxml import etree
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, LineString, Point, MultiPolygon, MultiLineString, GeometryCollection
from shapely.ops import unary_union
Image.MAX_IMAGE_PIXELS = None
NS = 'http://www.opengis.net/kml/2.2'
K = '{%s}' % NS
BND = [(-89.6223568,43.1090920),(-89.6224062,43.1120121),(-89.6273866,43.1120673),(-89.6273946,43.1090316)]
BPOLY = Polygon(BND)
C0 = (-89.6249, 43.1105)

def el(tag, text=None, **kw):
    e = etree.Element(K + tag)
    if text is not None: e.text = text
    return e

def km_from_prop(x, y):
    return math.hypot((x-C0[0])*81.2, (y-C0[1])*111.1)

# ---------- overlays ----------
def tile_overlay(go, kmzdir, outfiles, draw_base, swap_fix):
    name = go.findtext(K+'name'); vis = go.findtext(K+'visibility')
    href = go.find(K+'Icon/'+K+'href').text
    box = go.find(K+'LatLonBox')
    n, s, e, w = [float(box.findtext(K+t)) for t in ('north','south','east','west')]
    if swap_fix and (abs(s) > 90 or abs(e) < 90):
        # the tool wrote south/east swapped with lon/lat: north=lat_n, south=lon_e, east=lat_s, west=lon_w
        n, s, e, w = n, e, s, w
    im = Image.open(os.path.join(kmzdir, href)); im.load()
    W, H = im.size
    def px(lon, lat): return ((lon-w)/(e-w)*W, (n-lat)/(n-s)*H)
    P = [px(*c) for c in BND]
    xs = [p[0] for p in P]; ys = [p[1] for p in P]
    cx0, cy0 = max(0, int(math.floor(min(xs)))-3), max(0, int(math.floor(min(ys)))-3)
    cx1, cy1 = min(W, int(math.ceil(max(xs)))+3), min(H, int(math.ceil(max(ys)))+3)
    im = im.crop((cx0, cy0, cx1, cy1)); W2, H2 = im.size
    P2 = [(x-cx0, y-cy0) for x, y in P]
    def ll(x, y):  # crop pixel -> lon/lat
        return (w + (x+cx0)/W*(e-w), n - (y+cy0)/H*(n-s))
    # alpha mask, polygon grown by 1 px so the vector boundary line sits on imagery
    ss = 4
    poly = Polygon(P2).buffer(1.0, join_style=2)
    big = Image.new('L', (W2*ss, H2*ss), 0)
    ImageDraw.Draw(big).polygon([(x*ss, y*ss) for x, y in poly.exterior.coords], fill=255)
    alpha = big.resize((W2, H2), Image.BOX)
    base = os.path.splitext(os.path.basename(href))[0]
    pieces = []
    if im.mode in ('RGBA', 'LA', 'P') or href.lower().endswith('.png'):
        # already a PNG: one overlay, alpha outside the parcel
        rgba = im.convert('RGBA')
        a0 = np.asarray(rgba)[..., 3].astype(np.uint16)
        a = (a0 * np.asarray(alpha).astype(np.uint16) // 255).astype(np.uint8)
        arr = np.asarray(rgba).copy(); arr[..., 3] = a
        fn = 'files/%s.png' % base
        Image.fromarray(arr, 'RGBA').save(os.path.join(outfiles, os.path.basename(fn)), optimize=True)
        pieces.append((fn, (0, 0, W2, H2), draw_base))
    else:
        mode = 'L' if im.mode == 'L' else 'RGB'
        im = im.convert(mode)
        x0 = int(math.ceil(max(P2[2][0], P2[3][0]))) + 3   # TL, BL (BND order: BR, TR, TL, BL)
        x1 = int(math.floor(min(P2[0][0], P2[1][0]))) - 3
        y0 = int(math.ceil(max(P2[1][1], P2[2][1]))) + 3
        y1 = int(math.floor(min(P2[0][1], P2[3][1]))) - 3
        a = np.asarray(alpha)
        assert a[y0:y1, x0:x1].min() == 255, 'inner rect not fully inside'
        fn = 'files/%s.jpg' % base
        im.crop((x0, y0, x1, y1)).save(os.path.join(outfiles, os.path.basename(fn)), 'JPEG', quality=90, optimize=True)
        pieces.append((fn, (x0, y0, x1, y1), draw_base))
        ov = 6
        strips = {'top': (0, 0, W2, y0+ov), 'bottom': (0, y1-ov, W2, H2),
                  'left': (0, y0, x0+ov, y1), 'right': (x1-ov, y0, W2, y1)}
        rgba = im.convert('RGBA'); rgba.putalpha(alpha)
        for k, b in strips.items():
            fn = 'files/%s_%s.png' % (base, k)
            rgba.crop(b).save(os.path.join(outfiles, os.path.basename(fn)), optimize=True)
            pieces.append((fn, b, draw_base+1))
    folder = el('Folder'); folder.append(el('name', name))
    if vis is not None: folder.append(el('visibility', vis))
    st = el('Style'); ls = el('ListStyle'); ls.append(el('listItemType', 'checkHideChildren')); st.append(ls); folder.append(st)
    for fn, (bx0, by0, bx1, by1), dord in pieces:
        g = el('GroundOverlay'); g.append(el('name', name))
        if vis is not None: g.append(el('visibility', vis))
        g.append(el('drawOrder', str(dord)))
        ic = el('Icon'); ic.append(el('href', fn)); g.append(ic)
        lb = el('LatLonBox')
        wl, nl = ll(bx0, by0); el_, sl = ll(bx1, by1)
        for t, v in (('north', nl), ('south', sl), ('east', el_), ('west', wl)):
            lb.append(el(t, '%.9f' % v))
        g.append(lb); folder.append(g)
    go.getparent().replace(go, folder)
    return [p[0] for p in pieces]

# ---------- vectors ----------
def parse_coords(t):
    pts = []
    for c in t.split():
        v = c.split(',')
        pts.append((float(v[0]), float(v[1])))
    return pts
def fmt(coords):
    return ' '.join('%.7f,%.7f,0' % (x, y) for x, y in coords)
def geom_of(pm):
    g = []
    for poly in pm.iter(K+'Polygon'):
        outer = parse_coords(poly.find('.//'+K+'outerBoundaryIs//'+K+'coordinates').text)
        holes = [parse_coords(h.text) for h in poly.findall('.//'+K+'innerBoundaryIs//'+K+'coordinates')]
        g.append(('poly', Polygon(outer, holes).buffer(0)))
    for ls in pm.iter(K+'LineString'):
        g.append(('line', LineString(parse_coords(ls.find(K+'coordinates').text))))
    return g
def parts(geom, kind):
    if geom.is_empty: return []
    if isinstance(geom, (Polygon, LineString)): gs = [geom]
    else: gs = list(getattr(geom, 'geoms', []))
    out = []
    for g in gs:
        if kind == 'poly' and isinstance(g, Polygon) and g.area > 1e-12: out.append(g)
        if kind == 'line' and isinstance(g, LineString) and g.length > 1e-9: out.append(g)
        if isinstance(g, (MultiPolygon, MultiLineString, GeometryCollection)): out += parts(g, kind)
    return out
def kml_geom(polys, lines):
    items = []
    for p in polys:
        e = el('Polygon'); ob = el('outerBoundaryIs'); lr = el('LinearRing'); lr.append(el('coordinates', fmt(p.exterior.coords))); ob.append(lr); e.append(ob)
        for h in p.interiors:
            ib = el('innerBoundaryIs'); lr = el('LinearRing'); lr.append(el('coordinates', fmt(h.coords))); ib.append(lr); e.append(ib)
        items.append(e)
    for l in lines:
        e = el('LineString'); e.append(el('tessellate', '1')); e.append(el('coordinates', fmt(l.coords))); items.append(e)
    if len(items) == 1: return items[0]
    mg = el('MultiGeometry')
    for i in items: mg.append(i)
    return mg
def clip_placemark(pm, as_lines=False):
    gs = geom_of(pm)
    if not gs: return True  # points etc. kept
    polys, lines = [], []
    for kind, g in gs:
        if kind == 'poly' and as_lines:
            lines += parts(g.boundary.intersection(BPOLY.buffer(-0.000004)), 'line')  # drop parcel lines that run along the boundary itself
        elif kind == 'poly':
            polys += parts(g.intersection(BPOLY), 'poly')
        else:
            lines += parts(g.intersection(BPOLY), 'line')
    for tag in ('Polygon', 'LineString', 'MultiGeometry'):
        for old in pm.findall(K+tag): pm.remove(old)
    if not polys and not lines: return False
    pm.append(kml_geom(polys, lines))
    return True
def trim_far_rings(pm, km=5.5):
    gs = []
    for poly in list(pm.iter(K+'Polygon')):
        pts = parse_coords(poly.find('.//'+K+'outerBoundaryIs//'+K+'coordinates').text)
        if min(km_from_prop(x, y) for x, y in pts) > km:
            poly.getparent().remove(poly)
    return any(True for _ in pm.iter(K+'Polygon'))

def build(name, kmzdir, out_kmz, clip_folders, line_folders=(), trim_folders=(), swap_fix=False):
    parser = etree.XMLParser(strip_cdata=False, remove_blank_text=False, huge_tree=True)
    tree = etree.parse(os.path.join(kmzdir, 'doc.kml'), parser)
    root = tree.getroot()
    work = '/home/claude/out/kmz_' + name
    shutil.rmtree(work, ignore_errors=True); os.makedirs(work + '/files')
    hrefs = []
    gos = list(root.iter(K+'GroundOverlay'))
    order = {}
    for i, go in enumerate(gos):
        hrefs += tile_overlay(go, kmzdir, work + '/files', 2*i, swap_fix)
    report = {}
    for f in root.iter(K+'Folder'):
        fname = f.findtext(K+'name') or ''
        key = next((c for c in list(clip_folders)+list(line_folders)+list(trim_folders) if fname.startswith(c)), None)
        if not key: continue
        before = len(f.findall(K+'Placemark')); dropped = 0
        for pm in f.findall(K+'Placemark'):
            if key in trim_folders: keep = trim_far_rings(pm)
            else: keep = clip_placemark(pm, as_lines=key in line_folders)
            if not keep: f.remove(pm); dropped += 1
        report[fname] = (before, before-dropped)
    tree.write(os.path.join(work, 'doc.kml'), xml_declaration=True, encoding='UTF-8')
    if os.path.exists(out_kmz): os.remove(out_kmz)
    with zipfile.ZipFile(out_kmz, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(work, 'doc.kml'), 'doc.kml')
        for h in hrefs: z.write(os.path.join(work, h), h, compress_type=zipfile.ZIP_STORED)
    print(name, os.path.getsize(out_kmz), report)
    return report

if __name__ == '__main__':
    D = '/home/claude/dl/k/'; O = '/home/claude/out/'
    build('essentials', D+'essentials', O+'essentials.kmz',
          clip_folders=['Mapped wetlands', 'Streams', 'Soils'], line_folders=['Tax parcel lines'], swap_fix=True)
    build('dd', D+'dd', O+'dd.kmz',
          clip_folders=['Candidate build sites', 'Driveway routes', 'Pond screening'], trim_folders=['Public land'], swap_fix=True)
    build('steward', D+'steward', O+'steward.kmz', clip_folders=['Erosion watch'], swap_fix=True)
    build('property', D+'property', O+'property.kmz',
          clip_folders=['Contours', 'Ridgelines', 'Drainage Paths', 'Benches', 'South-Facing Slopes', 'Landforms', 'Cover Types', 'Field Edges'])
