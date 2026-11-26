"""Edit text on page 1 of the Hunting & Recreation property overview PDF in place (no generator in the repo).

Relief now matches Essentials (164 ft, 921 to 1,085 ft on the 2024 bare-earth LiDAR), and the deer stat carries the
repeat-sighting caveat. The fonts are subset TrueType with all ASCII digits and letters, so same-length swaps keep layout.
Usage: python3 po_text_fix.py <in.pdf> <out.pdf>
"""
import sys
import pikepdf

REPS = [(b'(152 ft) Tj', b'(164 ft) Tj'),
        (b'(Of relief, 925 to 1,078 ft) Tj', b'(Of relief, 921 to 1,085 ft) Tj'),
        (b'The land rises 152 feet', b'The land rises 164 feet'),
        (b'(Likely deer, night flight) Tj', b'(Likely deer, may repeat) Tj')]

pdf = pikepdf.open(sys.argv[1])
c = pdf.pages[0].obj.Contents
done = set()
for st in (list(c) if isinstance(c, pikepdf.Array) else [c]):
    d = o = st.read_bytes()
    for a, b in REPS:
        if a in d:
            d = d.replace(a, b); done.add(a)
    if d != o:
        st.write(d)
assert len(done) == len(REPS), done
pdf.save(sys.argv[2])
print('ok')
