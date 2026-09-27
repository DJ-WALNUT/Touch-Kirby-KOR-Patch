"""이미지 영역 확대 + 색 분포 (스타일 샘플링용)
  python tools/probe.py jp/menu/b01.gif [x0 y0 x1 y1] [--zoom 4] [--out _sheets/p.png]"""
import sys
from PIL import Image
a = sys.argv[1:]
zoom = int(a[a.index('--zoom')+1]) if '--zoom' in a else 4
out = a[a.index('--out')+1] if '--out' in a else '_sheets/probe.png'
nums = [int(x) for x in a[1:] if x.lstrip('-').isdigit()][:4]
im = Image.open(a[0]).convert('RGB')
box = tuple(nums) if len(nums) == 4 else (0, 0) + im.size
c = im.crop(box)
if out != 'none': c.resize((c.width*zoom, c.height*zoom), Image.NEAREST).save(out)
cols = sorted(c.getcolors(1 << 20), reverse=True)[:14]
print(im.size, box, ' '.join('%02x%02x%02x:%d' % (*col, n) for n, col in cols))
