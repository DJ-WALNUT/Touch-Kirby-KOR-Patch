"""글자 주변 스타일 추정: 흰 글자에 붙은 외곽선 색(흰 픽셀 1~2px 이웃 중 가장 흔한 진한 색)과 배경색
  python tools/style.py x0 y0 x1 y1 파일…"""
import sys
from collections import Counter
import numpy as np
from PIL import Image
box = [int(v) for v in sys.argv[1:5]]
for f in sys.argv[5:]:
    a = np.asarray(Image.open(f).convert('RGB')).astype(int)
    x0, y0, x1, y1 = box
    sub = a[y0:y1, x0:x1]
    white = (sub.sum(-1) >= 740)
    bg = Counter(map(tuple, sub.reshape(-1, 3))).most_common(1)[0][0]
    near = np.zeros_like(white)
    for dy in (-2, -1, 0, 1, 2):
        for dx in (-2, -1, 0, 1, 2):
            near |= np.roll(np.roll(white, dy, 0), dx, 1)
    ring = near & ~white
    cols = Counter(map(tuple, sub[ring]))
    dark = [(c, n) for c, n in cols.most_common(12) if sum(c) < sum(bg) - 40]
    print(f, 'bg %02x%02x%02x' % bg, 'stroke', ' '.join('%02x%02x%02x:%d' % (*c, n) for c, n in dark[:3]))
