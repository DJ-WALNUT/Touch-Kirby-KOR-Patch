"""jp/ 이미지를 폴더별 대조표로 모은다 → _sheets/ (글자 이미지 선별용)"""
import glob, os
from PIL import Image, ImageDraw
files = sorted(f for f in glob.glob('jp/**/*', recursive=True) if f.lower().endswith(('.gif','.jpg')))
groups = {}
for f in files:
    im = Image.open(f); w,h = im.size
    if w*h < 400 or 'spacer' in f: continue
    groups.setdefault(os.path.dirname(f), []).append((f, im.convert('RGB'), w, h))
os.makedirs('_sheets', exist_ok=True)
for g, items in groups.items():
    W=1400; x=y=0; rowh=0; pos=[]
    for f,im,w,h in items:
        s = min(1, 600/w, 300/h); tw,th = int(w*s), int(h*s)
        if x+tw > W: x=0; y+=rowh+18; rowh=0
        pos.append((f,im,x,y,tw,th)); x+=tw+10; rowh=max(rowh,th)
    H=y+rowh+18
    for part in range(0, H, 1500):
        sheet = Image.new('RGB',(W,min(1500,H-part)),(90,90,90)); d=ImageDraw.Draw(sheet)
        for f,im,x,y,tw,th in pos:
            if y < part or y >= part+1500: continue
            sheet.paste(im.resize((tw,th)),(x,y-part+14)); d.text((x,y-part),os.path.basename(f),fill=(255,255,0))
        sheet.save('_sheets/%s_%d.png' % (g.replace('jp','root',1).replace('/','_'), part//1500))
print(sorted(os.listdir('_sheets')), sum(len(v) for v in groups.values()))
