import numpy as np, tifffile
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi
L='/home/claude/novags-site/hamele/li-img/'
W=np.asarray(Image.open(L+'map_water.jpg').convert('RGB')).astype(float)
relief=np.load('/home/claude/ess2/slope/relief.npy')
a=tifffile.imread('/home/claude/ess2/dem/bare.tif').astype(float)
sx,sy=1.9992458793095798, 2.0008105670348253; X0,Y0=756146.8802273567, 496580.64710133435
k,sig=2,1
H=(a.shape[0]//k)*k; Wd=(a.shape[1]//k)*k
z=ndi.gaussian_filter(a[:H,:Wd].reshape(H//k,k,Wd//k,k).mean((1,3)),sig)
dx,dy=sx*k,sy*k
p=np.pad(z,1,mode='edge')
gx=((p[:-2,2:]+2*p[1:-1,2:]+p[2:,2:])-(p[:-2,:-2]+2*p[1:-1,:-2]+p[2:,:-2]))/(8*dx)
gy=((p[2:,:-2]+2*p[2:,1:-1]+p[2:,2:])-(p[:-2,:-2]+2*p[:-2,1:-1]+p[:-2,2:]))/(8*dy)
sl=np.hypot(gx,gy)*100
U=1388.48/3600; FX=756210.7-58.8*U; FY=496510.6+73.4*U
y0,y1,x0,x1=112,1043,104,1251
iy0,iy1,ix0,ix1=y0+3,y1-2,x0+3,x1-2
py,px=np.mgrid[iy0:iy1,ix0:ix1].astype(float)
fx=(px-85.23)/0.33081; fy=(py-88.12)/0.33081
X=FX+fx*U; Y=FY-fy*U
col=(X-X0)/dx-0.5; row=(Y0-Y)/dy-0.5
s=ndi.map_coordinates(sl,[row,col],order=1,mode='nearest')
bins=[6,12,20,35]
cls=np.digitize(s,bins)
# remove specks smaller than ~25 px by majority of neighbors
for _ in range(2):
    out=cls.copy()
    for c in range(5):
        m=cls==c
        lab,n=ndi.label(m)
        if n==0: continue
        sz=ndi.sum(m,lab,range(1,n+1))
        small=np.isin(lab,1+np.where(sz<25)[0])
        if small.any():
            # replace with mode of 5x5 neighborhood excluding this class
            cnt=np.stack([ndi.uniform_filter((cls==j).astype(float),7) if j!=c else np.zeros(cls.shape) for j in range(5)],-1)
            out[small]=cnt.argmax(-1)[small]
    cls=out
colors=np.array([[26,152,80],[145,207,96],[254,224,139],[252,141,89],[215,48,39]],float)
alpha=0.5
g=relief[iy0:iy1,ix0:ix1][...,None]
rgb=(1-alpha)*g+alpha*colors[cls]
# thin class edges slightly darker for legibility
edge=np.zeros(cls.shape,bool)
edge[1:,:]|=cls[1:,:]!=cls[:-1,:]; edge[:,1:]|=cls[:,1:]!=cls[:,:-1]
rgb[edge]=rgb[edge]*0.9
O=W.copy()
O[iy0:iy1,ix0:ix1]=rgb
# clear old legend outside the interior
leg_old=np.zeros(W.shape[:2],bool); leg_old[1030:1150,0:460]=True
inter=np.zeros(W.shape[:2],bool); inter[iy0:iy1,ix0:ix1]=True
bg=np.median(W[1100:1150,600:700].reshape(-1,3),0)
O[leg_old&~inter]=bg
# frame line rows/cols bordering legend: restore from W where frame line (orange) lies in cleared area
orange=(W[...,0]-W[...,2]>60)
O[leg_old&~inter&orange]=W[leg_old&~inter&orange]
S=np.asarray(Image.open(L+'map_soils.jpg').convert('RGB')).astype(float)
O[iy1:1052,180:470]=S[iy1:1052,180:470]
img=Image.fromarray(np.clip(O,0,255).astype(np.uint8))
d=ImageDraw.Draw(img)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',19)
labs=['Under 6% (flat to gentle)','6 to 12% (moderate)','12 to 20% (moderately steep)','20 to 35% (steep)','35% and over (very steep)']
pitch=30; n=len(labs)
tw=max(d.textlength(t,font=font) for t in labs)
bx0=9; bx1=int(81+tw+12); by1=1146; by0=by1-(n*pitch+20)
d.rounded_rectangle([bx0,by0,bx1,by1],radius=5,fill=(251,251,251),outline=(160,160,160),width=2)
for i,(t,c) in enumerate(zip(labs,colors)):
    cy=by0+10+pitch*i+pitch//2
    d.rectangle([23,cy-7,64,cy+7],fill=tuple(int(v) for v in (0.5*235+0.5*c)),outline=(34,34,34),width=2)
    d.text((81,cy),t,font=font,fill=(0,0,0),anchor='lm')
img.save('/home/claude/ess2/slope/map_slope.png')
img.save(L+'map_slope.jpg',quality=88,progressive=True,optimize=True)
# report class acres within image for sanity
pa=(U/0.33081)**2/43560
print('img class acres',[round((cls==c).sum()*pa,2) for c in range(5)],'total',round(cls.size*pa,2))
