# Square the seven report maps (li-img) to a straight-edged rectangle of the same area as the
# old slanted flight boundary. Removes the old baked-in boundary line where it falls inside the
# new rectangle, masks outside it, and draws a new dashed line in the same style.
import numpy as np, sys, os
from PIL import Image, ImageDraw
sys.path.insert(0,'/tmp/pk')
D='/home/claude/novags-site/hamele/li-img/'
ORIG='/tmp/pk/li-orig/'
BG=235.0
W,H=1360,1155
LIA=0.33081;LIBX=85.23;LIBY=88.12
RECT_F=(58.8,73.4,3527.0,2888.0)           # frame units x0,y0,x1,y1
X0,Y0=LIA*RECT_F[0]+LIBX,LIA*RECT_F[1]+LIBY
X1,Y1=LIA*RECT_F[2]+LIBX,LIA*RECT_F[3]+LIBY
OLD=[(1256.6,1035.5),(1247.5,122.4),(106.7,102.4),(102.6,1051.6)]  # BR,TR,TL,BL li px
FR={'map_overview':(9,1066,345,1145),'map_water':(9,1005,447,1145),'map_soils':(9,945,174,1145),
'map_zoning':(9,1005,377,1145),'map_build':(9,1036,335,1145),'map_ponds':(9,1036,467,1145),'map_steward':(9,1066,406,1145)}
SS=4
def seg_dist(xx,yy,a,b):
    (x1,y1),(x2,y2)=a,b; dx,dy=x2-x1,y2-y1
    t=np.clip(((xx-x1)*dx+(yy-y1)*dy)/(dx*dx+dy*dy),0,1)
    return np.hypot(xx-(x1+t*dx),yy-(y1+t*dy))
yy,xx=np.mgrid[0:H,0:W].astype(float)
dold=np.min([seg_dist(xx,yy,OLD[i],OLD[(i+1)%4]) for i in range(4)],axis=0)
inside=(xx>=X0-0.5)&(xx<=X1+0.5)&(yy>=Y0-0.5)&(yy<=Y1+0.5)
LINE_HW=5.0  # old line half width incl. white casing and jpeg halo
fillm=(dold<=LINE_HW)&inside
def lerp_line(a,b,t): return a+(b-a)*t
def shift_fill(O):
    # inpaint the old line band: mirror across both band edges and cross-fade, so both seams match
    O=O.copy(); hw=LINE_HW
    BR,TR,TL,BL=OLD
    specs=[('top',TL,TR),('bottom',BL,BR),('left',TL,BL),('right',TR,BR)]
    for name,a,b in specs:
        if name in('top','bottom'):
            m=inside&(seg_dist(xx,yy,a,b)<=hw)
            ys,xs=np.nonzero(m)
            if not len(ys): continue
            t=(xs-a[0])/(b[0]-a[0]); lc=a[1]+(b[1]-a[1])*t
            sgn=1 if name=='top' else -1
            sv=(ys-lc)*sgn                       # +inward
            inn=np.round(lc+sgn*(2*hw-sv)).astype(int); out=np.round(lc-sgn*(2*hw+sv)).astype(int)
            inn=np.clip(inn,0,H-1); out=np.clip(out,0,H-1)
            w=np.clip((sv+hw)/(2*hw),0,1)[:,None]
            O[ys,xs]=O[inn,xs]*w+O[out,xs]*(1-w)
        else:
            m=inside&(seg_dist(xx,yy,a,b)<=hw)
            ys,xs=np.nonzero(m)
            if not len(ys): continue
            t=(ys-a[1])/(b[1]-a[1]); lc=a[0]+(b[0]-a[0])*t
            sgn=1 if name=='left' else -1
            sv=(xs-lc)*sgn
            inn=np.clip(np.round(lc+sgn*(2*hw-sv)).astype(int),0,W-1); out=np.clip(np.round(lc-sgn*(2*hw+sv)).astype(int),0,W-1)
            w=np.clip((sv+hw)/(2*hw),0,1)[:,None]
            O[ys,xs]=O[ys,inn]*w+O[ys,out]*(1-w)
    return O
def rect_mask(x0,y0,x1,y1):
    im=Image.new('L',(W*SS,H*SS),0);ImageDraw.Draw(im).rectangle([(x0+.5)*SS,(y0+.5)*SS,(x1+.5)*SS,(y1+.5)*SS],fill=255)
    return np.asarray(im.resize((W,H),Image.BOX)).astype(float)/255
def rrect(x0,y0,x1,y1,r):
    im=Image.new('L',(W*SS,H*SS),0)
    ImageDraw.Draw(im).rounded_rectangle([x0*SS,y0*SS,(x1+1)*SS-1,(y1+1)*SS-1],radius=r*SS,fill=255)
    return np.asarray(im.resize((W,H),Image.BOX)).astype(float)/255
ORANGE=(232,113,26)
def draw_line(base):
    # white casing ~7.5 px, orange dashes ~3 px, dash 25 / gap 12, drawn supersampled
    im=Image.fromarray(np.clip(base,0,255).astype(np.uint8)).convert('RGBA')
    L=Image.new('RGBA',(W*SS,H*SS),(0,0,0,0)); d=ImageDraw.Draw(L)
    P=[(X1,Y1),(X1,Y0),(X0,Y0),(X0,Y1),(X1,Y1)]
    S=lambda p:((p[0]+.5)*SS,(p[1]+.5)*SS)
    hw=3.75; d.rectangle([(X0+.5-hw)*SS,(Y0+.5-hw)*SS,(X1+.5+hw)*SS,(Y1+.5+hw)*SS],outline=(240,240,240,255),width=int(2*hw*SS))
    dash,gap=25.0,12.0
    for i in range(4):
        (ax,ay),(bx,by)=P[i],P[i+1]; ln=np.hypot(bx-ax,by-ay); t=0.0
        while t<ln:
            e=min(ln,t+dash); u0,u1=t/ln,e/ln
            d.line([S((ax+(bx-ax)*u0,ay+(by-ay)*u0)),S((ax+(bx-ax)*u1,ay+(by-ay)*u1))],fill=ORANGE+(255,),width=int(3.2*SS))
            t+=dash+gap
    L=L.resize((W,H),Image.LANCZOS)
    return np.asarray(Image.alpha_composite(im,L).convert('RGB')).astype(float)
import clipli_shared as C  # soils fix, north arrow + scale bar sources
Mr=rect_mask(X0-3.0,Y0-3.0,X1+3.0,Y1+3.0)[...,None]
for f,(x0,y0,x1,y1) in FR.items():
    O=np.asarray(Image.open(ORIG+f+'.jpg').convert('RGB')).astype(float)
    if f=='map_soils': O=C.soils_fix(O)
    O=shift_fill(O)
    out=BG*(1-Mr)+O*Mr
    out=draw_line(out)
    # legend back on top, whole box (it covered the corner of the line in the original too)
    Ml=rrect(x0,y0,x1,y1,3)[...,None]; Mi=rrect(x0+2,y0+2,x1-2,y1-2,2)[...,None]
    lv=np.where((O.min(2,keepdims=True)>=200),251.0,O)
    band=np.clip(Ml-Mi,0,1); lv=lv*(1-band)+160.0*band
    inner=np.asarray(Image.fromarray((Mr[...,0]*255).astype(np.uint8))).astype(float)[...,None]/255
    # inside the rectangle keep the legend exactly as the original drew it; outside use the cleaned copy
    lgd=O*inner+lv*(1-inner)
    out=out*(1-Ml)+lgd*Ml
    if f=='map_build':
        xs=slice(7,339)
        out[1101:1118,xs]=out[1129:1146,xs]
        out[1118:1147,xs]=BG
    out[C.NREG]=C.ov[C.NREG]
    m=C.SB_KEEP[...,None]*1.0; rr=C.SB_RING[...,None]*0.5
    out=out*(1-m)+C.WAT*m
    out=out*(1-rr)+(C.WAT*0.5+BG*0.5)*rr
    Image.fromarray(np.clip(out,0,255).round().astype(np.uint8)).save(D+f+'.jpg',quality=90,optimize=True,progressive=True)
    print(f,os.path.getsize(D+f+'.jpg')//1024,'KB')
