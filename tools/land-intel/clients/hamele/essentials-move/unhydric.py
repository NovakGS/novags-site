"""Remove the hydric-soil indicator overlay from hamele/li-img/map_water.jpg.
Relief under the overlay is taken from map_ponds/map_zoning (same relief base) where those are plain;
elsewhere the overlay is unblended with alpha/color fitted on the pixels where the relief is known."""
import sys
from PIL import Image
import numpy as np
from scipy import ndimage as ndi
L='/home/claude/novags-site/hamele/li-img/'
w=np.asarray(Image.open('/home/claude/ess2/w/orig_map_water.jpg').convert('RGB')).astype(float)
P=np.asarray(Image.open(L+'map_ponds.jpg').convert('RGB')).astype(float)
Z=np.asarray(Image.open(L+'map_zoning.jpg').convert('RGB')).astype(float)
def isgray(m,t=2): return (np.abs(m[...,0]-m[...,2])<t)&(np.abs(m[...,0]-m[...,1])<t)
r=w[...,0]; d1=w[...,1]-r; d2=w[...,2]-r
H,W=r.shape
ins=np.zeros((H,W),bool); ins[121:1037,111:1246]=True      # inside the dashed frame line
edge=np.zeros((H,W),bool); edge[104:1050,96:1260]=True; edge&=~ins  # the frame line band
# chroma decomposition: green fill (60,8), hydric (13,22)
M=np.linalg.inv(np.array([[60.0,13.0],[8.0,22.0]]))
u=M[0,0]*d1+M[0,1]*d2; v=M[1,0]*d1+M[1,1]*d2
v=np.clip(v,0,1)
v[(~ins)]=0
v[v<0.04]=0
core=v>0.3
lab,n=ndi.label(core)
sizes=ndi.sum(core,lab,range(1,n+1))
core=np.isin(lab,1+np.nonzero(sizes>=200)[0])
zone=ndi.binary_dilation(core,iterations=4)
v[~zone]=0
print('hydric components kept',int((sizes>=200).sum()),'of',n)
# known relief
known=np.full((H,W),np.nan)
gp=isgray(P); gz=isgray(Z)
known[gz]=Z[...,0][gz]
known[gp]=P[...,0][gp]
# fit a, C on pure hydric pixels with known relief
pure=(np.abs(d1-13)<1.5)&(np.abs(d2-22)<1.5)&ins&~np.isnan(known)
g=known[pure]
coef=[]
for c in range(3):
    A=np.vstack([g,np.ones_like(g)]).T
    (s,k),*_=np.linalg.lstsq(A,w[...,c][pure],rcond=None)
    coef.append((s,k))
a=1-np.mean([s for s,k in coef]); C=np.array([k for s,k in coef])/a
print('pure n',pure.sum(),'slopes',[round(s,4) for s,k in coef],'a',round(a,4),'C',C.round(1))
res=w[...,0][pure]-(a*C[0]+(1-a)*g); print('fit resid r',res.std().round(2))
# reject known relief that does not fit the blend model under hydric pixels (map labels, markers)
pred=a*C.mean()+(1-a)*known
bad=(v>0.5)&(np.abs(w.mean(-1)-pred)>12)
bad=ndi.binary_dilation(bad,iterations=3)&(v>0)
known[bad]=np.nan
print('rejected known px',bad.sum())
# relief estimate for every pixel needing it
gest=known.copy()
need=(v>0)&np.isnan(gest)
unb=(w.mean(-1)-a*C.mean())/(1-a)          # unblend assuming full coverage
purelike=(v>0.9)&(u<0.05)
gest[need&purelike]=unb[need&purelike]
# remaining (mixed) pixels: nearest estimate
miss=np.isnan(gest)
idx=ndi.distance_transform_edt(miss,return_distances=False,return_indices=True)
gfill=gest[idx[0],idx[1]]
out=w-(v*a)[...,None]*(C[None,None,:]-gfill[...,None])
# frame line band: where the water map has hydric color near the line, use the ponds map pixel (same line drawing)
band=edge&((d2>8)&(d1<0.8*d2+3))&ndi.binary_dilation(zone,iterations=12)
bandd=ndi.binary_dilation(band,iterations=2)&edge
out[bandd]=P[bandd]
print('band px',bandd.sum(),'changed px',(np.abs(out-w).max(-1)>1).sum())
np.save('/home/claude/ess2/w/out_water.npy',out)
Image.fromarray(np.clip(out+0.5,0,255).astype(np.uint8)).save('/home/claude/ess2/w/water_nohyd_full.png')
# legend: drop the "Hydric soil indicator" row (4 rows -> 3, same box as the 3-row pond map legend)
o=np.clip(out+0.5,0,255).astype(np.uint8)
Wi=w.astype(np.uint8)
o[1035:1106,8:448]=Wi[1004:1075,8:448]
o[1003:1035,0:460]=P.astype(np.uint8)[1003:1035,0:460]
Image.fromarray(o).save('/home/claude/ess2/w/map_water_new.png')
# flatten JPEG ringing left in the moved legend gap row
o=np.asarray(Image.open('/home/claude/ess2/w/map_water_new.png')).copy()
blk=o[1073:1081,12:444]; msk=blk.mean(-1)>238; blk[msk]=251; o[1073:1081,12:444]=blk
Image.fromarray(o).save('/home/claude/ess2/w/map_water_new.png')
Image.fromarray(o).save('/home/claude/novags-site/hamele/li-img/map_water.jpg',quality=88,progressive=True,optimize=True)
