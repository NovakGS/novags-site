import json, re, math, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
Image.MAX_IMAGE_PIXELS=None
R='/home/claude/novags-site/hamele/img/'
V=json.load(open(R+'vec.json'))
VW,VH=V['VW'],V['VH']
FB='/usr/share/fonts/opentype/inter/Inter-Bold.otf'
FS='/usr/share/fonts/opentype/inter/Inter-SemiBold.otf'

def tiles_region(kind, x0,y0,x1,y1, ow,oh):
    t=V['tiles'][kind]; sx=t['w']/VW; sy=t['h']/VH; ts=t['ts']
    px0,py0,px1,py1=x0*sx,y0*sy,x1*sx,y1*sy
    c0,c1=int(px0//ts),int(min(t['c']-1,(px1-1)//ts)); r0,r1=int(py0//ts),int(min(t['r']-1,(py1-1)//ts))
    W=(c1-c0+2)*ts; H=(r1-r0+2)*ts
    m=Image.new('RGB',(W,H),(5,7,10))
    for r in range(r0,r1+1):
        for c in range(c0,c1+1):
            if r<0 or c<0: continue
            im=Image.open(f'{R}tiles/{kind}/{r}_{c}.{t["ext"]}').convert('RGB')
            m.paste(im,((c-c0)*ts,(r-r0)*ts))
    box=(px0-c0*ts,py0-r0*ts,px1-c0*ts,py1-r0*ts)
    return m.resize((ow,oh),Image.LANCZOS,box=box)

def img_region(name,x0,y0,x1,y1,ow,oh,mode='RGB'):
    im0=Image.open(R+name).convert(mode); sx=im0.width/VW; sy=im0.height/VH
    im=Image.new(mode,(im0.width+400,im0.height+400)); im.paste(im0,(200,200))
    return im.resize((ow,oh),Image.LANCZOS,box=(x0*sx+200,y0*sy+200,x1*sx+200,y1*sy+200))

def parse(d):
    subs=[]
    for part in re.split(r'M',d):
        n=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',part)))
        if len(n)>=4: subs.append(list(zip(n[0::2],n[1::2])))
    return subs

def hexrgb(h): h=h.lstrip('#'); return tuple(int(h[i:i+2],16) for i in (0,2,4))

class Canvas:
    def __init__(s,crop,ow,oh,ss=3,css=1.0):
        s.x0,s.y0,s.x1,s.y1=crop; s.ow,s.oh=ow,oh; s.ss=ss
        s.k=ow/(s.x1-s.x0)*ss   # canvas px per frame unit
        s.css=css*ss            # canvas px per CSS px
        s.W,s.H=ow*ss,oh*ss
    def new(s): return Image.new('RGBA',(s.W,s.H),(0,0,0,0))
    def P(s,x,y): return ((x-s.x0)*s.k,(y-s.y0)*s.k)
    def Pn(s,xn,yn): return s.P(xn*VW,yn*VH)
    def down(s,im): return im.resize((s.ow,s.oh),Image.LANCZOS)

def fill_layer(cv,feats,alpha):
    L=cv.new()
    for col,d in feats:
        mask=Image.new('L',(cv.W,cv.H),0); dm=ImageDraw.Draw(mask)
        for sub in parse(d):
            # evenodd via XOR
            m2=Image.new('L',(cv.W,cv.H),0); ImageDraw.Draw(m2).polygon([cv.P(x,y) for x,y in sub],fill=255)
            mask=Image.fromarray(np.bitwise_xor(np.array(mask),np.array(m2)))
        c=Image.new('RGBA',(cv.W,cv.H),hexrgb(col)+(255,))
        L=Image.alpha_composite(L,Image.composite(c,Image.new('RGBA',(cv.W,cv.H),(0,0,0,0)),mask))
    a=np.array(L); a[...,3]=(a[...,3].astype(float)*alpha).astype(np.uint8)
    return Image.fromarray(a)

def stroke(cv,L,pts,rgba,w):
    dr=ImageDraw.Draw(L); P=[cv.P(x,y) for x,y in pts]; wpx=max(1,int(round(w*cv.css)))
    dr.line(P,fill=rgba,width=wpx,joint='curve')
    r=wpx/2
    for (x,y) in (P[0],P[-1]): dr.ellipse((x-r,y-r,x+r,y+r),fill=rgba)

def line_layer(cv,paths,rgba,w,dash=None,dots=None):
    L=cv.new()
    for d in paths:
        for sub in parse(d):
            if dots:
                P=[cv.P(x,y) for x,y in sub]; step=dots*cv.css; r=w*cv.css/2; acc=0; dr=ImageDraw.Draw(L)
                for (ax,ay),(bx,by) in zip(P,P[1:]):
                    seg=math.hypot(bx-ax,by-ay); t=acc
                    while t<=seg:
                        x=ax+(bx-ax)*t/seg if seg else ax; y=ay+(by-ay)*t/seg if seg else ay
                        dr.ellipse((x-r,y-r,x+r,y+r),fill=rgba); t+=step
                    acc=t-seg
            elif dash:
                on,off=dash[0]*cv.css,dash[1]*cv.css; P=[cv.P(x,y) for x,y in sub]; dr=ImageDraw.Draw(L); wpx=max(1,int(round(w*cv.css)))
                pos=0.0; per=on+off
                for (ax,ay),(bx,by) in zip(P,P[1:]):
                    seg=math.hypot(bx-ax,by-ay); s0=0.0
                    if seg<1e-9: continue
                    while s0<seg-1e-6:
                        ph=pos%per
                        if ph<on:
                            st=max(min(on-ph,seg-s0),1e-3); e=s0+st
                            dr.line([(ax+(bx-ax)*s0/seg,ay+(by-ay)*s0/seg),(ax+(bx-ax)*e/seg,ay+(by-ay)*e/seg)],fill=rgba,width=wpx)
                        else:
                            st=max(min(per-ph,seg-s0),1e-3); e=s0+st
                        pos+=st; s0=e
            else:
                dr=ImageDraw.Draw(L); P=[cv.P(x,y) for x,y in sub]; wpx=max(1,int(round(w*cv.css)))
                dr.line(P,fill=rgba,width=wpx,joint=('curve' if wpx>6 else None)); r=wpx/2
                for (x,y) in (P[0],P[-1]): dr.ellipse((x-r,y-r,x+r,y+r),fill=rgba)
    return L

def contours(cv,minor=(0x78,0x4e,0x28,int(.6*255)),index=(0x5c,0x34,0x14,int(.92*255)),wm=.7,wi=1.6):
    L=cv.new()
    mi=[f[1] for f in V['contours'] if f[0]=='m']; ix=[f[1] for f in V['contours'] if f[0]=='i']
    L=Image.alpha_composite(L,line_layer(cv,mi,minor,wm))
    L=Image.alpha_composite(L,line_layer(cv,ix,index,wi))
    return L

def text_rot(cv,L,xn,yn,txt,ang,size,fill,halo):
    f=ImageFont.truetype(FS,int(size*cv.css))
    bb=f.getbbox(txt); tw,th=bb[2]-bb[0],bb[3]-bb[1]; pad=int(4*cv.css)
    T=Image.new('RGBA',(tw+2*pad,th+2*pad),(0,0,0,0)); d=ImageDraw.Draw(T)
    d.text((pad-bb[0],pad-bb[1]),txt,font=f,fill=fill,stroke_width=int(1.6*cv.css),stroke_fill=halo)
    T=T.rotate(-ang,resample=Image.BICUBIC,expand=True)
    x,y=cv.Pn(xn,yn); L.alpha_composite(T,(int(x-T.width/2),int(y-T.height/2)))

def circle(dr,x,y,r,fill=None,outline=None,width=0):
    dr.ellipse((x-r,y-r,x+r,y+r),fill=fill,outline=outline,width=width)

def dashed_ring(L,x,y,r,col,w,n=10):
    dr=ImageDraw.Draw(L)
    for i in range(n):
        a0=i*360/n; dr.arc((x-r,y-r,x+r,y+r),a0,a0+360/n*0.55,fill=col,width=w)

def markers(cv,L,hubs=False,deer=False,ring_px=16,tags=True):
    dr=ImageDraw.Draw(L); c=cv.css
    if hubs:
        for xn,yn,_ in V['hubs']:
            x,y=cv.Pn(xn,yn)
            circle(dr,x,y,(9/2+1.5+1)*c,fill=(0,0,0,90))
            circle(dr,x,y,(9/2+1.5)*c,fill=(255,255,255,255))
            circle(dr,x,y,(9/2)*c,fill=hexrgb('#9b5fd7')+(255,))
    if deer:
        G={}
        for xn,yn,lk,g in V['deer']:
            x,y=cv.Pn(xn,yn); r=ring_px/2*c; bw=2.5*c
            circle(dr,x,y,r+2*c,outline=(0,0,0,128),width=int(2*c))
            if lk: circle(dr,x,y,r,outline=(255,255,255,255),width=int(bw))
            else:  dashed_ring(L,x,y,r,(255,255,255,165),int(bw))
            circle(dr,x,y,r-bw,outline=(0,0,0,100),width=max(1,int(1*c)))
            gg=G.setdefault(g,[0,1,0,0]); gg[0]+=xn; gg[1]=min(gg[1],yn); gg[2]+=1; gg[3]+=lk
        if tags:
            f=ImageFont.truetype(FB,int(11*c))
            for g,(sx,my,k,l) in G.items():
                if not l: continue
                x,y=cv.Pn(sx/k,my); txt=f'{l} Deer'
                bb=f.getbbox(txt); tw=bb[2]-bb[0]; th=bb[3]-bb[1]
                px,py=7*c,4*c; bx1=x-tw/2-px; bx2=x+tw/2+px; by2=y-22*c; by1=by2-th-2*py
                dr.line([(x,by2),(x,by2+12*c)],fill=(255,255,255,205),width=max(1,int(1*c)))
                dr.rounded_rectangle((bx1,by1,bx2,by2),radius=7*c,fill=(5,7,10,220),outline=(255,255,255,140),width=max(1,int(1*c)))
                dr.text((x-tw/2-bb[0],by1+py-bb[1]),txt,font=f,fill=(255,255,255,255))
    return L
