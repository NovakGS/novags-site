"""Patch the Thermal Survey listing graphic: headline and east-group tag.

Usage: python3 lg_thermal_fix.py <in.jpg> <out.jpg>
Old headline "Night Thermal Survey: 7 Likely Deer" and tag "5 Deer" become
"Night Thermal Survey: 7 Likely Sightings (5 to 7 Deer)" and "5 Sightings",
to match the map page. The original graphic was set in Roboto, which is not
installed here, so the redrawn headline and tag use Inter Bold.
"""
import sys
from PIL import Image, ImageDraw, ImageFont

BOLD = '/usr/share/fonts/opentype/inter/Inter-Bold.otf'
BG = (9, 12, 17)
TITLE = 'Night Thermal Survey: 7 Likely Sightings (5 to 7 Deer)'
TAG = '5 Sightings'

im = Image.open(sys.argv[1])
assert im.size == (2400, 2226), im.size
d = ImageDraw.Draw(im)

# Headline: cap top 2026, baseline 2066, left edge 52 in the original.
d.rectangle((40, 2012, 1995, 2086), fill=BG)
ft = ImageFont.truetype(BOLD, 55)
d.text((51, 2066), TITLE, font=ft, fill=(255, 255, 255), anchor='ls')
right = 51 + d.textlength(TITLE, font=ft)
assert right < 1990, right

# East-group tag: old box x 1758-1869, y 1070-1106, leader at x 1812-1813.
fg = ImageFont.truetype(BOLD, 30)
tw = d.textlength(TAG, font=fg)
cx = 1813
x0, x1 = round(cx - tw / 2 - 14), round(cx + tw / 2 + 14)
y0, y1 = 1070, 1111
d.rounded_rectangle((x0, y0, x1, y1), radius=7, fill=(5, 7, 10), outline=(255, 255, 255), width=2)
d.text((cx, 1098), TAG, font=fg, fill=(255, 255, 255), anchor='ms')

im.save(sys.argv[2], quality='keep', subsampling='keep')
print('title right edge', right, 'tag box', x0, x1)
