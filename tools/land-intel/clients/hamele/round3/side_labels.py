"""Draw the approximate side lengths on the Essentials overview map as plat-style labels that sit on each boundary line."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import sys
SRC = '/home/claude/r3/overview_base.jpg'
OUT = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/novags-site/hamele/li-img/map_overview.jpg'
base = Image.open(SRC).convert('RGBA')
# Squared flight boundary in image pixels (see essentials-move/slope_map.py)
X0, X1, Y0, Y1 = 104.7, 1252.0, 112.4, 1043.5
mx, my = (X0 + X1) / 2, (Y0 + Y1) / 2
FONT = ImageFont.truetype('/usr/share/fonts/opentype/inter/Inter-Bold.otf', 27)
ORANGE = (224, 112, 32, 255); INK = (28, 28, 28, 255); CARD = (255, 255, 255, 255)

def pill(text, cx, cy, vertical=False):
    d0 = ImageDraw.Draw(Image.new('RGBA', (10, 10)))
    tw = d0.textlength(text, font=FONT); asc, desc = FONT.getmetrics()
    padx, h = 15, 40
    w = int(tw + 2 * padx)
    tile = Image.new('RGBA', (w + 16, h + 16), (0, 0, 0, 0))
    sh = Image.new('RGBA', tile.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([8, 10, 8 + w, 10 + h], radius=h // 2, fill=(0, 0, 0, 110))
    sh = sh.filter(ImageFilter.GaussianBlur(3.5))
    tile = Image.alpha_composite(tile, sh)
    d = ImageDraw.Draw(tile)
    d.rounded_rectangle([8, 8, 8 + w, 8 + h], radius=h // 2, fill=CARD, outline=ORANGE, width=3)
    d.text((8 + w / 2, 8 + h / 2 + 1), text, font=FONT, fill=INK, anchor='mm')
    if vertical:
        tile = tile.rotate(90, expand=True, resample=Image.BICUBIC)
    base.alpha_composite(tile, (int(round(cx - tile.width / 2)), int(round(cy - tile.height / 2))))

NS, EW = '1,340± ft', '1,085± ft'
pill(NS, mx, Y0); pill(NS, mx, Y1)
pill(EW, X0, my, vertical=True); pill(EW, X1, my, vertical=True)
base.convert('RGB').save(OUT, quality=88, progressive=True, optimize=True)
print('saved', OUT)
