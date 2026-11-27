"""Make the deer count on the Hunting & Recreation property overview PDF read as sightings (5 to 7 deer), in place.

Page 1: the stat label under "7". Page 2: the "7 likely" paragraph in Night Thermal Survey, rewrapped to the same
three lines so nothing below it moves. Fonts are subset TrueType with all ASCII letters and digits.
Usage: python3 po_deer_fix.py <in.pdf> <out.pdf>
"""
import sys
import pikepdf

REPS = {
    0: [(b'(Likely deer, may repeat) Tj', b'(Likely sightings, 5-7 deer) Tj')],
    1: [(b"(7 likely deer) Tj /F3+0 9.6 Tf 13.2 TL (: a pair at the south end, and a group on the east) Tj T* "
         b"(side seen over about five minutes, which may include the) Tj T* "
         b"(same animals moving, so that group is between 3 and 5 deer.) Tj T*",
         b"(7 likely sightings) Tj /F3+0 9.6 Tf 13.2 TL (: a pair at the south end and 5 on the east) Tj T* "
         b"(side over about five minutes. Those 5 may repeat the same) Tj T* "
         b"(deer, so 5 to 7 deer in all.) Tj T*")],
}

pdf = pikepdf.open(sys.argv[1])
for pg, reps in REPS.items():
    c = pdf.pages[pg].obj.Contents
    done = set()
    for st in (list(c) if isinstance(c, pikepdf.Array) else [c]):
        d = o = st.read_bytes()
        for a, b in reps:
            if a in d:
                d = d.replace(a, b); done.add(a)
        if d != o:
            st.write(d)
    assert len(done) == len(reps), (pg, done)
pdf.save(sys.argv[2])
print('ok')
