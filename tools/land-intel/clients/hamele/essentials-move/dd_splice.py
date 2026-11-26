import pikepdf, sys
from reportlab.pdfbase.pdfmetrics import stringWidth
src, soils, out = sys.argv[1:4]
INSERT_AT = 2  # after page 2 (Zoning and land use), before build sites
pdf = pikepdf.open(src); sp = pikepdf.open(soils)
n_new = len(sp.pages)
for i, pg in enumerate(sp.pages):
    pdf.pages.insert(INSERT_AT + i, pg)
def edit(page, fn):
    ops = pikepdf.parse_content_stream(page)
    new = fn(ops)
    page.Contents = pdf.make_stream(pikepdf.unparse_content_stream(new))
def renum(num):
    def fn(ops):
        out = []
        for k, (operands, op) in enumerate(ops):
            if str(op) == 'Tj' and str(operands[0]).startswith('Page '):
                t = 'Page %d' % num
                # previous Tm sets the x position; right-align at 576
                for j in range(len(out) - 1, -1, -1):
                    if str(out[j][1]) == 'Tm':
                        a = list(out[j][0]); a[4] = 576 - stringWidth(t, 'Helvetica', 7.4)
                        out[j] = pikepdf.ContentStreamInstruction(a, pikepdf.Operator('Tm')); break
                out.append(pikepdf.ContentStreamInstruction([pikepdf.String(t)], op)); continue
            out.append(pikepdf.ContentStreamInstruction(operands, op))
        return out
    return fn
for idx, page in enumerate(pdf.pages):
    if INSERT_AT <= idx < INSERT_AT + n_new: continue
    edit(page, renum(idx + 1))
def sub(ops):
    out = []
    for operands, op in ops:
        if str(op) == 'Tj' and str(operands[0]) == 'Records, build sites, ponds, and what surrounds the property.':
            operands = [pikepdf.String('Records, soils, build sites, ponds, and what surrounds the property.')]
        out.append(pikepdf.ContentStreamInstruction(operands, op))
    return out
edit(pdf.pages[0], sub)
pdf.save(out, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
print('pages', len(pdf.pages))
