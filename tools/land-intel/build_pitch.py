#!/usr/bin/env python3
"""Novak|GS Land Intelligence - build a brokerage's private presentation page.

  python3 tools/land-intel/build_pitch.py tools/land-intel/clients/exit.json

Starts from an earlier presentation page (pitch.source, e.g. hamele/index.html) so the shared
look, the theme toggle, the pinned partner bar, the menu, and the map/thermal slider carry over.
Swaps in the client's logo pair, the "Prepared for" lines, and the page body
(pitch.main, with <!-- COMBINATION --> replaced by the source page's data-sources section,
then any pitch.replace [find, replace] pairs applied once each),
adds the client CSS, and drops the source page's visit tracker.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def die(msg):
    sys.exit('build_pitch: ' + msg)


def sub1(pattern, repl, s, what, flags=re.S, count=1):
    out, n = re.subn(pattern, lambda m: repl, s, count=count, flags=flags)
    if n == 0:
        die(what + ' not found')
    return out


def main():
    cfg = json.load(open(sys.argv[1], encoding='utf-8'))
    p = cfg['pitch']
    s = (ROOT / p['source']).read_text(encoding='utf-8')
    main_html = (ROOT / p['main']).read_text(encoding='utf-8')

    s = sub1(r'<title>.*?</title>', '<title>%s</title>' % p['title'], s, 'title')
    s = sub1(r'<meta name="description" content="[^"]*">', '<meta name="description" content="%s">' % p['description'], s, 'description')
    css = (ROOT / p['css']).read_text(encoding='utf-8').strip()
    s = s.replace('</style>', css + '\n</style>', 1)
    s = s.replace('/* travis */\n', '')

    # logo pair in the header, the pinned bar, and anywhere else the source used it
    logo = ('<a class="uch-logo" href="%s" target="_blank" rel="noopener" aria-label="%s"{tab}>'
            '<picture class="ucb-w"><source srcset="%s" type="image/webp"><img src="%s" alt="%s" width="%d" height="%d"></picture>'
            '<picture class="ucb-d"><source srcset="%s" type="image/webp"><img src="%s" alt="%s" width="%d" height="%d"></picture></a>') % (
        p['logo_url'], p['logo_label'],
        p['logo_dark_webp'], p['logo_dark_png'], p['logo_alt'], p['logo_w'], p['logo_h'],
        p['logo_light_webp'], p['logo_light_png'], p['logo_alt'], p['logo_w'], p['logo_h'])
    pat = r'<a class="uch-logo" href="[^"]*" target="_blank" rel="noopener" aria-label="[^"]*"( tabindex="-1")?><img class="ucb-w"[^>]*><img class="ucb-d"[^>]*></a>'
    s, n = re.subn(pat, lambda m: logo.replace('{tab}', m.group(1) or ''), s)
    if n != 2:
        die('expected 2 header logos, found %d' % n)
    s, n = re.subn(r'(<header class="uch" id="uch">.*?<span class="for"><i></i>Private Preview</span>)<p>.*?</p>',
                   lambda m: m.group(1) + '<p>' + p['for_lines'] + '</p>', s, count=1, flags=re.S)
    if not n: die('header lines not found')
    s, n = re.subn(r'(<div class="uch-mini" id="uch-mini".*?<span class="for"><i></i>Private Preview</span>)<p>.*?</p>',
                   lambda m: m.group(1) + '<p>' + p['mini_line'] + '</p>', s, count=1, flags=re.S)
    if not n: die('pinned bar line not found')

    # body
    comb = re.search(r'<section class="sec">\s*<p class="kick">The Combination</p>.*?</section>', s, re.S)
    if not comb:
        die('Combination section not found in the source page')
    if main_html.count('<!-- COMBINATION -->') != 1:
        die('pitch body needs one <!-- COMBINATION --> marker')
    main_html = main_html.replace('<!-- COMBINATION -->', comb.group(0))
    for find, repl in p.get('replace', []):
        if main_html.count(find) != 1:
            die('pitch.replace text found %d times: %s' % (main_html.count(find), find[:60]))
        main_html = main_html.replace(find, repl)
    s, n = re.subn(r'(<main class="hl-main">\n).*?(?=\n<footer>)', lambda m: m.group(1) + main_html.strip('\n') + '\n', s, count=1, flags=re.S)
    if not n: die('main not found')

    s = re.sub(r'<script src="/[a-z0-9-]+/track\.js[^"]*"[^>]*></script>\n?', '', s)
    s = s.replace('/* pinned UC banner:', '/* pinned partner banner:')
    for bad in p.get('must_not_contain', []):
        k = s.lower().find(bad.lower())
        if k >= 0:
            die('%r still on the page: ...%s...' % (bad, s[max(0, k - 80):k + 80]))
    out = ROOT / p['out']
    out.write_text(s, encoding='utf-8')
    print('pitch:', out.relative_to(ROOT))


if __name__ == '__main__':
    main()
