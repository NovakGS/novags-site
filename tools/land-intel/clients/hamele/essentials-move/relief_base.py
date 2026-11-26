import numpy as np
from PIL import Image
from scipy import ndimage as ndi
L='/home/claude/novags-site/hamele/li-img/'
W=np.asarray(Image.open(L+'map_water.jpg').convert('RGB')).astype(float)
P=np.asarray(Image.open(L+'map_ponds.jpg').convert('RGB')).astype(float)
Z=np.asarray(Image.open(L+'map_zoning.jpg').convert('RGB')).astype(float)
ch=lambda a:a.max(2)-a.min(2)
cw,cp,cz=ch(W),ch(P),ch(Z)
y0,y1,x0,x1=112,1043,104,1251
inside=np.zeros(cw.shape,bool); inside[y0+3:y1-2,x0+3:x1-2]=True
g0=(cw>25)&inside
lab,n=ndi.label(g0); sz=ndi.sum(g0,lab,range(1,n+1))
big=np.isin(lab,1+np.where(sz>500)[0])
green=ndi.binary_dilation(big,iterations=3)&inside&(cw>6)
known=green&(cw>40)&(cp<6)
fit=[]
for c in range(3):
    w=W[...,c][known]; g=P[...,c][known]
    A=np.vstack([g,np.ones_like(g)]).T
    (s,i),*_=np.linalg.lstsq(A,w,rcond=None)
    fit.append((s,i)); print(c,'slope',s,'int',i,'C',i/(1-s),'resid',np.std(w-(s*g+i)))
a=1-np.mean([f[0] for f in fit]); C=np.array([f[1] for f in fit])/a
print('a',a,'C',C)
# gray estimate from unblend (use mean of channels)
apx=np.clip((W[...,1]-(W[...,0]+W[...,2])/2)/(C[1]-(C[0]+C[2])/2),0,a)
est=np.stack([(W[...,c]-apx*C[c])/(1-apx) for c in range(3)],-1).mean(-1)
base=W.mean(-1)
out=base.copy()
def consistent(K):
    pred=np.stack([(1-a)*K[...,c]+a*C[c] for c in range(3)],-1)
    blend=np.abs(pred-W).mean(-1)
    # on light-tint edge pixels alpha smaller; accept if gray K close to est too
    return (blend<14)|(np.abs(K.mean(-1)-est)<10)
gp=green&(cp<6)&consistent(P); gz=green&(cz<6)&~gp&consistent(Z)
out[gp]=P[...,:].mean(-1)[gp]
out[gz]=Z.mean(-1)[gz]
nei=green&~gp&~gz
out[nei]=est[nei]
# check: where known, compare est vs ponds
k2=green&(cp<6)&(cw>40)
print('unblend err on known',np.mean(np.abs(est[k2]-P.mean(-1)[k2])))
ring=(ndi.binary_dilation(big,iterations=6)&~ndi.binary_erosion(big,iterations=4))&inside
m=(~ring).astype(float)
num=ndi.gaussian_filter(out*m,4.0); den=ndi.gaussian_filter(m,4.0)
fill=num/np.maximum(den,1e-6)
out[ring]=fill[ring]
out=np.clip(out,0,255)
np.save('relief.npy',out)
Image.fromarray(out.astype(np.uint8)).save('relief.png')
print('neither px',nei.sum())
