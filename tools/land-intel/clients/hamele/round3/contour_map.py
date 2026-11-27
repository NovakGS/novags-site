"""Essentials contour map: 2-ft contours from the 2024 bare-earth LiDAR, 10-ft index contours labeled,
over the shaded relief with a soft elevation tint, in the same frame as the other Essentials maps."""
import numpy as np, tifffile, sys
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import patheffects as pe
from matplotlib.colors import LinearSegmentedColormap
OUT = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/novags-site/hamele/li-img/map_contours.jpg'
F = np.asarray(Image.open('/home/claude/r3/overview_base.jpg').convert('RGB')).astype(float)
relief = np.load('/home/claude/ess2/slope/relief.npy')
a = tifffile.imread('/home/claude/ess2/dem/bare.tif').astype(float)
sx, sy = 1.9992458793095798, 2.0008105670348253; X0, Y0 = 756146.8802273567, 496580.64710133435
U = 1388.48 / 3600; FX = 756210.7 - 58.8 * U; FY = 496510.6 + 73.4 * U
y0, y1, x0, x1 = 112, 1043, 104, 1251
iy0, iy1, ix0, ix1 = y0 + 3, y1 - 2, x0 + 3, x1 - 2
h, w = iy1 - iy0, ix1 - ix0
py, px = np.mgrid[iy0:iy1, ix0:ix1].astype(float)
fx = (px - 85.23) / 0.33081; fy = (py - 88.12) / 0.33081
X = FX + fx * U; Y = FY - fy * U
col = (X - X0) / sx - 0.5; row = (Y0 - Y) / sy - 0.5
z = ndi.map_coordinates(ndi.gaussian_filter(a, 1.2), [row, col], order=3, mode='nearest')
print('elev', z.min(), z.max())
# soft hypsometric tint over the relief
cm = LinearSegmentedColormap.from_list('hyp', ['#6f9a5a', '#a9c27d', '#e3dba0', '#d9b27c', '#b7825a'])
t = (z - z.min()) / (z.max() - z.min())
tint = cm(t)[..., :3] * 255
g = relief[iy0:iy1, ix0:ix1][..., None]
rgb = 0.58 * g + 0.42 * tint
rgb = 0.85 * rgb + 0.15 * 255  # lift so the contour lines read
fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
ax = fig.add_axes([0, 0, 1, 1]); ax.axis('off')
ax.imshow(np.clip(rgb, 0, 255).astype(np.uint8), extent=(0, w, h, 0), interpolation='nearest')
xs = np.arange(w) + 0.5; ys = np.arange(h) + 0.5
lo = int(np.floor(z.min() / 2) * 2); hi = int(np.ceil(z.max() / 2) * 2)
minor = [v for v in range(lo, hi + 1, 2) if v % 10]
major = [v for v in range(lo, hi + 1, 2) if v % 10 == 0]
ax.contour(xs, ys, z, levels=minor, colors='#6b4423', linewidths=0.55, alpha=0.55)
cs = ax.contour(xs, ys, z, levels=major, colors='#4a2a10', linewidths=1.5, alpha=0.95)
lab = ax.clabel(cs, levels=[v for v in major if v % 20 == 0], fmt=lambda v: '%d' % v, fontsize=15, inline=True,
                inline_spacing=6, colors='#3a2008')
for tx in lab:
    tx.set_fontweight('bold'); tx.set_fontfamily('DejaVu Sans')
    tx.set_path_effects([pe.withStroke(linewidth=3, foreground=(1, 1, 1, 0.85))])
ax.set_xlim(0, w); ax.set_ylim(h, 0)
fig.canvas.draw()
inner = np.asarray(fig.canvas.buffer_rgba())[..., :3].astype(float)
plt.close(fig)
O = F.copy()
O[iy0:iy1, ix0:ix1] = inner
# new legend in place of the overview legend
bg = np.median(F[1100:1150, 600:700].reshape(-1, 3), 0)
O[1058:1155, 0:420] = bg
img = Image.fromarray(np.clip(O, 0, 255).astype(np.uint8))
d = ImageDraw.Draw(img)
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 19)
rows = [('Flight boundary', 'b'), ('2-ft contour', 'm'), ('10-ft contour (labeled every 20 ft)', 'M')]
pitch = 26; tw = max(d.textlength(t, font=font) for t, _ in rows)
bx0 = 9; bx1 = int(81 + tw + 12); by1 = 1149; by0 = by1 - (len(rows) * pitch + 14)
d.rounded_rectangle([bx0, by0, bx1, by1], radius=5, fill=(251, 251, 251), outline=(160, 160, 160), width=2)
for i, (tx, k) in enumerate(rows):
    cy = by0 + 7 + pitch * i + pitch // 2
    if k == 'b': d.line([23, cy, 66, cy], fill=(224, 112, 32), width=5)
    elif k == 'm': d.line([23, cy, 66, cy], fill=(150, 118, 92), width=2)
    else: d.line([23, cy, 66, cy], fill=(74, 42, 16), width=4)
    d.text((81, cy), tx, font=font, fill=(0, 0, 0), anchor='lm')
img.save(OUT, quality=88, progressive=True, optimize=True)
print('saved', OUT, img.size, 'levels', lo, hi, len(minor), len(major))
