#!/usr/bin/env python3
"""Novak|GS Land Intelligence - reskin a finished job for another brokerage.

Takes one job's finished client pages (built and hand-tuned for one client, e.g. /hamele/) and
produces the same four package pages, files, and reports in another client's look (e.g. EXIT):

  python3 tools/land-intel/reskin.py tools/land-intel/clients/exit.json [--pages-only]

Steps, all driven by the client file:
  1. copy     images, map tiles, and package files from the source job, with renames
  2. archives rename folders inside ZIPs and the document name inside KMZs
  3. pdfs     rebrand the report PDFs (header bar, logo, accent color, property title) and the
              two-page property overview (title and "Prepared for" line)
  4. pages    rebuild each page: skin CSS, fonts, icons, header with section tabs, hero with the
              package card and listing agent, contact box, footer, renamed paths and Drive links,
              text edits, and inserted sections (skins/<client>/fragments/*.html)

Every text edit must match exactly once, so a changed source page stops the run instead of
quietly producing a half-converted page. The source job is never modified.
"""
import argparse, io, json, os, re, shutil, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = Path(__file__).resolve().parent

ICONS = {
    'icon_phone': '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25 11.4 11.4 0 0 0 3.6.57 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.57a1 1 0 0 1-.25 1z"/></svg>',
    'icon_download': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4v11"/><path d="m7 10 5 5 5-5"/><path d="M5 20h14"/></svg>',
    'icon_mail': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="1.5"/><path d="m3.5 6 8.5 7 8.5-7"/></svg>',
}


def die(msg):
    sys.exit('reskin: ' + msg)


def fill(tpl, vals):
    def sub(m):
        k = m.group(1)
        if k not in vals:
            die('template needs {{%s}}' % k)
        return str(vals[k])
    return re.sub(r'\{\{([a-z_0-9]+)\}\}', sub, tpl)


def once(s, find, repl, where):
    n = s.count(find)
    if n != 1:
        die('%s: expected 1 match for %r, found %d' % (where, find[:90], n))
    return s.replace(find, repl)


def esc_text(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# ------------------------------------------------------------------------------------ 1. copy
def copy_assets(cfg):
    src_root, dst = ROOT, ROOT / cfg['dest']['dir']
    dst.mkdir(parents=True, exist_ok=True)
    for a, b in cfg.get('copy_dirs', []) + cfg.get('copy_files', []):
        s, d = src_root / a, dst / b
        if not s.is_dir():
            die('missing source folder ' + a)
        shutil.copytree(s, d, dirs_exist_ok=True)
    for a, b in cfg.get('renames', []):
        s, d = dst / a, dst / b
        if s.exists():
            if d.exists():
                d.unlink()
            s.rename(d)
        elif not d.exists():
            die('nothing to rename at ' + a)
    print('copy: assets in', cfg['dest']['dir'])


# -------------------------------------------------------------------------------- 2. archives
def rewrite_zip(path, fn):
    """Rewrite every entry of a ZIP through fn(name, data) -> (name, data)."""
    src = zipfile.ZipFile(path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as out:
        for info in src.infolist():
            data = src.read(info.filename)
            name, data = fn(info.filename, data)
            zi = zipfile.ZipInfo(name, date_time=info.date_time)
            zi.compress_type = zipfile.ZIP_STORED if info.compress_type == zipfile.ZIP_STORED else zipfile.ZIP_DEFLATED
            zi.external_attr = info.external_attr
            out.writestr(zi, data)
    src.close()
    Path(path).write_bytes(buf.getvalue())


def archives(cfg):
    dst = ROOT / cfg['dest']['dir']
    for rel, pairs in cfg.get('zip_folder_renames', {}).items():
        def fn(name, data, pairs=pairs):
            for a, b in pairs:
                if name.startswith(a):
                    name = b + name[len(a):]
            return name, data
        rewrite_zip(dst / rel, fn)
        print('zip: renamed folders in', rel)
    for rel, pairs in cfg.get('kmz_text', {}).items():
        def fn(name, data, pairs=pairs):
            if name.lower().endswith('.kml'):
                t = data.decode('utf-8')
                for a, b in pairs:
                    t = t.replace(a, b)
                data = t.encode('utf-8')
            return name, data
        rewrite_zip(dst / rel, fn)
        print('kmz: renamed document in', rel)


# ------------------------------------------------------------------------------------ 3. pdfs
def _rg(c):
    return ('%s %s %s rg' % tuple(('%g' % v) if v in (0, 1) else ('%.6f' % v).rstrip('0').lstrip('0') for v in c)).encode()


def _overlay(pages, draw):
    """One reportlab page per PDF page, drawn by draw(canvas, page_index, width, height)."""
    from reportlab.pdfgen import canvas as rl
    from pypdf import PdfReader
    buf = io.BytesIO()
    w, h = float(pages[0].mediabox.width), float(pages[0].mediabox.height)
    c = rl.Canvas(buf, pagesize=(w, h))
    for i in range(len(pages)):
        draw(c, i, w, h)
        c.showPage()
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages


def rebrand_report(path, cfg):
    """ReportLab-built report: 39.6 pt header bar with the client logo, accent headings."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, StreamObject
    b = cfg['brand']
    r = PdfReader(str(path))
    w = PdfWriter(clone_from=r)
    bar_old = b'.101961 .101961 .101961 rg\nn 0 752.4 612 39.6 re f*'
    bar_new = _rg(b['pdf_bar_rgb']) + b'\nn 0 752.4 612 39.6 re f*'
    logo_re = re.compile(rb'q\n[\d.]+ 0 0 [\d.]+ 36 [\d.]+ cm\n/(FormXob\.[0-9a-f]+) Do\nQ\n(?=1 1 1 rg)')
    seen = 0
    for page in w.pages:
        data = page.get_contents().get_data()
        if bar_old not in data:
            die('%s: header bar not found' % path.name)
        data = data.replace(bar_old, bar_new)
        data, n = logo_re.subn(b'', data, count=1)
        seen += n
        data = data.replace(b'.407843 .490196 .32549 rg', _rg(b['pdf_accent_rgb']))
        data = data.replace(b'.933333 .941176 .917647 rg', _rg(b['pdf_tint_rgb']))
        for a, bb in cfg.get('pdf_text', []):
            data = data.replace(('(%s)' % a).encode('latin-1'), ('(%s)' % bb).encode('latin-1'))
        st = StreamObject()
        st.set_data(data)
        page[NameObject('/Contents')] = w._add_object(st)
    if not seen:
        die('%s: logo not found' % path.name)
    logo = str(ROOT / b['pdf_logo_white'])
    from PIL import Image
    lw, lh = Image.open(logo).size
    hgt = 30.0
    wid = hgt * lw / lh

    def draw(c, i, W, H):
        c.drawImage(logo, 36, 752.4 + (39.6 - hgt) / 2, width=wid, height=hgt, mask='auto')
    for page, ov in zip(w.pages, _overlay(w.pages, draw)):
        page.merge_page(ov)
    meta = dict(r.metadata or {})
    for a, bb in cfg.get('pdf_text', []):
        meta = {k: (v.replace(a, bb) if isinstance(v, str) else v) for k, v in meta.items()}
    w.add_metadata(meta)
    with open(path, 'wb') as f:
        w.write(f)


def rebrand_overview(path, cfg, spec):
    """Two-page property overview: replace the title and the "Prepared for" line in the dark header."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, StreamObject
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    fonts = TOOL / 'fonts'
    pdfmetrics.registerFont(TTFont('Roboto-800', str(fonts / 'Roboto-800.ttf')))
    pdfmetrics.registerFont(TTFont('Roboto-400', str(fonts / 'Roboto-400.ttf')))
    r = PdfReader(str(path))
    w = PdfWriter(clone_from=r)
    title_re = re.compile(rb'BT 1 0 0 1 36 754 Tm /F\d\+0 18 Tf [\d.]+ TL \((?:\\.|[^\\)])*\) Tj T\* ET\n')
    sub_re = re.compile(rb'BT 1 0 0 1 36 736 Tm /F\d\+0 9\.5 Tf [\d.]+ TL \((?:\\.|[^\\)])*\) Tj T\* ET\n')
    for page in w.pages:
        data = page.get_contents().get_data()
        data, n1 = title_re.subn(b'', data, count=1)
        data, n2 = sub_re.subn(b'', data, count=1)
        if not (n1 and n2):
            die('%s: header text not found' % path.name)
        st = StreamObject()
        st.set_data(data)
        page[NameObject('/Contents')] = w._add_object(st)
    N = len(w.pages)

    def draw(c, i, W, H):
        c.setFillColorRGB(1, 1, 1)
        c.setFont('Roboto-800', 18)
        c.drawString(36, 754, spec['title'])
        c.setFillColorRGB(.764706, .796078, .823529)
        c.setFont('Roboto-400', 9.5)
        c.drawString(36, 736, spec['sub'].format(n=i + 1, N=N))
    for page, ov in zip(w.pages, _overlay(w.pages, draw)):
        page.merge_page(ov)
    meta = dict(r.metadata or {})
    if spec.get('meta_title'):
        meta['/Title'] = spec['meta_title']
    w.add_metadata(meta)
    with open(path, 'wb') as f:
        w.write(f)


def pdfs(cfg):
    dst = ROOT / cfg['dest']['dir']
    for spec in cfg.get('pdfs', []):
        p = dst / spec['file']
        if spec['kind'] == 'report':
            rebrand_report(p, cfg)
        else:
            rebrand_overview(p, cfg, spec)
        print('pdf: rebranded', spec['file'])


# ----------------------------------------------------------------------------------- 4. pages
def page_vals(cfg, pk):
    v = {}
    for k in ('brand', 'agent', 'office', 'property', 'footer'):
        v.update(cfg.get(k, {}))
    v.update(ICONS)
    v['pkg_name'] = pk['name']
    v['pkg_tag'] = pk['tag']
    v['pkg_label'] = 'Land Intelligence Package %d of %d' % (pk['num'], len(cfg['packages']))
    v['tabs'] = ''.join('<a href="%s">%s</a>' % (h, t) for h, t in pk['tabs'])
    base = cfg['dest']['base']
    v['menu'] = ''.join('<li><a href="%s/%s/">%s</a></li>' % (base, p['slug'], p['name']) for p in cfg['packages'])
    crumbs = []
    for t, u in cfg['property']['crumbs']:
        crumbs.append('<a href="%s" rel="noopener">%s</a>' % (u, t) if u else '<span>%s</span>' % t)
    crumbs.append('<span>%s</span>' % cfg['property']['property_name'])
    v['crumbs'] = '<i>/</i>'.join(crumbs)
    v['facts'] = ''.join('<div><dt>%s</dt><dd>%s</dd></div>' % (a, b) for a, b in cfg['property'].get('facts', []))
    # The agent's email is optional: with "agent_email" in the client file, the hero card and the
    # contact box get an email link and an Email button; without it they show phone and text only.
    em = cfg.get('agent', {}).get('agent_email', '')
    first = cfg.get('agent', {}).get('agent_first', '')
    v['agent_email_link'] = '<a class="xem" href="mailto:%s">%s</a>' % (em, em) if em else ''
    v['agent_email_ln'] = '<a href="mailto:%s">%s%s</a>' % (em, ICONS['icon_mail'], em) if em else ''
    v['agent_email_btn'] = '<a href="mailto:%s">Email</a>' % em if em else ''
    v['agent_email_btn_named'] = '<a href="mailto:%s">Email %s</a>' % (em, first) if em else ''
    return v


def transform(cfg, pk, s, skin_css, frags, drive_map):
    where = pk['slug']
    v = page_vals(cfg, pk)
    P = cfg['property']
    # head
    title = '%s, %s: %s | %s' % (P['property_name'], P['county_short'], pk['name'], cfg['office']['office_name'])
    s = re.sub(r'<title>.*?</title>', lambda m: '<title>%s</title>' % esc_text(title), s, count=1, flags=re.S)
    s = re.sub(r'<meta name="description" content="[^"]*">',
               lambda m: '<meta name="description" content="%s. %s">' % (P['property_name'], pk['desc']), s, count=1)
    s = re.sub(r'<link rel="icon"[^>]*>', '<link rel="icon" type="image/png" href="%s">' % cfg['brand']['favicon'], s, count=1)
    s = re.sub(r'<link rel="apple-touch-icon"[^>]*>', '<link rel="apple-touch-icon" href="%s">' % cfg['brand']['apple_touch_icon'], s, count=1)
    s = re.sub(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com/[^"]*">',
               '<link rel="stylesheet" href="%s">' % cfg['fonts_css'], s, count=1)
    # skin CSS
    mk = cfg['source']['skin_marker']
    i = s.find(mk)
    if i < 0:
        die(where + ': skin marker not found')
    j = s.find('</style>', i)
    s = s[:i] + skin_css.strip() + '\n' + s[j:]
    # header, hero, contact, footer
    s, n = re.subn(r'<header role="banner">.*?</header>', lambda m: fill(frags['header'], v).strip(), s, count=1, flags=re.S)
    if not n: die(where + ': header not found')
    s, n = re.subn(r'<p class="crumbs">.*?<p class="price">[^<]*</p>\s*</div>', lambda m: fill(frags['hero'], v).strip(), s, count=1, flags=re.S)
    if not n: die(where + ': hero not found')
    s, n = re.subn(r'<div class="box"><h4>Contact Agent</h4>.*?(?=<div class="box"><h4>)', lambda m: fill(frags['contact_agent'], v), s, count=1, flags=re.S)
    if not n: die(where + ': agent box not found')
    s, n = re.subn(r'<footer>.*?</footer>', lambda m: fill(frags['footer'], v).strip(), s, count=1, flags=re.S)
    if not n: die(where + ': footer not found')
    # page-specific edits (before the global ones, so their find text is the source wording)
    for e in cfg.get('edits', []):
        if e['page'] != where:
            continue
        if 'insert_before' in e:
            s = once(s, e['find'], (TOOL.parent.parent / cfg['skin'] / e['insert_before']).read_text(encoding='utf-8') + e['find'], where)
        else:
            s = once(s, e['find'], e['replace'], where)
    for a, b in cfg.get('replace_all', []):
        s = s.replace(a, b)
    # paths, Drive links, tracker
    for a, b in cfg['path_map']:
        s = s.replace(a, b)
    for a, b in drive_map.items():
        s = s.replace(a, b)
    s = re.sub(r'<script src="/hamele/track\.js[^"]*"[^>]*></script>\n?', '', s)
    if cfg.get('tracker'):
        s = once(s, '</body>', '<script src="%s" defer></script>\n</body>' % cfg['tracker'], where)
    if drive_map:
        ids = set(re.findall(r'drive\.google\.com/(?:uc\?export=download&amp;id=|drive/folders/|file/d/)([\w-]{20,})', s))
        stray = ids - set(drive_map.values())
        if stray:
            die('%s: Drive links not in this client\'s Drive map: %s' % (where, sorted(stray)))
    left = [m for m in re.findall(r'/hamele/[^"\' )]*', s)]
    if left:
        die('%s: source paths left: %s' % (where, sorted(set(left))[:6]))
    for bad in ('uchunting', 'UC Hunting', 'United Country', 'Travis', 'Hamele'):
        if bad.lower() in s.lower():
            k = s.lower().find(bad.lower())
            die('%s: %r still on the page: ...%s...' % (where, bad, s[max(0, k - 80):k + 80]))
    return s


def pages(cfg):
    skin = ROOT / cfg['skin']
    skin_css = (skin / 'skin.css').read_text(encoding='utf-8')
    frags = {k: (skin / (k + '.html')).read_text(encoding='utf-8') for k in ('header', 'hero', 'contact_agent', 'footer')}
    drive_map = {}
    if cfg.get('drive_links'):
        drive_map = json.load(open(ROOT / cfg['drive_links'], encoding='utf-8')).get('id_map_from_hamele', {})
    for pk in cfg['packages']:
        src = ROOT / cfg['source']['dir'] / pk['src'] / 'index.html'
        out = ROOT / cfg['dest']['dir'] / pk['slug'] / 'index.html'
        s = transform(cfg, pk, src.read_text(encoding='utf-8'), skin_css, frags, drive_map)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(s, encoding='utf-8')
        print('page:', out.relative_to(ROOT))


def load_client(path):
    """Read the client file. "{job}" anywhere in it stands for the job number, so the next
    listing only needs a new "job" value (plus its property, agent, and dest details)."""
    cfg = json.load(open(path, encoding='utf-8'))
    job = cfg.get('job', '')
    def fill(v):
        if isinstance(v, str): return v.replace('{job}', job)
        if isinstance(v, list): return [fill(x) for x in v]
        if isinstance(v, dict): return {fill(k): fill(x) for k, x in v.items()}
        return v
    return fill(cfg)

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('client')
    ap.add_argument('--pages-only', action='store_true', help='rebuild the HTML only (files and PDFs already done)')
    a = ap.parse_args()
    cfg = load_client(a.client)
    if not a.pages_only:
        copy_assets(cfg)
        archives(cfg)
        pdfs(cfg)
    pages(cfg)


if __name__ == '__main__':
    main()
