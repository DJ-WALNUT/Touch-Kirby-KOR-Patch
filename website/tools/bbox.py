"""글자색 픽셀의 bbox: python tools/bbox.py 색1,색2 tol x0 y0 x1 y1 파일…"""
import sys
import numpy as np
from PIL import Image
cols = [tuple(int(c[i:i+2], 16) for i in (0, 2, 4)) for c in sys.argv[1].split(',')]
tol = int(sys.argv[2]); box = [int(v) for v in sys.argv[3:7]]
for f in sys.argv[7:]:
    a = np.asarray(Image.open(f).convert('RGB')).astype(int)
    x0, y0, x1, y1 = box[0], box[1], min(box[2], a.shape[1]), min(box[3], a.shape[0])
    sub = a[y0:y1, x0:x1]
    m = np.min([np.abs(sub - c).sum(-1) for c in cols], axis=0) <= tol
    ys, xs = np.nonzero(m)
    print(f, (x0 + xs.min(), y0 + ys.min(), x0 + xs.max() + 1, y0 + ys.max() + 1) if len(xs) else None, int(m.sum()))
