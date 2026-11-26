#!/usr/bin/env python3
"""Novak|GS Land Intelligence - client page builder.

Builds the client-facing package pages for one property from the engine's land_intel.json and the
Drive file IDs, inside the client's branded shell (header, footer, contact, CSS) taken from an
existing client page so every page matches it.

  python tools/land-intel/build_pages.py tools/land-intel/clients/hamele.json

The client file (clients/<name>.json) says where things live:
  shell        existing branded page whose <head>, header, contact section, and footer are reused
  base         URL folder for the pages ("/hamele")
  data         land_intel.json produced by land_intel.py
  drive        drive_links.json: {"folder": id, "packages": {"1 Essentials": {"folder": id, "files": {name: id}}, ...}}
  images       folder holding the engine's map images (map_*.png, cross_sections.png, landuse_history.png)
  presentation URL of the presentation page (kept for reference; the client pages do not link to it)
  crumbs       optional breadcrumb trail [[text, url or null], ...] shown above each page title
  pages        which packages get a page here and at what slug; package 2 can point at an existing page
  packs        optional per-client package names, e.g. {"2 Hunting & Recreation": {"name": "Country Property",
               "tag": "Interactive Map", "desc": "...", "drive": "2 Country Property"}}; "drive" is the folder
               name used in drive_links.json when the client's Drive copy is renamed
  site_root    optional folder to write into instead of the repo (for a staging build)

The shell can be any client page with a <header> holding <nav class="uc-nav ...">, a contact section
(<section class="sec" id="contact">), and a <footer> whose link list sits under "Quick Links" or "Menu".
"""
import json, os, re, sys, html, shutil
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
E = html.escape

def money(v): return '${:,.0f}'.format(v) if isinstance(v, (int, float)) and v else 'n/a'
def ac(v, d=1): return 'n/a' if v is None else ('{:,.%df}' % d).format(v)
def mb(b): return '%.1f MB' % (b / 1048576) if b >= 1048576 else '%d KB' % max(1, round(b / 1024))
def dl_url(fid): return 'https://drive.google.com/uc?export=download&amp;id=%s' % fid
def view_url(fid): return 'https://drive.google.com/file/d/%s/view' % fid
def folder_url(fid): return 'https://drive.google.com/drive/folders/%s' % fid
def plural(n, one, many=None): return '%s %s' % (n, one if n == 1 else (many or one + 's'))

PACK_ORDER = ['1 Essentials', '2 Hunting & Recreation', '3 Buyer Due Diligence', '4 Stewardship']
PACK_INFO = {
    '1 Essentials': ('Essentials', 'What the land is, where the water goes, and what is underfoot. One mapping flight plus the public layers every buyer asks about.'),
    '2 Hunting & Recreation': ('Hunting & Recreation', 'The terrain read, cover and edges, live night thermal, and files for the hunting apps buyers already use.'),
    '3 Buyer Due Diligence': ('Buyer Due Diligence', 'Public records, candidate build sites and driveways, pond screening, and what surrounds the property.'),
    '4 Stewardship': ('Stewardship', 'The baseline for owning it: erosion watch, cover and canopy, ongoing deer herd surveys, and repeat photo points. Paid for by the buyer after closing.'),
}

PACK_TAG = {'1 Essentials': 'The Land', '2 Hunting & Recreation': 'Interactive Map', '3 Buyer Due Diligence': 'Records & Build Sites', '4 Stewardship': 'After Closing'}
DRIVE_KEY = {}   # package key -> folder name in drive_links.json, when a client renames a package

def apply_packs(cfg):
    """Let a client rename packages without touching the builders.
    cfg["packs"] = {"2 Hunting & Recreation": {"name": "Country Property", "desc": "...", "tag": "Interactive Map",
                                               "drive": "2 Country Property"}, ...}  (every field optional)"""
    for k, o in cfg.get('packs', {}).items():
        if k not in PACK_INFO: sys.exit('unknown package in "packs": %s' % k)
        PACK_INFO[k] = (o.get('name', PACK_INFO[k][0]), o.get('desc', PACK_INFO[k][1]))
        PACK_TAG[k] = o.get('tag', PACK_TAG[k])
        if o.get('drive'): DRIVE_KEY[k] = o['drive']

def drive_pack(cfg, pack):
    return cfg['_drive']['packages'].get(DRIVE_KEY.get(pack, pack), {})
AGENT_FILES = ('Listing Graphics.zip',)   # for the listing team; offered on the presentation page, not on the client pages

# ------------------------------------------------------------------------------------------- shell
EXTRA_CSS = ('<style>'
             '.li-sw{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}'
             '.li-sw a{display:flex;flex-direction:column;gap:4px;padding:12px 14px;border:1px solid #e6e6e6;background:#fff;text-decoration:none;color:#1a1a1a}'
             '.li-sw a b{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--or)}'
             '.li-sw a span{font-size:15px;font-weight:600;text-transform:uppercase}'
             '.li-sw a.on{border-color:var(--or);box-shadow:inset 0 -3px 0 var(--or)}'
             '.li-sw a:hover{border-color:var(--or)}'
             '.li-fig{margin:0;border:1px solid #e6e6e6;background:#fff}'
             '.li-fig img{display:block;width:100%;height:auto}'
             '.li-fig figcaption{padding:10px 14px;font-size:14px;line-height:1.5;color:#777;border-top:1px solid #e6e6e6}'
             '.li-two{display:grid;grid-template-columns:1.15fr 1fr;gap:18px;align-items:start}'
             '.li-tbl{width:100%;border-collapse:collapse;font-size:14.5px;background:#fff;border:1px solid #e6e6e6}'
             '.li-tbl th{background:#e6e6e6;text-align:left;padding:8px 10px;font-weight:600;font-size:13px;text-transform:uppercase;color:#1a1a1a}'
             '.li-tbl td{padding:8px 10px;border-top:1px solid #efefef;color:#555;vertical-align:top}'
             '.li-scroll{overflow-x:auto}'
             '.card.dl small.use{flex:1;display:block;padding:8px 16px 4px;font-size:14.5px;line-height:1.5;color:var(--muted)}'
             '.card.dl small.use b{display:block;margin-bottom:3px;font-size:12px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--or)}'
             '.li-kv{display:grid;grid-template-columns:minmax(180px,.8fr) 2fr;border:1px solid #e6e6e6;background:#fff}'
             '.li-kv dt,.li-kv dd{margin:0;padding:9px 12px;border-top:1px solid #efefef;font-size:14.5px;line-height:1.5}'
             '.li-kv dt{font-weight:600;color:#1a1a1a}.li-kv dd{color:#555}'
             '.li-kv dt:first-of-type,.li-kv dd:first-of-type{border-top:0}'
             '.li-src{font-size:13px;line-height:1.6;color:#848484}.li-src a{color:#777}'
             '.li-back{display:flex;flex-wrap:wrap;gap:10px}'
             '@media(max-width:860px){.li-sw{grid-template-columns:repeat(2,1fr)}.li-two{grid-template-columns:1fr}.li-kv{grid-template-columns:1fr}.li-kv dd{border-top:0;padding-top:0}}'
             '</style>')

def load_shell(path):
    s = open(path, encoding='utf-8').read()
    head = s[:s.find('<body>')]
    header = s[s.find('<header'):s.find('</header>') + 9]
    contact = s[s.find('<section class="sec" id="contact">'):]
    contact = contact[:contact.find('</section>') + 10]
    m = re.search(r'<footer[\s>]', s)
    footer = s[m.start():s.find('</footer>') + 9] if m else ''
    return head, header, contact, footer

def page(shell, title, desc, nav, quick, main):
    head, header, contact, footer = shell
    head = re.sub(r'<title>.*?</title>', '<title>%s</title>' % E(title), head, flags=re.S)
    head = re.sub(r'<meta name="description" content="[^"]*">', '<meta name="description" content="%s">' % E(desc), head)
    header = re.sub(r'<nav class="(uc-nav[^"]*)"[^>]*>.*?</nav>', lambda m: '<nav class="%s" aria-label="Page">%s</nav>' % (m.group(1), ''.join('<a href="%s">%s</a>' % (h, E(t)) for h, t in nav)), header, count=1, flags=re.S)
    footer = re.sub(r'<h5>(Quick Links|Menu)</h5><ul>.*?</ul>', lambda m: '<h5>%s</h5><ul>%s</ul>' % (m.group(1), ''.join('<li><a href="%s">%s</a></li>' % (h, E(t)) for h, t in quick)), footer, count=1, flags=re.S)
    extra_css = EXTRA_CSS
    if '.li-sw{' not in head:
        head = head.replace('</head>', extra_css + '\n</head>')
    return (head + '<body>\n' + header + '\n<div class="hl-root">\n<main class="hl-main">\n' + main + '\n' + contact + '\n</main>\n</div>\n' + footer + '\n</body>\n</html>\n')

# ------------------------------------------------------------------------------------------- blocks
def hero(cfg, D, kicker, h1, lede):
    pr = D['property']; m = D['meta']
    trail = ' // '.join(('<a href="%s" rel="noopener">%s</a>' % (E(u), E(t))) if u else E(t) for t, u in cfg.get('crumbs', []))
    crumbs = (trail + ' // ' if trail else '') + E('%s: %s' % (cfg['property_name'], h1))
    return ('<section class="sec" style="gap:14px">\n'
            '<p class="crumbs">%s</p>\n'
            '<div><p class="lnum">%s</p><h1 class="ltitle">%s<span class="sep"> | </span><span class="l2">%s</span></h1></div>\n'
            '<div class="lmeta"><div style="display:flex;flex-direction:column;gap:8px"><p class="county">County: %s</p><p class="loc">%s County, %s</p></div><p class="price">%s&plusmn; Acres</p></div>\n'
            '<h2 class="uh" style="margin-top:6px">What This Package Covers</h2>\n<p class="lede">%s</p>\n</section>\n'
            % (crumbs, E(kicker), E(cfg['property_name']), E(h1), E(m['county']), E(m['county']), E(m['state']), ac(pr['acres']), lede))

def switcher(cfg, current):
    a = []
    for k in PACK_ORDER:
        url = cfg['pages'].get(k)
        if not url: continue
        a.append('<a href="%s"%s><b>%s</b><span>%s</span></a>' % (url, ' class="on" aria-current="page"' if k == current else '', E(PACK_TAG[k]), E(PACK_INFO[k][0])))
    if len(a) < 2: return ''
    return '<section class="sec"><h2>More About This Property</h2><nav class="li-sw" aria-label="More about this property">%s</nav></section>\n' % ''.join(a)

def stats(items):
    return '<div class="stats">%s</div>\n' % ''.join('<div class="stat"><b>%s</b><span>%s</span></div>' % (b, s) for b, s in items)

def fig(cfg, img, alt, cap):
    if not img: return ''
    return '<figure class="li-fig"><img src="%s" alt="%s" width="%d" height="%d" loading="lazy" decoding="async"><figcaption>%s</figcaption></figure>\n' % (img['url'], E(alt), img['w'], img['h'], cap)

def join_and(xs): return ' and '.join(xs) if len(xs) < 3 else ', '.join(xs[:-1]) + ', and ' + xs[-1]

def two(left, right): return '<div class="li-two">%s<div style="display:flex;flex-direction:column;gap:14px">%s</div></div>\n' % (left, right)

def town(s): return ' '.join(w if w.lower() not in ('of', 'and', 'the') else w.lower() for w in s.title().split()) if s else s

def table(head, rows):
    if not rows: return ''
    return ('<div class="li-scroll"><table class="li-tbl"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>\n'
            % (''.join('<th>%s</th>' % E(h) for h in head), ''.join('<tr>%s</tr>' % ''.join('<td>%s</td>' % (E('' if c is None else str(c))) for c in r) for r in rows)))

def kv(pairs):
    return '<dl class="li-kv">%s</dl>\n' % ''.join('<dt>%s</dt><dd>%s</dd>' % (E(k), v) for k, v in pairs if v not in (None, ''))

def sources(items):
    items = [s for s in items if s and s.get('name')]
    if not items: return ''
    return '<p class="li-src">Sources: %s.</p>\n' % '; '.join('<a href="%s" rel="noopener">%s</a> (retrieved %s)' % (E(s.get('url', '#')), E(s['name']), E(s.get('retrieved', ''))) for s in items)

DESC = {   # what each download is, by file-name ending
    'Essentials Report.pdf': ('Essentials Report', 'A printable summary: the property at a glance, slope and elevation, floodplain, wetlands, streams, and soils.'),
    'Essentials Map (Google Earth).kmz': ('Google Earth File', 'The leaf-off aerial with parcel lines, floodplain, wetlands, streams, and soils. Tap on a phone to open in Google Earth.'),
    'Essentials GIS Layers (GeoJSON).zip': ('GIS Layers', 'Every Essentials layer as GeoJSON for QGIS, ArcGIS, or a mapping app.'),
    'Leaf-Off Aerial (GeoTIFF).tif': ('Leaf-Off Aerial (GeoTIFF)', 'The drone aerial as a georeferenced image, 1.5-inch pixels.'),
    'Elevation 2ft Contours (Shapefile).zip': ('2-Ft Contours', 'Contours from the 2024 bare-earth LiDAR as a shapefile.'),
    'Listing Graphics.zip': ('Listing Graphics', 'Six 2400 px images sized for a listing gallery.'),
    'Property Map (Google Earth).kmz': ('Google Earth File', 'Every hunting layer in one file, including the thermal snapshot.'),
    'Property Overview.pdf': ('Two-Page Property Overview', 'A plain-language summary of the terrain, cover, and thermal survey.'),
    'Hunting App Files (GPX + KML).zip': ('Hunting App Files', 'Ridgelines, drainage paths, travel hubs, benches, edges, corners, contours, and the boundary for onX, HuntStand, BaseMap, Gaia GPS, and others.'),
    'Buyer Due Diligence Report.pdf': ('Due Diligence Report', 'Parcels and assessment, zoning records, build sites and driveways, pond screening, geology and wells, nearby records, and historical maps.'),
    'Due Diligence Map (Google Earth).kmz': ('Google Earth File', 'Build sites, driveway routes, pond screening, zoning, public land, and nearby records in one file.'),
    'Due Diligence GIS Layers (GeoJSON).zip': ('GIS Layers', 'Every Due Diligence layer as GeoJSON.'),
    'Public Records (CSV).zip': ('Records Tables', 'Parcels, soils, build sites, nearby DNR records, public land, permits, and historical maps as spreadsheets (CSV).'),
    'Surface Model (GeoTIFF).tif': ('Drone Surface Model', 'Top-of-surface elevations from the drone flight (trees, buildings, ground) as a GeoTIFF.'),
    'Bare Earth 2024 LiDAR (GeoTIFF).tif': ('Bare-Earth Elevation', 'The 2024 public LiDAR ground surface, clipped to the property.'),
    'Historical Topo Maps.zip': ('Historical USGS Maps', 'The oldest and newest detailed USGS topographic maps of the property, as images and GeoTIFFs.'),
    'Stewardship Baseline Report.pdf': ('Baseline Report', 'Erosion watch, cover and canopy, thermal baseline, land-use history, and repeat photo points.'),
    'Stewardship Map (Google Earth).kmz': ('Google Earth File', 'Erosion watch lines, repeat photo points, and the thermal snapshot.'),
    'Stewardship GIS Layers (GeoJSON).zip': ('GIS Layers', 'Every Stewardship layer as GeoJSON.'),
    'Repeat Photo Points.gpx': ('Repeat Photo Points (GPX)', 'Load into a phone app and stand in the same spots each visit.'),
}
USE = {   # plain-language "How to Use It" note under each download, by file-name ending
    'Essentials Report.pdf': 'A standard document that opens on any phone or computer, so you can print it for a showing or email it to a buyer, lender, or appraiser.',
    'Essentials Map (Google Earth).kmz': 'A map file for the free Google Earth app. Tap it on a phone or open it on a computer, then turn layers on and off to see what’s where on the property.',
    'Essentials GIS Layers (GeoJSON).zip': 'The map layers in a format that professional mapping software reads. Most buyers won’t open it; it’s the file to hand a surveyor, forester, or builder.',
    'Leaf-Off Aerial (GeoTIFF).tif': 'A high-detail photo of the property that mapping software places exactly where it belongs. It’s a large file, so download it on Wi-Fi; for a quick look, the Google Earth file is easier.',
    'Elevation 2ft Contours (Shapefile).zip': 'Lines that connect points of equal height, every 2 feet. A builder, engineer, or excavator uses them to plan a driveway, building pad, or pond.',
    'Property Map (Google Earth).kmz': 'A map file for the free Google Earth app. Tap it on a phone or open it on a computer, then turn layers on and off to scout the terrain before a visit.',
    'Property Overview.pdf': 'A standard document that opens on any phone or computer, so you can print it or send it to a buyer as a quick read on the property.',
    'Hunting App Files (GPX + KML).zip': 'The scouting lines and points in the formats hunting apps import. Unzip the folder, then add the files with the app’s import option (often on its website) to see them on a phone in the field.',
    'Buyer Due Diligence Report.pdf': 'A standard document that opens on any phone or computer, so you can share it with a buyer, lender, attorney, or builder as one summary of the records and build options.',
    'Due Diligence Map (Google Earth).kmz': 'A map file for the free Google Earth app. Tap it on a phone or open it on a computer, then turn layers on and off to compare build sites, driveway routes, and nearby records.',
    'Due Diligence GIS Layers (GeoJSON).zip': 'The map layers in a format that professional mapping software reads. Most buyers won’t open it; it’s the file to hand a surveyor, forester, or builder.',
    'Public Records (CSV).zip': 'Spreadsheets of the records behind the report. Unzip the folder and open the tables in Excel or Google Sheets to sort, filter, or print them.',
    'Surface Model (GeoTIFF).tif': 'A height map of the property as the drone saw it, treetops and buildings included. It’s for an engineer, forester, or anyone working in mapping software.',
    'Bare Earth 2024 LiDAR (GeoTIFF).tif': 'A height map of the ground itself, with the trees taken out. An engineer or excavator uses it to size up a driveway, building pad, or pond.',
    'Historical Topo Maps.zip': 'Old government maps of the area. Unzip the folder and open the images like any photo; the mapping copies line up with today’s maps in mapping software.',
    'Stewardship Baseline Report.pdf': 'A standard document that opens on any phone or computer, so you can keep it with the property records as the starting point each repeat flight is compared to.',
    'Stewardship Map (Google Earth).kmz': 'A map file for the free Google Earth app. Tap it on a phone or open it on a computer, then turn layers on and off to see the erosion watch lines and photo points on the aerial.',
    'Stewardship GIS Layers (GeoJSON).zip': 'The map layers in a format that professional mapping software reads. Most buyers won’t open it; it’s the file to hand a surveyor, forester, or builder.',
    'Repeat Photo Points.gpx': 'GPS points for a phone app like onX, HuntStand, or Gaia GPS. Walk to each point and take a photo from the same spot each visit, so changes are easy to compare.',
}
def downloads(cfg, D, pack, intro):
    links = drive_pack(cfg, pack); files = {f['name']: f['bytes'] for f in D['files'].get(pack, [])}
    cards = []
    order = list(DESC)
    files = dict(sorted(files.items(), key=lambda kv_: next((i for i, k in enumerate(order) if kv_[0].endswith(k)), 99)))
    for name, size in files.items():
        fid = links.get('files', {}).get(name)
        if not fid or name.endswith(AGENT_FILES): continue
        key = next((k for k in DESC if name.endswith(k)), None)
        t, s = DESC.get(key, (name, ''))
        ext = name.rsplit('.', 1)[-1].upper()
        use = USE.get(key, '')
        use = ('<small class="use"><b>How to Use It</b>%s</small>' % E(use)) if use else ''
        cards.append('<a class="card dl" href="%s" rel="noopener"><strong>%s</strong><span>%s %s.</span>%s<em>Download %s</em></a>' % (dl_url(fid), E(t), E(s), mb(size), use, ext))
    folder = links.get('folder')
    if not cards: return ''
    return ('<section class="sec" id="downloads"><h2>Downloads</h2><p class="body" style="margin-top:-4px">%s</p><div class="card-grid">%s</div>'
            '%s</section>\n' % (intro, ''.join(cards), ('<p class="note">Everything in this package is also in one <a href="%s" rel="noopener">Google Drive folder</a>. Downloads come from Google Drive; large files may show a "can\'t scan for viruses" notice before downloading.</p>' % folder_url(folder)) if folder else ''))

# ------------------------------------------------------------------------------------------- packages
def p_essentials(cfg, D, I):
    pr = D['property']; tr = D.get('terrain', {}); fl = D.get('flood', {}); wt = D.get('wetlands', {}); so = D.get('soils', {}); wa = D.get('water', {}); acs = D.get('access', {})
    cov = (D.get('cover') or {}).get('cover_acres', {}); pa = D.get('parcels', {})
    sl = tr.get('slope_classes_acres', {})
    gentle = (sl.get('0-6%') or 0) + (sl.get('6-12%') or 0)
    main = hero(cfg, D, 'Land Intelligence Report', 'Essentials',
                'One leaf-off mapping flight%s, combined with the public layers every buyer asks about: parcel lines, floodplain, wetlands, streams, and soils.'
                % (' on %s' % E(D['meta']['flight_dates'].get('mapping')) if D['meta']['flight_dates'].get('mapping') else ''))
    main += stats([(ac(tr.get('relief_ft'), 0) + ' ft', 'Of elevation change, %s to %s ft' % (ac(tr.get('elev_min_ft'), 0), ac(tr.get('elev_max_ft'), 0))),
                   (ac(gentle), 'Acres under 12% slope'),
                   ('0' if not fl.get('sfha_acres') else ac(fl.get('sfha_acres'), 2), 'Acres in the FEMA 1% annual chance floodplain'),
                   (ac(wt.get('acres_in_boundary'), 1), 'Acres of mapped wetland (WI DNR)')])
    main += switcher(cfg, '1 Essentials')
    ov = fig(cfg, I.get('map_overview'), 'Leaf-off aerial with the flight boundary and tax parcel lines',
            'Leaf-off aerial from the drone flight, with the flight boundary (orange) and county tax-parcel lines (yellow, approximate).')
    main += '<section class="sec" id="overview"><h2>The Property at a Glance</h2>\n' + two(ov, kv([('Mapped area', '%s acres (flight boundary)' % ac(pr['acres'], 2)),
                ('Municipality', E(', '.join(town(m) for m in pa.get('municipality', [])) or 'n/a')),
                ('Tax parcels', E('%s (%s)' % (pa.get('count'), ', '.join(str(p.get('PARCELID')) for p in pa.get('list', []))))),
                ('Cover', E(', '.join('%s %.1f ac' % (k, v) for k, v in sorted(cov.items(), key=lambda x: -x[1]))) if cov else None),
                ('Median slope', '%s%%' % tr.get('median_slope_pct')),
                ('Watershed', E(wa.get('watershed') or 'n/a')),
                ('Nearest public road', E('%s, %s ft from the boundary' % (acs.get('nearest_public_road'), ac(acs.get('distance_ft'), 0))) if acs.get('nearest_public_road') else None)])
                 + '<p class="note">%s</p>' % E(pa.get('note', ''))) + '</section>\n'
    wfig = fig(cfg, I.get('map_water'), 'Floodplain, wetlands, hydric soils, and streams over shaded relief', 'FEMA floodplain (dark blue), WI DNR mapped wetlands (green), hydric-soil wetland indicators (light blue), and streams over the LiDAR shaded relief.')
    def zlabel(k):
        z, _, d = k.partition(' - ')
        return 'Zone %s%s' % (z, (', ' + d.lower()) if d else '')
    zones = ', '.join('%s (%s ac)' % (zlabel(k), ac(v, 2)) for k, v in fl.get('zones_acres', {}).items()) or 'none inside the boundary'
    main += '<section class="sec" id="water"><h2>Where the Water Goes</h2>\n' + two(wfig, kv([('FEMA flood zone', E(zones)), ('FIRM panels', E(', '.join('%s, effective %s' % (p['panel'], p['effective']) for p in fl.get('panels', [])))),
                ('Mapped wetland in boundary', '%s ac%s' % (ac(wt.get('acres_in_boundary'), 2), (' (%s)' % E(', '.join('%s %.2f ac' % (k, v) for k, v in wt.get('classes_in_boundary', {}).items()))) if wt.get('classes_in_boundary') else '')),
                ('Wetland points (too small to outline)', str(wt.get('points_in_boundary', 0)) + ' inside, %d within 1/4 mile' % wt.get('points_within_quarter_mile', 0)),
                ('Hydric-soil indicators', '%s ac inside the boundary' % ac(wt.get('wetland_indicator_acres'), 2)),
                ('Nearest stream', E('%s, %s ft away' % (wa['nearest_stream']['name'], ac(wa['nearest_stream']['distance_ft'], 0))) if wa.get('nearest_stream') else 'None within 1/2 mile'),
                ('Nearest pond or lake', E('%s, %s ft away' % (wa['nearest_waterbody']['name'], ac(wa['nearest_waterbody']['distance_ft'], 0))) if wa.get('nearest_waterbody') else 'None within 1/2 mile')])
                 + '<p class="note">%s</p>' % E(wt.get('note', ''))) + '</section>\n'
    rows = [[u['musym'], u['name'], ac(u['acres'], 2), u['drainage'], u['farmland'], u['dwellings_no_basement'], u['septic']] for u in so.get('units', [])]
    us = so.get('units', [])
    gd = sum(u['acres'] for u in us if (u.get('drainage') or '').lower().startswith('well')); pf = sum(u['acres'] for u in us if 'prime' in (u.get('farmland') or '').lower() and not (u.get('farmland') or '').lower().startswith('not'))
    sfig = fig(cfg, I.get('map_soils'), 'Soil map units over shaded relief', 'NRCS soil map units, labeled by symbol.')
    main += '<section class="sec" id="soils"><h2>What&rsquo;s Underfoot</h2>\n' + two(sfig, kv([('Soil map units', str(len(us))),
            ('Largest unit', E('%s, %s ac' % (us[0]['name'], ac(us[0]['acres'], 1))) if us else None),
            ('Well-drained ground', '%s ac' % ac(gd, 1)),
            ('Prime (some only if drained) or statewide-important farmland', '%s ac' % ac(pf + sum(u['acres'] for u in us if 'statewide' in (u.get('farmland') or '').lower()), 1))]))
    main += table(['Map unit', 'Soil', 'Acres', 'Drainage', 'Farmland class', 'Homes w/o basements', 'Septic fields'], rows)
    main += '<p class="note">%s</p></section>\n' % E(so.get('note', ''))
    main += downloads(cfg, D, '1 Essentials', 'Every file is ready to open on a phone or computer, with no special software for the PDF and Google Earth files.')
    main += sources([pa.get('source') and {'name': pa['source']['name'], 'url': 'https://www.sco.wisc.edu/parcels/data/', 'retrieved': D['meta']['built'][:10]}, fl.get('source'), wt.get('source'), wt.get('source_indicators'), so.get('source'), wa.get('source'), acs.get('source')])
    return main

def p_due(cfg, D, I):
    pa = D.get('parcels', {}); C = D.get('county_records', {}); R = D.get('records', {}); BS = D.get('build_sites', {}); PD = D.get('ponds', {})
    rr = R.get('contaminated_sites', {}); wl = R.get('wells', {}); pl = R.get('public_land', {}); ht = D.get('historic_topos', {})
    best = BS.get('sites', [None])[0] if BS.get('sites') else None
    main = hero(cfg, D, 'Land Intelligence Report', 'Buyer Due Diligence',
                'The public records a buyer would otherwise chase down one office at a time, plus candidate build sites with driveway routes, pond screening, and what surrounds the property.')
    main += stats([(str(len(BS.get('sites', []))), 'Candidate build areas screened'),
                   (('%s ft' % ac(best['driveway_ft'], 0)) if best and best.get('driveway_ft') else 'n/a', 'Driveway to the top-ranked site'),
                   (str(len(PD.get('sites', []))), 'Pond sites screened'),
                   (str(rr.get('open', 0)), 'Open DNR contamination records within %s mile' % ac(rr.get('within_mi', 1), 0))])
    main += switcher(cfg, '3 Buyer Due Diligence')
    cols = [('Parcel', lambda p: p.get('PARCELID')), ('Acres in boundary', lambda p: ac(p.get('acres_in_boundary'), 2)), ('Parcel acres (GIS)', lambda p: ac(p.get('GISACRES') or p.get('acres_calc'), 2)),
            ('Tax roll', lambda p: p.get('TAXROLLYEAR')), ('Class', lambda p: p.get('PROPCLASS')), ('Assessed', lambda p: money(p.get('CNTASSDVALUE'))),
            ('Est. fair market', lambda p: money(p.get('ESTFMKVALUE'))), ('Net tax', lambda p: money(p.get('NETPRPTA')))]
    pl_ = pa.get('list', [])
    cols = [c for c in cols if any(c[1](p) not in (None, '', 'n/a') for p in pl_)]
    has_tax = any(c[0] in ('Assessed', 'Net tax') for c in cols)
    main += '<section class="sec" id="records"><h2>Parcels and Assessment</h2>' + table([c[0] for c in cols], [[c[1](p) for c in cols] for p in pl_])
    muni = ', '.join(town(m) for m in pa.get('municipality', [])) or 'the municipality'
    main += '<p class="note">%s%s</p></section>\n' % (E(pa.get('note', '')), '' if has_tax else E(' The statewide parcel file carries no assessment or tax values for these parcels; the current assessment and tax bill are on record with %s.' % muni))
    if C.get('available'):
        z = C.get('zoning', {})
        zf = fig(cfg, I.get('map_zoning'), 'County zoning, wetland district, shoreland district, and resource protection corridors', '%s County zoning and planning layers.' % E(C['county']))
        main += '<section class="sec" id="zoning"><h2>Zoning and Land-Use Records</h2>' + two(zf, kv([('County rural zoning in boundary', E(', '.join('%s, %s ac' % (k, ac(v, 2)) for k, v in z.items())) or E('None. The property is in %s, which zones its own land; check with the municipality.' % (', '.join(town(m) for m in pa.get('municipality', [])) or 'a municipality'))),
                    ('Shoreland, wetland, floodplain districts', E(', '.join('%s: %s ac' % (k, ac(v, 2)) for k, v in C.get('shoreland_wetland_floodplain_acres', {}).items() if v)) or 'None in the boundary'),
                    ('Resource protection corridor', '%s ac' % ac(C.get('resource_protection_acres'), 2)),
                    ('Farmland preservation plan', E(', '.join(C.get('farmland_preservation', [])) or 'n/a')),
                    ('Zoning permits on these parcels', E('; '.join('%s %s (%s)' % (p['permit'], p['description'], p['issued']) for p in C.get('zoning_permits_on_parcels', []))) or 'None on record'),
                    ('Conditional use permits', E('; '.join('%s: %s' % (p['cup'], p['description']) for p in C.get('conditional_use_permits', []))) or 'None mapped'),
                    ('Zoning deed restrictions', E('; '.join('Petition %s: %s' % (p['petition'], p['reason']) for p in C.get('deed_restrictions', []))) or 'None mapped'),
                    ('Zoning office', E(C.get('office') or ''))]))
        if I.get('landuse_history'):
            main += fig(cfg, I['landuse_history'], 'Land use inside the boundary by year', 'How %s County has classified the ground inside the boundary over time (acres).' % E(C['county']))
        main += '</section>\n'
    srows = [[s['id'], ac(s['acres'], 2), '%s%%' % s['mean_slope_pct'], s.get('soil'), s.get('dwellings_no_basement'), s.get('septic'),
              ('%s ft' % ac(s['driveway_ft'], 0)) if s.get('driveway_ft') else 'n/a', ('%s%%' % s['driveway_max_grade_pct']) if s.get('driveway_max_grade_pct') is not None else 'n/a'] for s in BS.get('sites', [])]
    bf = fig(cfg, I.get('map_build'), 'Candidate build areas and driveway routes over the aerial', 'Candidate build areas (yellow) and the gentlest driveway route from the nearest public road (red).')
    main += '<section class="sec" id="build"><h2>Where a House, Shop, or Driveway Could Go</h2>' + two(bf, '<p class="body">%s</p><p class="note">%s</p>' % (E(BS.get('method', '')), E(BS.get('note', ''))))
    main += table(['Site', 'Acres', 'Avg slope', 'Soil', 'Homes w/o basements', 'Septic fields', 'Driveway', 'Steepest 50 ft'], srows) + '</section>\n'
    prow = []
    for p in PD.get('sites', []):
        for s in p['scenarios']:
            prow.append([p['id'], '%s ac' % p['drainage_acres'], '%s ft' % s['embankment_height_ft'], '%s ac' % s['pool_acres'], '%s ac-ft' % s['storage_acre_ft'], '%s ft' % ac(s['embankment_length_ft'], 0), p.get('pond_reservoir_rating')])
    pf = fig(cfg, I.get('map_ponds'), 'Pond screening sites with catchments and pools', 'Embankment sites, the area draining to each (dashed), and the pool at the first embankment height (blue).')
    main += '<section class="sec" id="ponds"><h2>What a Pond Here Would Involve</h2>' + two(pf, '<p class="body">%s</p><p class="note">%s</p>' % (E(PD.get('method', '')), E(PD.get('note', ''))))
    main += (table(['Site', 'Drains', 'Embankment', 'Pool', 'Storage', 'Embankment length', 'Soil rating (pond area)'], prow) if prow else '') + '</section>\n'
    bd = wl.get('bedrock_depth_ft'); wd = wl.get('well_depth_ft'); br = R.get('bedrock') or {}; sf = R.get('surficial') or {}
    main += '<section class="sec" id="ground"><h2>Ground and Water Beneath</h2>'
    main += kv([('Bedrock (state map)', E('%s. %s' % (br.get('DescriptionOfMapUnits.Name'), br.get('DescriptionOfMapUnits.Description'))) if br.get('DescriptionOfMapUnits.Name') else None),
                ('Surface deposits (state map)', E('%s. %s' % (sf.get('DescriptionOfMapUnits.Name'), sf.get('DescriptionOfMapUnits.Description'))) if sf.get('DescriptionOfMapUnits.Name') else None),
                ('Depth to bedrock, nearby wells', E('%s within %.0f mile: %d to %d ft, median %d ft' % (plural(wl['records_with_bedrock_depth'], 'well'), wl['within_mi'], bd['min'], bd['max'], bd['median'])) if bd else 'No records nearby'),
                ('Well depth, same wells', E('%d to %d ft, median %d ft' % (wd['min'], wd['max'], wd['median'])) if wd else None),
                ('Historical well reports within %.0f mile' % (wl.get('within_mi') or 1), str(wl.get('historical_well_reports')))])
    main += '<p class="note">%s</p>' % E(wl.get('note', ''))
    main += fig(cfg, I.get('cross_sections'), 'Elevation cross-sections through the property', 'Cross-sections through the middle of the property: 2024 LiDAR bare earth (brown) and top of surface (green).')
    li = D.get('lidar', {})
    main += '<p class="note">The drone surface was checked against the %s LiDAR on open, flat ground: median difference %+.2f ft, spread (NMAD) %.2f ft. No independent survey checkpoints were set on this property, so elevations are stated relative to the public LiDAR, not as a certified accuracy.</p></section>\n' % (
        E(str(li.get('dataset'))), li.get('drone_minus_lidar_median_ft') or 0, li.get('drone_minus_lidar_nmad_ft') or 0)
    rrows = [[x['name'], x['status'], x['address'], '%s to %s' % (x['opened'] or '?', x['closed'] or 'open'), '%.2f mi' % x['distance_mi']] for x in rr.get('list', [])[:10]]
    plrows = [[x['name'], x['manager'], x['access'], ('{:,.0f}'.format(x['acres']) if (x.get('acres') or 0) >= 1 else 'under 1'), '%.2f mi' % x['distance_mi']] for x in pl.get('list', [])[:10]]
    cf = fig(cfg, I.get('map_context'), 'Public land and DNR records within two miles', 'Public land (green) and WI DNR contaminated-land records (red) within about two miles.')
    main += '<section class="sec" id="around"><h2>What Is Around It</h2>' + two(cf, '<p class="body">Within %s mile of the property: %s and %s in the WI DNR contaminated-lands database, %s on the property itself.</p><p class="body">%s within %s miles.</p>' % (
        ac(rr.get('within_mi'), 0), plural(rr.get('open', 0), 'open record'), plural(rr.get('closed', 0), 'closed record'), 'none' if not rr.get('on_property') else rr['on_property'],
        plural(len(pl.get('list', [])), 'public property', 'public properties'), ac(pl.get('within_mi'), 0)))
    main += table(['Record', 'Status', 'Address', 'Years', 'Distance'], rrows)
    main += '<h3 class="tgh">Public Land Within %s Miles</h3>' % ac(pl.get('within_mi'), 0) + table(['Name', 'Managed by', 'Access', 'Acres', 'Distance'], plrows) + '</section>\n'
    crops = ht.get('crops', [])
    if crops:
        main += '<section class="sec" id="history"><h2>Historical Maps</h2><p class="body">USGS topographic maps of this ground exist for %s. The oldest and newest detailed editions are below, with the boundary in orange.</p><div class="li-two">' % E(', '.join(str(y) for y in ht.get('years', [])))
        for c in crops: main += fig(cfg, I.get('historic_topo_%d' % c['year']), c['title'], E(c['title']))
        main += '</div></section>\n'
    main += downloads(cfg, D, '3 Buyer Due Diligence', 'Every file is ready to open on a phone or computer, with no special software for the PDF and Google Earth files.')
    main += sources([rr.get('source'), wl.get('source'), wl.get('source_wcr')] + (R.get('geology_sources') or []) + [pl.get('source'), pl.get('source2')] + (C.get('sources') or []) + [ht.get('source'), D.get('access', {}).get('source')])
    return main

def p_steward(cfg, D, I):
    S = D.get('stewardship', {}); th = S.get('thermal_baseline', {})
    main = hero(cfg, D, 'Land Intelligence Report', 'Stewardship',
                'A buyer-paid service for after closing. This flight becomes the baseline, and each repeat flight and deer herd survey measures what changed: herd use, erosion, canopy, trails, and restoration work.')
    main += stats([(str(S.get('erosion_watch_count', 0)), 'Steep drainage paths on erosion watch'), (str(S.get('photo_points', 0)), 'Repeat photo points saved'),
                   (str(sum(th.values())) if th else 'n/a', 'Thermal detections in the baseline'), (str(len(S.get('cover_units', []))), 'Cover types with canopy heights')])
    main += switcher(cfg, '4 Stewardship')
    main += '<section class="sec" id="baseline"><h2>The Baseline</h2><p class="body">%s</p>' % E(S.get('note', ''))
    sf_ = fig(cfg, I.get('map_steward'), 'Erosion watch lines and repeat photo points over the aerial', 'Erosion watch (red) and repeat photo points (yellow).')
    er = [[e['id'], '%s%%' % e['mean_slope_pct'], '%s ac' % e['drainage_acres'], '%s ft' % ac(e['length_ft'], 0)] for e in S.get('erosion_watch', [])]
    main += two(sf_, '<h3 class="tgh">Erosion Watch</h3>' + (table(['ID', 'Avg slope', 'Drains', 'Length'], er) if er else '<p class="body">No drainage path met the erosion-watch threshold.</p>')
                + '<p class="note">%s</p>' % E(S.get('method', '')))
    cu = [[u['cover'], ac(u['acres'], 2), ('%s ft' % ac(u['median_canopy_ft'], 0)) if u.get('median_canopy_ft') is not None else 'n/a'] for u in S.get('cover_units', [])]
    main += '<h3 class="tgh">Cover and Canopy</h3>' + table(['Cover', 'Acres', 'Median canopy height (2024 LiDAR)'], cu)
    if I.get('landuse_history'):
        main += '<h3 class="tgh">Land-Use History</h3>' + fig(cfg, I['landuse_history'], 'Land use inside the boundary by year', 'County land-use classes inside the boundary, by year (acres).')
    main += '</section>\n'
    main += ('<section class="sec" id="herd"><h2>Ongoing Deer Herd Surveys</h2>'
             '<p class="body">%s Each ongoing survey flies the property again after dark, in the same season and on the same flight plan, '
             'so the owner can compare herd use from one year to the next instead of guessing at it.</p><div class="card-grid">'
             '<div class="card"><strong>Same Season, Same Route</strong><span>Flown at the same time of year, altitude, and overlap as the baseline, so each count compares fairly.</span></div>'
             '<div class="card"><strong>Where the Herd Is Using the Land</strong><span>Each survey maps where deer were found, so shifts toward or away from cover, plots, and edges show up over time.</span></div>'
             '<div class="card"><strong>A Count, Not a Census</strong><span>Each survey is a snapshot of one night, delivered after processing. Deer under heavy cover or off the property that night are not counted, so treat each number as a minimum.</span></div>'
             '</div>'
             '<div class="together" style="border-color:var(--edge2);background:var(--panel);margin-top:18px"><h3>Paid for by the Buyer</h3>'
             '<p>Stewardship is for the buyer after closing. Ongoing deer herd surveys and repeat flights are booked and paid for by the buyer, directly with Novak Geospatial Solutions&trade;. '
             'They are not part of the listing or the purchase price.</p></div></section>\n'
             % (('The night thermal survey from %s is the herd baseline: %s.' % (E(', '.join((D['meta']['flight_dates'].get('thermal') or '').split(', ')[:2])), E(join_and(['%d %s' % (v, k.lower()) for k, v in th.items()]))))
                if th else 'The first night thermal survey becomes the herd baseline.'))
    main += ('<section class="sec" id="repeat"><h2>What Each Repeat Flight Adds</h2><div class="card-grid">'
             '<div class="card"><strong>Erosion and Washouts</strong><span>The same drainage paths re-mapped and compared, so a gully that grew is measured, not guessed.</span></div>'
             '<div class="card"><strong>Canopy and Openings</strong><span>Storm damage, timber work, and regrowth shown against this flight.</span></div>'
             '<div class="card"><strong>Trails and Food Plots</strong><span>New trails, plots, and clearings mapped with acreage on each visit.</span></div>'
             '<div class="card"><strong>Deer Herd Survey</strong><span>A night thermal count in the same season, compared to the baseline.</span></div>'
             '</div></section>\n')
    main += downloads(cfg, D, '4 Stewardship', 'Every file is ready to open on a phone or computer, with no special software for the PDF and Google Earth files.')
    return main

BUILDERS = {'1 Essentials': p_essentials, '3 Buyer Due Diligence': p_due, '4 Stewardship': p_steward}

# ------------------------------------------------------------------------------------------- images
def prep_images(cfg, outdir):
    src = cfg['images']; I = {}
    os.makedirs(outdir, exist_ok=True)
    for f in sorted(os.listdir(src)):
        if not f.lower().endswith('.png'): continue
        k = f[:-4]; im = Image.open(os.path.join(src, f)).convert('RGB')
        if im.width > 1600: im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
        dst = os.path.join(outdir, k + '.jpg'); im.save(dst, 'JPEG', quality=82, optimize=True, progressive=True)
        I[k] = {'url': cfg['base'] + '/li-img/' + k + '.jpg', 'w': im.width, 'h': im.height}
    return I

# ------------------------------------------------------------------------------------------- package 2 page (existing)
def patch_package2(cfg, D, path):
    s = open(path, encoding='utf-8').read()
    links = drive_pack(cfg, '2 Hunting & Recreation').get('files', {})
    for name, fid in links.items():
        for old in re.findall(r'href="(/[^"]+)" download="%s"' % re.escape(name), s):
            s = s.replace('href="%s" download="%s"' % (old, name), 'href="%s" rel="noopener"' % dl_url(fid))
    sw = switcher(cfg, '2 Hunting & Recreation')
    s = re.sub(r'<!-- LI-SWITCH -->.*?<!-- /LI-SWITCH -->\n?', '', s, flags=re.S)
    s = s.replace('<!-- DOWNLOADS -->', '<!-- LI-SWITCH -->\n' + sw + '<!-- /LI-SWITCH -->\n<!-- DOWNLOADS -->', 1)
    if '.li-sw{' not in s:
        s = s.replace('</head>', EXTRA_CSS + '\n</head>', 1)
    open(path, 'w', encoding='utf-8').write(s)

def main():
    cfg = json.load(open(sys.argv[1], encoding='utf-8'))
    rel = lambda p: p if os.path.isabs(p) else os.path.join(ROOT, p)
    D = json.load(open(rel(cfg['data']), encoding='utf-8'))
    cfg['_drive'] = json.load(open(rel(cfg['drive']), encoding='utf-8'))
    apply_packs(cfg)
    cfg['images'] = rel(cfg['images'])
    shell = load_shell(rel(cfg['shell']))
    site = rel(cfg.get('site_root', '.'))
    I = prep_images(cfg, os.path.join(site, cfg['base'].strip('/'), 'li-img'))
    quick = [(cfg['pages'][k], PACK_INFO[k][0]) for k in PACK_ORDER if cfg['pages'].get(k)]
    for pack, fn in BUILDERS.items():
        url = cfg['pages'].get(pack)
        if not url: continue
        nav = [('#downloads', 'Downloads'), ('#contact', 'Contact')]
        title = '%s: Land Intelligence %s | %s' % (cfg['property_name'], PACK_INFO[pack][0], cfg['client_brand'])
        html_ = page(shell, title, '%s. %s' % (cfg['property_name'], PACK_INFO[pack][1]), nav, quick, fn(cfg, D, I))
        out = os.path.join(site, url.strip('/'), 'index.html'); os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, 'w', encoding='utf-8').write(html_); print('wrote', out, len(html_))
    p2 = cfg['pages'].get('2 Hunting & Recreation')
    if p2 and cfg.get('patch_package2', True):
        patch_package2(cfg, D, os.path.join(site, p2.strip('/'), 'index.html')); print('patched', p2)

if __name__ == '__main__':
    main()
