"""Read-only Pillow preview of the 320x480 physical UI; *not* a real AWTK screenshot."""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from player_ui import BG, TEXT, SECONDARY, THEMES
from wave import segments

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / 'outputs'
SCALE = 3
FONT = '/usr/share/fonts/truetype/lato/Lato-Regular.ttf'
FONT_BOLD = '/usr/share/fonts/truetype/lato/Lato-Semibold.ttf'


def rgb(hexval):
    return tuple(bytes.fromhex(hexval.lstrip('#')))


def draw_album(d, x, y, size):
    # Abstract placeholder cover. Deliberately only the art contains a palette;
    # the player UI background is one flat #121417 surface.
    d.rounded_rectangle((x,y,x+size-1,y+size-1), radius=10*SCALE, fill='#E8DFD5')
    d.ellipse((x+45*SCALE,y+33*SCALE,x+230*SCALE,y+218*SCALE), fill='#D8B9C0')
    d.ellipse((x+70*SCALE,y+57*SCALE,x+200*SCALE,y+187*SCALE), fill='#AA8BA8')
    d.polygon([(x,y+177*SCALE),(x+82*SCALE,y+126*SCALE),(x+159*SCALE,y+178*SCALE),
               (x+228*SCALE,y+112*SCALE),(x+size,y+176*SCALE), (x+size,y+size),(x,y+size)], fill='#556772')
    d.polygon([(x,y+206*SCALE),(x+100*SCALE,y+164*SCALE),(x+191*SCALE,y+220*SCALE),
               (x+size,y+170*SCALE),(x+size,y+size),(x,y+size)], fill='#324955')
    d.text((x+24*SCALE,y+19*SCALE),'MUSIC',font=ImageFont.truetype(FONT_BOLD,10*SCALE),fill='#2C3840')
    d.text((x+24*SCALE,y+37*SCALE),'FOR QUIET NIGHTS',font=ImageFont.truetype(FONT,8*SCALE),fill='#4D5A62')


def text_center(d, center, y, txt, face, size, fill):
    f=ImageFont.truetype(face,size*SCALE)
    bb=d.textbbox((0,0),txt,font=f)
    d.text((center*SCALE-(bb[2]-bb[0])/2, y*SCALE),txt,font=f,fill=fill)


def render_player(color='Jade'):
    a = THEMES[color]
    sc=SCALE
    img=Image.new('RGB',(320*sc,480*sc),rgb(BG))
    d=ImageDraw.Draw(img)
    # Status row, never Mochi branding on home.
    f=ImageFont.truetype(FONT,10*sc); fb=ImageFont.truetype(FONT_BOLD,10*sc)
    d.text((24*sc,12*sc),'FLAC  ·  24/96',font=f,fill=SECONDARY)
    d.text((246*sc,12*sc),'87%',font=fb,fill=TEXT)
    d.rounded_rectangle((273*sc,14*sc,290*sc,23*sc),radius=2*sc,outline=TEXT,width=1*sc)
    d.rectangle((291*sc,17*sc,293*sc,20*sc),fill=TEXT)
    d.rectangle((276*sc,17*sc,286*sc,20*sc),fill=a)
    # Album art is the only colorful object, deliberately no backdrop blur.
    draw_album(d,28*sc,58*sc,264*sc)
    # Fine, discrete page markers.
    for i,x in enumerate((151,160,169)):
        d.ellipse(((x-2)*sc,324*sc,(x+2)*sc,328*sc),fill=a if i==0 else '#485058')
    text_center(d,160,337,'Slow Motion',FONT_BOLD,19,TEXT)
    text_center(d,160,363,'Akina Nakamori',FONT,15,SECONDARY)
    # 64 bars, not a fake real audio waveform. Dynamic fill is true progress.
    for bar in segments(32,392,102,238):
        d.rounded_rectangle((bar.x*sc,bar.y*sc,(bar.x+bar.w)*sc-1,(bar.y+bar.h)*sc-1),
                            radius=1*sc, fill=a if bar.active else '#475059')
    small=ImageFont.truetype(FONT,11*sc)
    d.text((28*sc,407*sc),'1:42',font=small,fill=SECONDARY)
    bb=d.textbbox((0,0),'3:58',font=small)
    d.text((292*sc-(bb[2]-bb[0]),407*sc),'3:58',font=small,fill=SECONDARY)
    # Quiet, large touch targets for transport controls.
    white=rgb(TEXT)
    d.polygon([(99*sc,443*sc),(99*sc,455*sc),(88*sc,449*sc)],fill=white)
    d.rectangle((85*sc,444*sc,87*sc,454*sc),fill=white)
    d.polygon([(221*sc,443*sc),(221*sc,455*sc),(232*sc,449*sc)],fill=white)
    d.rectangle((233*sc,444*sc,235*sc,454*sc),fill=white)
    d.ellipse((139*sc,428*sc,181*sc,470*sc),fill=a)
    d.rounded_rectangle((153*sc,440*sc,157*sc,458*sc),radius=1*sc,fill=BG)
    d.rounded_rectangle((163*sc,440*sc,167*sc,458*sc),radius=1*sc,fill=BG)
    # Additional available actions remain hidden under top interactions.
    return img


def render_settings():
    sc=SCALE
    im=Image.new('RGB',(320*sc,480*sc),rgb(BG)); d=ImageDraw.Draw(im)
    s=lambda n:n*sc
    fsm=ImageFont.truetype(FONT,11*sc); fn=ImageFont.truetype(FONT,17*sc); fb=ImageFont.truetype(FONT_BOLD,20*sc)
    d.text((s(24),s(12)),'87%   ·   FLAC',font=fsm,fill=SECONDARY)
    d.text((s(24),s(53)),'Apariencia',font=fb,fill=TEXT)
    d.text((s(24),s(98)),'COLOR DE ACENTO',font=fsm,fill=SECONDARY)
    for i,(name,col) in enumerate(THEMES.items()):
        y=132+i*44
        d.ellipse((s(25),s(y+2),s(47),s(y+24)),fill=col)
        d.text((s(63),s(y+1)),name,font=fn,fill=TEXT)
        d.line((s(24),s(y+36),s(296),s(y+36)),fill='#292D31',width=1*sc)
        if name=='Jade':
            d.ellipse((s(265),s(y+3),s(286),s(y+24)),outline=col,width=sc*2)
            d.ellipse((s(272),s(y+10),s(279),s(y+17)),fill=col)
    d.text((s(24),s(422)),'Solo cambia el acento.',font=fsm,fill=SECONDARY)
    d.text((s(24),s(439)),'El fondo permanece uniforme.',font=fsm,fill=SECONDARY)
    return im


def main():
    OUTPUT.mkdir(exist_ok=True,parents=True)
    for name in ('Jade','Violeta','Coral'):
        render_player(name).save(OUTPUT/f'mochi-reproduciendo-{name.lower()}.png')
    render_settings().save(OUTPUT/'mochi-ajustes-colores.png')
    print('Vistas previas independientes (NO son capturas AWTK):',OUTPUT)

if __name__=='__main__': main()
