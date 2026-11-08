import math
W,H=1738,1130     # MacBook Air 13 aspect (2560x1664); drawn on 1600 wide, centred
DX=(W-1600)//2
out=[]
def add(s):
    if s.count(' fill=')>1:
        s=s.replace('fill="none" stroke="#111" stroke-width="3.2"','stroke="#111" stroke-width="3.2"',1)
    out.append(s)
JP="'Klee One','Klee','Hiragino Maru Gothic ProN','Noto Sans CJK JP',sans-serif"
EN="'Chalkboard SE','Marker Felt','Comic Sans MS','Noto Sans',sans-serif"
SK='fill="none" stroke="#111" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"'
def arrow(x0,y0,cx,cy,x1,y1,dash=False):
    d=f'M{x0},{y0} Q{cx},{cy} {x1},{y1}'
    da=' stroke-dasharray="2 12"' if dash else ''
    add(f'<path d="{d}" {SK}{da}/>')
    ang=math.atan2(y1-cy,x1-cx); L=22
    for s in (+0.5,-0.5):
        a=ang+math.pi+s
        add(f'<path d="M{x1},{y1} L{x1+L*math.cos(a):.1f},{y1+L*math.sin(a):.1f}" {SK}/>')
def label(x,y,jp,en,sub_jp=None,sub_en=None,anchor="start",n=None):
    if n is not None:
        add(f'<circle cx="{x-36}" cy="{y-15}" r="24" {SK} fill="#fff"/>')
        add(f'<text x="{x-36}" y="{y-4}" font-family="{EN}" font-size="30" font-weight="700" fill="#111" text-anchor="middle">{n}</text>')
    add(f'<text x="{x}" y="{y}" font-family="{JP}" font-size="44" font-weight="700" fill="#111" text-anchor="{anchor}">{jp}</text>')
    add(f'<text x="{x}" y="{y+40}" font-family="{EN}" font-size="28" fill="#111" text-anchor="{anchor}">{en}</text>')
    if sub_jp:
        add(f'<text x="{x}" y="{y+84}" font-family="{JP}" font-size="26" fill="#555" text-anchor="{anchor}">→ {sub_jp}</text>')
        add(f'<text x="{x}" y="{y+116}" font-family="{EN}" font-size="22" fill="#555" text-anchor="{anchor}">{sub_en}</text>')

add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
add('''<defs>
<filter id="wob" x="-5%" y="-5%" width="110%" height="110%">
 <feTurbulence type="fractalNoise" baseFrequency="0.018" numOctaves="2" seed="7"/>
 <feDisplacementMap in="SourceGraphic" scale="5"/></filter>
<filter id="wobt" x="-5%" y="-20%" width="110%" height="140%">
 <feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="1" seed="3"/>
 <feDisplacementMap in="SourceGraphic" scale="2"/></filter>
</defs>''')
add(f'<rect width="{W}" height="{H}" fill="#f4f4f2"/>')
add(f'<g transform="translate({DX},0)">')
# --- blue title band (slightly tilted), like a strip of tape
add('<g filter="url(#wob)">')
add(f'<path d="M-120,-10 L1080,-10 L1060,120 L-120,135 Z" fill="#5cc3ec" {SK}/>')
add('</g>')
add('<g filter="url(#wobt)">')
add(f'<text x="70" y="78" font-family="{JP}" font-size="58" font-weight="700" fill="#111">あそびかた</text>')
add(f'<text x="420" y="78" font-family="{EN}" font-size="40" fill="#111">How to play with me</text>')
add('</g>')

# --- the robot ------------------------------------------------------------
add('<g filter="url(#wob)">')
cx=760
# base: a squat cylinder
add(f'<path d="M{cx-190},905 L{cx-190},950 Q{cx},1015 {cx+190},950 L{cx+190},905" {SK} fill="#fff"/>')
add(f'<ellipse cx="{cx}" cy="905" rx="190" ry="55" {SK} fill="#fff"/>')
add(f'<ellipse cx="{cx}" cy="900" rx="150" ry="38" {SK} fill="none" stroke-opacity=".5"/>')
# lower bracket + box
add(f'<path d="M{cx-75},905 L{cx-75},800 L{cx+70},800 L{cx+70},880" {SK}/>')
add(f'<path d="M{cx-55},905 L{cx-55},820 L{cx+50},820" {SK}/>')
add(f'<path d="M{cx-10},835 L{cx+70},835 L{cx+70},900 L{cx-10},900 Z" {SK} fill="#a9dcef"/>')
# pole
add(f'<path d="M{cx-18},800 L{cx-18},520 M{cx+18},800 L{cx+18},520" {SK}/>')
# neck box
add(f'<path d="M{cx-48},430 L{cx+52},430 L{cx+52},525 L{cx-48},525 Z" {SK} fill="#a9dcef"/>')
# side bracket
add(f'<path d="M{cx-95},350 L{cx-95},500 Q{cx-95},512 {cx-80},512 L{cx-62},512 Q{cx-50},512 {cx-50},500 L{cx-50},400" {SK} fill="#fff"/>')
# head: a sideways cylinder, the big round eye facing right
add(f'<path d="M{cx-110},270 L{cx+90},250 L{cx+90},420 L{cx-110},410" {SK} fill="#fff"/>')
add(f'<ellipse cx="{cx-110}" cy="340" rx="38" ry="70" {SK} fill="#fff"/>')
add(f'<path d="M{cx-20},262 Q{cx-12},340 {cx-20},414" {SK} stroke-opacity=".6"/>')
add(f'<ellipse cx="{cx+105}" cy="335" rx="62" ry="98" {SK} fill="#fff"/>')
add(f'<ellipse cx="{cx+112}" cy="335" rx="32" ry="52" fill="#111" stroke="#111" stroke-width="3"/>')
add(f'<circle cx="{cx+122}" cy="316" r="8" fill="#fff"/>')
# pat-pat marks above the head
add(f'<path d="M{cx-60},215 Q{cx-50},195 {cx-60},175 M{cx-30},210 Q{cx-20},185 {cx-30},160 M{cx},215 Q{cx+10},195 {cx},175" {SK}/>')
# grass / ground
add(f'<path d="M{cx+230},985 q8,-12 16,0 q8,-12 16,0 q8,-12 16,0 M{cx-330},990 q8,-12 16,0 q8,-12 16,0" {SK}/>')
# a cloud
add(f'<path d="M1240,190 q-10,-40 30,-40 q20,-35 55,-5 q40,-15 45,25 q30,20 -5,40 q-20,25 -55,5 q-40,20 -60,-5 q-35,-5 -10,-20 Z" {SK} fill="#fff"/>')
add('</g>')

# --- the visitor: a tiny waving person (left), and a bottle (right) -------
add('<g filter="url(#wob)">')
px,py=300,860
add(f'<circle cx="{px}" cy="{py-120}" r="22" {SK} fill="#fff"/>')
add(f'<path d="M{px},{py-98} L{px},{py-30} M{px},{py-30} L{px-18},{py+20} M{px},{py-30} L{px+18},{py+20}" {SK}/>')
add(f'<path d="M{px},{py-80} L{px-25},{py-50} M{px},{py-80} L{px+22},{py-115} L{px+30},{py-148}" {SK}/>')
add(f'<path d="M{px+45},{py-165} q10,15 0,30 M{px+60},{py-175} q14,25 0,50" {SK}/>')   # )) wave marks
# footsteps toward the robot
for k,(fx,fy) in enumerate([(px+70,py+28),(px+120,py+45),(px+170,py+28),(px+220,py+45)]):
    add(f'<ellipse cx="{fx}" cy="{fy}" rx="11" ry="6" fill="#111"/>')
# bottle held up in front of the eye
bx,by=1000,380
add(f'<path d="M{bx},{by-60} L{bx+16},{by-60} L{bx+16},{by-45} Q{bx+34},{by-35} {bx+34},{by-10} L{bx+34},{by+70} L{bx-18},{by+70} L{bx-18},{by-10} Q{bx-18},{by-35} {bx},{by-45} Z" {SK} fill="#fff"/>')
add(f'<path d="M{bx-18},{by+15} L{bx+34},{by+15}" {SK}/>')
add('</g>')

# --- arrows + labels ------------------------------------------------------
add('<g filter="url(#wobt)">')
# 1 pat my head
label(130,250,"あたまをポンポン","Pat my head","すりすりするよ","I'll nuzzle up into your hand",n=5)
arrow(470,275, 600,215, cx-75,262)
# 2 hold it up to my eyes
label(1120,310,"目の前で見せてね","Hold it up to my eyes","おぼえて、さがしておくね","I'll look out for it",n=3)
arrow(975,350, 955,335, 935,345)
# 3 hide it, bring it back
label(1110,590,"かくして、また出してね","Hide it, then bring it back","見つけたら呼ぶよ！","I'll point at it and call you",n=4)
arrow(1090,620, 960,600, cx+120,450)
# 4 wave hi
label(110,520,"手をふってね","Wave hi","ふりかえすよ","I'll wave back",n=2)
arrow(250,640, 300,680, px+40,py-185)
# 5 come close
label(110,965,"ちかづいてね","Come close","じっと見てるよ","I'll keep my eyes on you",n=1)

# asleep note
add(f'<text x="1490" y="1050" font-family="{JP}" font-size="26" fill="#555" text-anchor="end">ねてたら（-_- zz）あたまをポンポン</text>')
add(f'<text x="1490" y="1084" font-family="{EN}" font-size="22" fill="#555" text-anchor="end">Asleep? Pat my head to wake me</text>')
add('</g>')
add('</g>')
add('</svg>')
open('how_to_play.svg','w').write("\n".join(out))
