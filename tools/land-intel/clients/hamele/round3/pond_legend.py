"""Round 3: relabel the pond map legend in plain words (same box, same size).
Reads the committed map_ponds.jpg (round-2 version) and rewrites its three legend labels."""
from PIL import Image, ImageDraw, ImageFont
import sys
SRC = sys.argv[1]; OUT = sys.argv[2]
im = Image.open(SRC).convert('RGB'); d = ImageDraw.Draw(im)
d.rectangle((77, 1046, 462, 1131), fill=(251, 251, 251))   # old label text area inside the legend box
f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 20)
asc = f.getmetrics()[0]
for txt, base in [('Land draining to the site', 1065), ('Pond with an 8 ft dam', 1095), ('Dam site', 1125)]:
    d.text((81, base - asc), txt, font=f, fill=(0, 0, 0))
im.save(OUT, quality=92)
