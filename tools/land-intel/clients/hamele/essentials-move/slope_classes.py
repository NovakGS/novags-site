import tifffile, numpy as np, sys
from shapely.geometry import Polygon
from shapely import contains_xy
from scipy import ndimage as ndi
a=tifffile.imread('/home/claude/ess2/dem/bare.tif').astype(float)
sx,sy=1.9992458793095798, 2.0008105670348253; X0,Y0=756146.8802273567, 496580.64710133435
U=1388.48/3600; FX=756210.7-58.8*U; FY=496510.6+73.4*U
def f2w(x,y): return (FX+x*U, FY-y*U)
oldq=Polygon([f2w(*p) for p in [(3540.8,2863.7),(3513.3,103.6),(65.0,43.2),(52.5,2912.4)]])
sq=Polygon([f2w(*p) for p in [(3527.0,2888.0),(3527.0,73.4),(58.8,73.4),(58.8,2888.0)]])
print('old area',oldq.area/43560,'sq area',sq.area/43560)
def horn(z,dx,dy):
    p=np.pad(z,1,mode='edge')
    gx=((p[:-2,2:]+2*p[1:-1,2:]+p[2:,2:])-(p[:-2,:-2]+2*p[1:-1,:-2]+p[2:,:-2]))/(8*dx)
    gy=((p[2:,:-2]+2*p[2:,1:-1]+p[2:,2:])-(p[:-2,:-2]+2*p[:-2,1:-1]+p[:-2,2:]))/(8*dy)
    return np.hypot(gx,gy)*100
bins=[0,6,12,20,35,1e9]
def classes(sl,dx,dy,x0,y0,poly,mode='center'):
    rows,cols=np.mgrid[0:sl.shape[0],0:sl.shape[1]]
    xs=x0+(cols+0.5)*dx; ys=y0-(rows+0.5)*dy
    ins=contains_xy(poly,xs,ys)
    cell=dx*dy/43560
    h,_=np.histogram(sl[ins],bins=bins)
    return [round(c*cell,2) for c in h], round(float(np.median(sl[ins])),2), round(ins.sum()*cell,2)
target=[2.88,8.13,11.39,10.04,1.11]
res=[]
for k in (1,2,3,4,5):
    if k==1: z=a; dx,dy=sx,sy
    else:
        H=(a.shape[0]//k)*k; W=(a.shape[1]//k)*k
        z=a[:H,:W].reshape(H//k,k,W//k,k).mean((1,3)); dx,dy=sx*k,sy*k
    for sig in (0,1,2,3):
        zz=ndi.gaussian_filter(z,sig) if sig else z
        sl=horn(zz,dx,dy)
        c,med,tot=classes(sl,dx,dy,X0,Y0,oldq)
        err=sum(abs(p-q) for p,q in zip(c,target))
        res.append((err,k,sig,c,med,tot))
for r in sorted(res)[:8]: print(r)
k,sig=2,1
H=(a.shape[0]//k)*k; W=(a.shape[1]//k)*k
z=ndi.gaussian_filter(a[:H,:W].reshape(H//k,k,W//k,k).mean((1,3)),sig)
sl=horn(z,sx*k,sy*k)
c,med,tot=classes(sl,sx*k,sy*k,X0,Y0,sq)
print('SQUARE classes',c,'median',med,'total',tot,'sum',round(sum(c),2))
rows,cols=np.mgrid[0:a.shape[0],0:a.shape[1]]
ins=contains_xy(sq,X0+(cols+0.5)*sx,Y0-(rows+0.5)*sy)
print('elev on square',a[ins].min(),a[ins].max())
import math
cs=list(sq.exterior.coords)
print('sides',[round(math.dist(cs[i],cs[i+1]),1) for i in range(4)],'perim',round(sq.length,1))
