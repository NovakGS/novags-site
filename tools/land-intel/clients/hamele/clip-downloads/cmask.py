import sys; sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw
import render_frame as Rn
def contour_masks(w,h,wm,wi,dx=0.0,dy=0.0,ss=4):
    """coverage masks (0..1) of the minor and index contours at w x h for the whole frame"""
    out=[]
    for kind,wd in (('m',wm),('i',wi)):
        L=Image.new('L',(w*ss,h*ss),0); dr=ImageDraw.Draw(L); k=w*ss/Rn.VW; wpx=max(1,int(round(wd*ss)))
        for f in Rn.V['contours']:
            if f[0]!=kind: continue
            for sub in Rn.parse(f[1]):
                P=[(x*k+dx*ss,y*k+dy*ss) for x,y in sub]; dr.line(P,fill=255,width=wpx,joint='curve')
        out.append(np.asarray(L.resize((w,h),Image.BOX),np.float32)/255)
    return out
def fit_lines(O, B, masks, sel):
    """O ~ B*(1-sum a_k M_k) + sum a_k C_k M_k on pixels sel; returns (model, params)"""
    Bm = B.copy(); params=[]
    for M in masks:
        others = sum(m for m in masks if m is not M) if len(masks)>1 else 0*M
        p = sel & (M > 0.5) & (others < 0.02)
        ys, xs = np.nonzero(p); ys, xs = ys[::max(1,len(ys)//40000)], xs[::max(1,len(ys)//40000)]
        m = M[ys, xs]
        A = np.zeros((len(ys)*3, 4)); y = np.zeros(len(ys)*3)
        for c in range(3):
            A[c::3, 0] = -m*B[ys, xs, c]; A[c::3, 1+c] = m; y[c::3] = O[ys, xs, c]-B[ys, xs, c]
        co, *_ = np.linalg.lstsq(A, y, rcond=None); a = co[0]; C = co[1:]/max(a, 1e-3)
        params.append((a, C)); Bm = Bm*(1-a*M[..., None])+a*C*M[..., None]
    return Bm, params
