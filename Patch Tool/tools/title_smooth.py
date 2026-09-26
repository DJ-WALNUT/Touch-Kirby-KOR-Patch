"""타이틀 로고의 사선·곡선에 원작식 안티앨리어싱을 넣는다 (Pillow 필요). import_art 다음, title_credit 전에 실행.

  python tools/title_smooth.py [--preview]

원작 「タ」의 사선처럼, 계단 경계마다 흰색 → 밝은 회색 → 어두운 회색 → 검정 으로 이어지는 픽셀을 넣는다.
  1. 대상 영역(치·커)의 흰 획 윤곽을 픽셀 경계선으로 추출
  2. 긴 직선 획(3px 이상)과 직각 모서리는 고정하고, 그 사이 계단 구간만 매끈한 선으로 단순화 (RDP)
  3. 8x8 로 초고해상도 래스터 → 픽셀마다 흰색이 덮는 비율(0~1)
  4. 비율에 맞는 회색을 그 타일의 원래 팔레트 뱅크 안의 무채색에서 고른다 (뱅크는 절대 바꾸지 않음)
"""
import os, sys
from collections import Counter
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
ROOT = config.ROOT
PNG = os.path.join(config.WORK, 'bank04bin', 'chr_title__scr_title.png')
BOXES = [(55, 62, 110, 102), (118, 62, 172, 102)]   # 치, 커 (x0, y0, x1, y1)
SS = 8          # 초고해상도 배율
EPS = 0.75      # 계단 단순화 허용 오차 (px)
FIX = 3         # 이 길이 이상 직선 구간은 원래 모양 유지


def loops_of(mask, W, H):
    """흰 픽셀 영역의 경계를 닫힌 꼭짓점 목록들로 (시계 방향, 픽셀 경계 좌표)"""
    nxt = {}
    for (x, y) in mask:
        if (x, y - 1) not in mask:
            nxt[(x, y)] = (x + 1, y)
        if (x + 1, y) not in mask:
            nxt[(x + 1, y)] = (x + 1, y + 1)
        if (x, y + 1) not in mask:
            nxt[(x + 1, y + 1)] = (x, y + 1)
        if (x - 1, y) not in mask:
            nxt[(x, y + 1)] = (x, y)
    loops = []
    seen = set()
    for s in list(nxt):
        if s in seen:
            continue
        pts = [s]
        seen.add(s)
        p = nxt[s]
        while p != s and p in nxt and p not in seen:
            pts.append(p)
            seen.add(p)
            p = nxt[p]
        loops.append(pts)
    return loops


def corners(pts):
    """일직선 위 점 제거 → 꼭짓점만"""
    out = []
    n = len(pts)
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) != 0:
            out.append(b)
    return out


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    dx, dy = x1 - x0, y1 - y0
    L = (dx * dx + dy * dy) ** 0.5 or 1
    dmax, idx = 0, 0
    for i in range(1, len(pts) - 1):
        d = abs(dy * pts[i][0] - dx * pts[i][1] + x1 * y0 - y1 * x0) / L
        if d > dmax:
            dmax, idx = d, i
    if dmax > eps:
        return rdp(pts[:idx + 1], eps)[:-1] + rdp(pts[idx:], eps)
    return [pts[0], pts[-1]]


def smooth_loop(cs):
    """긴 직선 변의 양 끝점을 고정점으로, 고정점 사이 계단 구간만 RDP"""
    n = len(cs)
    seglen = [abs(cs[(i + 1) % n][0] - cs[i][0]) + abs(cs[(i + 1) % n][1] - cs[i][1]) for i in range(n)]
    anchor = [False] * n
    for i in range(n):
        if seglen[i] >= FIX:
            anchor[i] = anchor[(i + 1) % n] = True
    if not any(anchor):
        return cs
    start = anchor.index(True)
    order = cs[start:] + cs[:start]
    anc = anchor[start:] + anchor[:start]
    out = []
    run = [order[0]]
    for i in range(1, n + 1):
        p = order[i % n]
        run.append(p)
        if anc[i % n]:
            out += rdp(run, EPS)[:-1]
            run = [p]
    return out


def main():
    im = Image.open(PNG)
    px = im.load()
    pal = im.getpalette()
    W, H = im.size
    isw = lambda i: i and tuple(pal[i * 3:i * 3 + 3]) == (255, 255, 255)
    changed = 0

    def tile_bank(X, Y):
        tx, ty = X // 8 * 8, Y // 8 * 8
        c = Counter(px[x, y] // 16 for x in range(tx, tx + 8) for y in range(ty, ty + 8) if px[x, y])
        return c.most_common(1)[0][0] if c else 0

    def gray_in(bk, v):
        cand = [i for i in range(bk * 16 + 1, bk * 16 + 16)
                if pal[i * 3] == pal[i * 3 + 1] == pal[i * 3 + 2]]
        return min(cand, key=lambda i: abs(pal[i * 3] - v)) if cand else None

    for (x0, y0, x1, y1) in BOXES:
        mask = {(x, y) for y in range(y0, y1) for x in range(x0, x1) if isw(px[x, y])}
        sub = Image.new('L', ((x1 - x0) * SS, (y1 - y0) * SS), 0)
        d = ImageDraw.Draw(sub)
        for lp in loops_of(mask, W, H):
            cs = corners(lp)
            sm = smooth_loop(cs)
            poly = [((x - x0) * SS, (y - y0) * SS) for x, y in sm]
            if len(poly) >= 3:
                # 겹치는 영역은 XOR (구멍 처리)
                tmp = Image.new('L', sub.size, 0)
                ImageDraw.Draw(tmp).polygon(poly, fill=255)
                sub = Image.eval(Image.merge('L', [sub]), lambda v: v)  # noqa
                from PIL import ImageChops
                sub = ImageChops.logical_xor(sub.convert('1'), tmp.convert('1')).convert('L')
        sp = sub.load()
        for y in range(y0, y1):
            for x in range(x0, x1):
                cov = sum(1 for yy in range((y - y0) * SS, (y - y0 + 1) * SS)
                          for xx in range((x - x0) * SS, (x - x0 + 1) * SS) if sp[xx, yy]) / (SS * SS)
                cur_w = (x, y) in mask
                cur = px[x, y]
                # 흰 획 또는 검은 판 픽셀만 대상 (배경·테두리는 건드리지 않음)
                if not (cur_w or tuple(pal[cur * 3:cur * 3 + 3]) == (0, 0, 0)):
                    continue
                if (cov >= 0.94 and cur_w) or (cov <= 0.06 and not cur_w):
                    continue
                bk = tile_bank(x, y)
                v = round(255 * cov)
                gi = gray_in(bk, v)
                if gi is None:
                    continue
                if gi != cur:
                    px[x, y] = gi
                    changed += 1
    im.save(PNG, transparency=0)
    print('안티앨리어싱 적용: %d픽셀' % changed)
    if '--preview' in sys.argv:
        a = im.convert('RGBA')
        bg = Image.new('RGBA', a.size, (255, 255, 255, 255))
        z = Image.alpha_composite(bg, a).crop((40, 55, 190, 110))
        os.makedirs(config.PREVIEW, exist_ok=True)
        z.resize((z.width * 6, z.height * 6), Image.NEAREST).save(os.path.join(config.PREVIEW, 'title_smooth.png'))


if __name__ == '__main__':
    main()
