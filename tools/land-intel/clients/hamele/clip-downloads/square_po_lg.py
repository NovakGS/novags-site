# Square the Property Overview PDF maps and the Listing Graphics to the straight-edged rectangle
# (same 33.3 ac as the old slanted flight boundary). Removes the old baked-in dashed line, masks
# outside the rectangle, redraws deer rings that the old line crossed or that sit outside, and
# draws a new dashed line in the same style (dark casing, orange dashes, L-shaped corner dashes).
import sys, io, os, glob, zipfile
import numpy as np, pikepdf, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
INPAINT = cv2.INPAINT_TELEA
from PIL import Image, ImageDraw, ImageFilter
OLD = [(3540.8, 2863.7), (3513.3, 103.6), (65.0, 43.2), (52.5, 2912.4)]  # BR, TR, TL, BL (frame units)
RECT = (58.8, 73.4, 3527.0, 2888.0)                                    # x0, y0, x1, y1 (frame units)
RINGS = [(2949.3, 124.0), (3525.2, 550.2), (3556.5, 712.8), (873.5, 2942.3)]  # deer rings crossed by the old line or outside
ORANGE = np.array((232, 114, 27), np.float32)
CASE_HW, CASE_A = 6.25, 0.49      # casing half width (units), black opacity
DASH_HW, DASH, PERIOD = 3.5, 40.0, 60.0
RING_IN, RING_OUT, RING_EDGE = 21.6, 29.1, 31.3
OUT = '/home/claude/out/sq/'

def seg_dist(xx, yy, a, b):
    (x1, y1), (x2, y2) = a, b; dx, dy = x2-x1, y2-y1
    t = np.clip(((xx-x1)*dx+(yy-y1)*dy)/(dx*dx+dy*dy), 0, 1)
    return np.hypot(xx-(x1+t*dx), yy-(y1+t*dy))

def cov1d(n, a, b):
    i = np.arange(n, dtype=np.float32)
    return np.clip(np.minimum(i+1, b)-np.maximum(i, a), 0, 1)

def rect_cov(h, w, x0, y0, x1, y1):
    return cov1d(h, y0, y1)[:, None]*cov1d(w, x0, x1)[None, :]

def fit_ring(O, s, X, Y):
    h, w, _ = O.shape
    L = O.mean(-1); sat = O.max(-1)-O.min(-1); white = (L > 200) & (sat < 45)
    r0, r1 = 22.3*s, 29.0*s; best = None
    for dx in np.arange(-3, 3.01, 0.25):
        for dy in np.arange(-3, 3.01, 0.25):
            cx, cy = X*s+dx, Y*s+dy
            x0, x1 = int(max(0, cx-r1-3)), int(min(w, cx+r1+4)); y0, y1 = int(max(0, cy-r1-3)), int(min(h, cy+r1+4))
            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            d = np.hypot(xx+.5-cx, yy+.5-cy); band = (d >= r0) & (d <= r1)
            sc = (white[y0:y1, x0:x1] & band).sum()/max(1, band.sum())
            if best is None or sc > best[0]: best = (sc, cx, cy)
    return best

def annulus_cov(h, w, cx, cy, ra, rb, ss=4):
    y0, y1 = int(max(0, cy-rb-2)), int(min(h, cy+rb+3)); x0, x1 = int(max(0, cx-rb-2)), int(min(w, cx+rb+3))
    o = (np.arange(ss)+.5)/ss
    yy = (np.arange(y0, y1)[:, None]+o[None, :]).ravel(); xx = (np.arange(x0, x1)[:, None]+o[None, :]).ravel()
    d = np.hypot(xx[None, :]-cx, yy[:, None]-cy)
    m = ((d >= ra) & (d < rb)).astype(np.float32)
    m = m.reshape(y1-y0, ss, x1-x0, ss).mean((1, 3))
    return (slice(y0, y1), slice(x0, x1)), m

def ring_window(h, w, xc, yc, cx, cy, r):
    win = (slice(int(max(0, cy-r-2)), int(min(h, cy+r+3))), slice(int(max(0, cx-r-2)), int(min(w, cx+r+3))))
    return win, np.hypot(xc[win]-cx, yc[win]-cy)

def diffuse(sub, R, V, iters=400):
    # fill pixels R by repeated neighbour averaging, using R and the valid pixels V
    sub = sub.copy()
    if not R.any() or not V.any(): return sub
    sub[R] = sub[V].mean(0); ok = R | V
    for _ in range(iters):
        acc = np.zeros_like(sub); cnt = np.zeros(sub.shape[:2], np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            acc += np.roll(np.roll(sub, dy, 0), dx, 1)*np.roll(np.roll(ok, dy, 0), dx, 1)[..., None]
            cnt += np.roll(np.roll(ok, dy, 0), dx, 1)
        sub[R] = (acc/np.maximum(cnt, 1)[..., None])[R]
    return sub

def square_map(O, s, fill, deer=False, base=None, relief=None, lines=None, labels=False):
    O = O.astype(np.float32); h, w, _ = O.shape; O0 = O.copy()
    P = [(x*s, y*s) for x, y in OLD]; BR, TR, TL, BL = P
    X0, Y0, X1, Y1 = [v*s for v in RECT]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32); yc, xc = yy+.5, xx+.5
    hw = 10*s+1.0; e = 8*s+1.0
    near = (xc >= X0-e) & (xc <= X1+e) & (yc >= Y0-e) & (yc <= Y1+e)
    segs = (('top', TL, TR, True), ('bottom', BL, BR, True), ('left', TL, BL, False), ('right', TR, BR, False))
    dist = {nm: seg_dist(xc, yc, a, b) for nm, a, b, _ in segs}
    R = 10*s+2.0                                   # half width of the strip looked at around each old side
    rings = []
    if deer:
        for X, Y in RINGS:
            sc, cx, cy = fit_ring(O0, s, X, Y); rings.append((cx, cy)); print('  ring', (X, Y), 'white share %.2f' % sc)
    # 1) take the old line off. The old line was drawn hard-edged on whole pixels: a dark casing a few
    #    pixels thick with an opaque orange dash core. Find its exact rows/columns, undo the casing in the
    #    gaps, and mark the dash parts to rebuild from the clean base layer.
    corner = np.zeros((h, w), bool); LOST = np.zeros((h, w), bool)
    for name, a, b, horiz in segs:
        other = np.min([dist[k] for k, *_ in segs if k != name], axis=0)
        zone = near & (dist[name] <= R)
        corner |= zone & (other <= R+2)
        if horiz:
            pos = np.arange(int(max(0, min(a[0], b[0]))), int(min(w, max(a[0], b[0])+1)))
            lc = a[1]+(b[1]-a[1])*(pos+.5-a[0])/(b[0]-a[0]); lim = h
        else:
            pos = np.arange(int(max(0, min(a[1], b[1]))), int(min(h, max(a[1], b[1])+1)))
            lc = a[0]+(b[0]-a[0])*(pos+.5-a[1])/(b[1]-a[1]); lim = w
        bi = np.floor(lc).astype(int); K = int(R)+4; ks = np.arange(-K, K+1)
        across = bi[:, None]+ks[None, :]
        ok = (across >= 0) & (across < lim); acc = np.clip(across, 0, lim-1)
        along = np.repeat(pos[:, None], len(ks), 1)
        Yc, Xc = (acc, along) if horiz else (along, acc)
        S = O0[Yc, Xc]; L = S.mean(-1); n = len(pos)
        good = (ok & (other[Yc, Xc] > R+2)).all(1)
        rr = np.arange(n)
        c0 = S[rr, K]; rf0 = (S[rr, 0]+S[rr, -1])/2
        dash0 = np.linalg.norm(c0-ORANGE, axis=-1) < np.linalg.norm(c0-rf0*0.49, axis=-1)
        gap0 = good & ~(dash0 | np.roll(dash0, 1) | np.roll(dash0, -1) | np.roll(dash0, 2) | np.roll(dash0, -2))
        # fit band thickness H and phase (on gap positions) so the band's two hard edges line up best
        best = None
        for H in range(max(3, int(9*s)), int(16*s)+2):
            for dl in np.arange(0, 1, 0.05):
                r0 = np.floor(lc-H/2+dl).astype(int)-bi+K
                if r0.min() < 1 or (r0+H).max() >= len(ks): continue
                sc = (np.abs(L[rr, r0-1]-L[rr, r0])+np.abs(L[rr, r0+H]-L[rr, r0+H-1]))[gap0].mean()
                if best is None or sc > best[0]: best = (sc, H, dl)
        _, H, dl = best
        r0 = np.floor(lc-H/2+dl).astype(int)-bi+K
        # the old line's whole-pixel steps don't fall exactly where the model puts them: settle each
        # position on the shift (-1, 0, +1) whose two outer edges are strongest nearby
        es = []
        for tsh in (-1, 0, 1):
            r = np.clip(r0+tsh, 1, len(ks)-H-1)
            e_ = np.abs(L[rr, r-1]-L[rr, r])+np.abs(L[rr, r+H]-L[rr, r+H-1])
            es.append(np.convolve(e_, np.ones(5)/5, 'same'))
        r0 = np.clip(r0+np.argmax(np.array(es), 0)-1, 1, len(ks)-H-1)
        jj = np.arange(len(ks))[None, :]
        inband = (jj >= r0[:, None]) & (jj < (r0+H)[:, None])
        refm = ((jj >= r0[:, None]-3) & (jj < r0[:, None]-1)) | ((jj >= (r0+H+1)[:, None]) & (jj < (r0+H+3)[:, None]))
        ref = (S*refm[..., None]).sum(1)/refm.sum(1)[:, None]
        mid = S[rr, r0+H//2]
        dash = good & (np.linalg.norm(mid-ORANGE, axis=-1) < np.linalg.norm(mid-ref*0.49, axis=-1))
        dashA = np.zeros(n, bool); dashA[:] = (np.linalg.norm(mid-ORANGE, axis=-1) < np.linalg.norm(mid-ref*0.49, axis=-1))
        gapc = good & ~dashA
        tr = np.median((L/np.maximum(ref.mean(-1), 1)[:, None])[gapc[:, None] & inband & (jj > r0[:, None]) & (jj < (r0+H-1)[:, None])])
        dashL = dashA | np.roll(dashA, 1) | np.roll(dashA, -1)
        U = S/tr
        # rebuild the whole band plus two rows each side (JPEG carries the orange a pixel or two past
        # the hard edge), so nothing of the old line or its casing is left behind
        lost = (jj >= r0[:, None]-2) & (jj < (r0+H+2)[:, None])
        wr = lost & ok & near[Yc, Xc] & (other[Yc, Xc] > R+2)
        keep = wr & ~lost
        O[Yc[keep], Xc[keep]] = np.clip(U[keep], 0, 255)
        LOST[Yc[wr & lost], Xc[wr & lost]] = True
        print('  %-6s band %d px (phase %.2f, edge score %.0f)  casing transmits %.2f  dash share %.2f' % (name, H, dl, best[0], tr, dashA.mean()))
    # what the opaque dash cores hid (and the corner where two old sides cross): rebuild from the clean
    # base layer the graphic was made from, and carry the map's own lines across with a small inpaint
    dmin = np.min([dist[k] for k, *_ in segs], axis=0)
    LOST |= corner & (dmin <= R)
    lsum = sum(lines) if lines else np.zeros((h, w), np.float32)
    if labels:
        # contour labels (dark text on a white halo) that the new frame or the rebuilt strip would cut:
        # take them out whole rather than leave half a label at the edge
        halo = ((O0.min(-1) > 205) & (O0.max(-1)-O0.min(-1) < 35)).astype(np.uint8)
        fp = cv2.dilate(cv2.morphologyEx(halo, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))), np.ones((3, 3), np.uint8))
        n_, lab = cv2.connectedComponents(fp)
        dn = np.minimum(np.minimum(np.abs(xc-X0), np.abs(xc-X1)), np.minimum(np.abs(yc-Y0), np.abs(yc-Y1)))
        hit = np.unique(lab[(LOST | (near & (dn < 10*s))) & (fp > 0)]); k_ = 0
        for k in hit:
            if k == 0: continue
            cm = lab == k
            if cm.sum() < 6000*s*s: LOST |= cm; k_ += 1
        print('  labels taken out at the edge: %d' % k_)
    RINGM = np.zeros((h, w), bool)
    for cx, cy in rings:
        win, dd = ring_window(h, w, xc, yc, cx, cy, (RING_EDGE+3)*s)
        ann = (dd >= (RING_IN-2.5)*s) & (dd < (RING_EDGE+2.5)*s)
        RINGM[win] |= ann
    ring = near & (dmin > R+2) & (dmin < R+45) & (lsum < 0.02) & ~RINGM
    ys, xs = np.nonzero(ring); sel = slice(None, None, max(1, len(ys)//60000)); ys, xs = ys[sel], xs[sel]
    Rl = relief[ys, xs][:, None] if relief is not None else np.zeros((len(ys), 1), np.float32)
    Bfit = np.zeros_like(O)
    for c in range(3):
        bc = base[..., c]
        X = np.c_[bc[ys, xs], bc[ys, xs]*Rl[:, 0]/255, Rl[:, 0], np.ones(len(ys))]
        yv = O0[ys, xs, c]; co, *_ = np.linalg.lstsq(X, yv, rcond=None)
        r_ = np.abs(X@co-yv); k_ = r_ < np.percentile(r_, 80); co, *_ = np.linalg.lstsq(X[k_], yv[k_], rcond=None)
        rl = relief if relief is not None else 0.0
        Bfit[..., c] = co[0]*bc+co[1]*bc*rl/255+co[2]*rl+co[3]
    print('  base fit residual %.1f' % float(np.median(np.abs(Bfit[ys, xs]-O0[ys, xs]))))
    m8 = LOST.astype(np.uint8)*255; rad = max(3.0, 6*s)
    if lines:
        # map linework (contours) the base layer doesn't carry: draw it back from the same vector data,
        # in the colour and weight fitted to the graphic, and keep it out of the smooth correction below
        from cmask import fit_lines
        Bfit, pr = fit_lines(O0, Bfit, lines, near & ~LOST & (dmin < R+120))
        print('  lines', [('%.2f' % a, [int(round(v)) for v in C]) for a, C in pr])
        zone = cv2.dilate(m8, np.ones((int(30*s)+1, int(30*s)+1), np.uint8)) > 0
        bad = np.abs(O0-Bfit).max(-1) > 20     # where the drawn contours and the graphic's disagree by a pixel
        m8 = (LOST | (zone & ((lsum > 0.02) | bad))).astype(np.uint8)*255
    m8 = (m8 > 0) | (RINGM & (cv2.dilate(m8, np.ones((int(60*s)+1, int(60*s)+1), np.uint8)) > 0))
    m8 = m8.astype(np.uint8)*255                # the white rings are drawn back on top: keep them out of the fill
    F = O-Bfit
    for c in range(3):
        Fi = cv2.inpaint(np.ascontiguousarray(F[..., c]).astype(np.float32), m8, rad, INPAINT)
        O[..., c] = np.where(LOST, Bfit[..., c]+Fi, O[..., c])
    # 2) mask outside the rectangle (imagery kept under the new casing)
    M = rect_cov(h, w, X0-CASE_HW*s-0.25*s, Y0-CASE_HW*s-0.25*s, X1+CASE_HW*s+0.25*s, Y1+CASE_HW*s+0.25*s)[..., None]
    out = O*M+np.array(fill, np.float32)*(1-M)
    # 3) deer rings back on top (the line is drawn over them, as in the original)
    for cx, cy in rings:                       # whole, even past the frame, like the deer markers on the map page
        win, cw = annulus_cov(h, w, cx, cy, RING_IN*s, RING_OUT*s); out[win] = out[win]*(1-cw[..., None])+252.0*cw[..., None]
        win, co = annulus_cov(h, w, cx, cy, RING_OUT*s, RING_EDGE*s); out[win] = out[win]*(1-co[..., None])+8.0*co[..., None]
    # 4) new line: dark casing, then orange dashes with an L-shaped dash at every corner
    c = CASE_HW*s
    Cc = rect_cov(h, w, X0-c, Y0-c, X1+c, Y1+c)-rect_cov(h, w, X0+c, Y0+c, X1-c, Y1-c)
    out = out*(1-CASE_A*Cc[..., None])
    Mo = np.zeros((h, w), np.float32); dh = DASH_HW*s
    def put(x0, y0, x1, y1):
        ya, yb = int(max(0, np.floor(y0))), int(min(h, np.ceil(y1)+1)); xa, xb = int(max(0, np.floor(x0))), int(min(w, np.ceil(x1)+1))
        cv = cov1d(yb, y0, y1)[ya:yb, None]*cov1d(xb, x0, x1)[None, xa:xb]
        Mo[ya:yb, xa:xb] = np.maximum(Mo[ya:yb, xa:xb], cv)
    for horiz, fixed, a, b in ((True, Y0, X0, X1), (True, Y1, X0, X1), (False, X0, Y0, Y1), (False, X1, Y0, Y1)):
        L = b-a; dash = DASH*s; n = max(1, int(round((L-dash)/(PERIOD*s)))); p = (L-dash)/n
        for k in range(n+1):
            t0, t1 = a+k*p, a+k*p+dash
            if k == 0: t0 -= dh
            if k == n: t1 += dh
            if horiz: put(t0, fixed-dh, t1, fixed+dh)
            else: put(fixed-dh, t0, fixed+dh, t1)
    out = out*(1-Mo[..., None])+ORANGE*Mo[..., None]
    return np.clip(out+0.5, 0, 255).astype(np.uint8)

def bases(w, h):
    import render_frame as RR
    return {'aerial': np.asarray(RR.tiles_region('aerial', 0, 0, 3600, 2964, w, h)).astype(np.float32),
            'thermal': np.asarray(RR.tiles_region('thermal', 0, 0, 3600, 2964, w, h)).astype(np.float32),
            'elevation': np.asarray(RR.img_region('elevation.jpg', 0, 0, 3600, 2964, w, h)).astype(np.float32),
            'relief': np.asarray(RR.img_region('relief.jpg', 0, 0, 3600, 2964, w, h)).astype(np.float32)}
BASE_PO = {5: 'aerial', 7: 'relief', 8: 'thermal'}
BASE_LG = {'01': 'aerial', '02': 'relief', '03': 'elevation', '04': 'aerial', '05': 'thermal', '06': 'aerial'}

if __name__ == '__main__':
    os.makedirs(OUT+'lg', exist_ok=True)
    pdf = pikepdf.open('/home/claude/dl/orig/property_overview.pdf')
    for objnum, deer in ((5, False), (7, False), (8, True)):
        obj = pdf.get_object((objnum, 0))
        pim = pikepdf.PdfImage(obj).as_pil_image().convert('RGB'); w, h = pim.size
        print('PO', objnum, w, h)
        bs = bases(w, h)
        res = Image.fromarray(square_map(np.asarray(pim), w/3600.0, (255, 255, 255), deer, bs[BASE_PO[objnum]], bs['relief'].mean(-1)))
        buf = io.BytesIO(); res.save(buf, 'JPEG', quality=90, optimize=True)
        obj.write(buf.getvalue(), filter=pikepdf.Name.DCTDecode)
        obj.ColorSpace = pikepdf.Name.DeviceRGB; obj.BitsPerComponent = 8
        res.save(OUT+'po_%d.png' % objnum)
    pdf.save(OUT+'property_overview.pdf')
    for f in sorted(glob.glob('/home/claude/dl/lg/*.jpg')):
        im = Image.open(f).convert('RGB'); w, h = im.size; s = w/3600.0; mh = round(2964*s)
        print('LG', os.path.basename(f))
        arr = np.asarray(im).copy()
        bs = bases(w, mh)
        lines = None
        if os.path.basename(f).startswith('03'):
            from cmask import contour_masks
            lines = contour_masks(w, mh, 1.5*s/0.6667, 2.5*s/0.6667, 0.0, 0.5*s/0.6667)
        arr[:mh] = square_map(arr[:mh], s, (9, 12, 17), 'Thermal' in f, bs[BASE_LG[os.path.basename(f)[:2]]], bs['relief'].mean(-1), lines, labels=lines is not None)
        Image.fromarray(arr).save(OUT+'lg/'+os.path.basename(f), 'JPEG', quality=92, optimize=True)
    zp = OUT+'listing_graphics.zip'
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_STORED) as z:
        for f in sorted(glob.glob(OUT+'lg/*.jpg')): z.write(f, os.path.basename(f))
    print('zip', os.path.getsize(zp))
