"""글자 이미지 한글화: tools/img_spec.py 의 사양대로 jp/ 이미지를 다시 그려 img_ko/ 에 저장.
  - 여러 조각(예: karakuri mid01 + chara01)은 한 캔버스로 합쳐서 작업한 뒤 다시 자른다
  - 원래 글자는 색 마스크 + 인페인팅(OpenCV Telea)으로 지운다 → 배경 무늬가 살아 있음
  - 새 글자는 주아체. 외곽선 여러 겹·그림자·자간·최대 폭(넘치면 가로로 좁힘)
  python tools/render_img.py [그룹…]      # 그룹 = 사양의 group 이름 (없으면 전부)
  비교 이미지: _sheets/cmp_<그룹>.png (위: 원본, 아래: 한글판, 2배)
"""
import os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JP, OUT = os.path.join(ROOT, 'jp'), os.path.join(ROOT, 'img_ko')
FONTS = {'jua': os.path.join(ROOT, 'fonts', 'Jua-Regular.ttf')}
# 주아체에 없는 글리프(「」…)는 둥근 고딕 히라기노 마루고로
FALLBACK = '/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc'
_fc, _cmap = {}, {}


def has_glyph(name, ch):
    if name not in _cmap:
        from fontTools.ttLib import TTFont
        _cmap[name] = set(TTFont(FONTS.get(name, name), fontNumber=0).getBestCmap())
    return ord(ch) in _cmap[name]


def font(name, size):
    k = (name, size)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(FONTS.get(name, name), size)
    return _fc[k]


def hexrgb(c):
    if isinstance(c, tuple):
        return c
    c = c.lstrip('#')
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------- 지우기
def erase(canvas, box, colors=None, tol=48, grow=1, bg=None, radius=3, keep=None, sat=None, dark=None):
    """box 안에서 글자 픽셀을 골라 인페인팅.
    colors: 글자 색 목록 → 이 색들과 가까운 픽셀이 마스크 (없고 bg 도 없으면 box 전체)
    bg: 배경 색 목록 → 이 색들과 모두 먼 픽셀이 마스크
    keep: 마스크에서 뺄 box 목록 (지우면 안 되는 그림)
    sat: 채도(HSV S)가 이 값보다 큰 픽셀이 마스크 (회색·파스텔 배경 위의 진한 색 글자)
    dark: RGB 합이 이 값보다 작은 픽셀도 마스크 (sat 와 함께 쓰면 둘 중 하나)"""
    a = np.asarray(canvas).astype(np.int32)
    x0, y0, x1, y1 = box
    m = np.zeros(a.shape[:2], np.uint8)
    sub = a[y0:y1, x0:x1]
    if sat is not None or dark is not None:
        mx, mn = sub.max(-1), sub.min(-1)
        sel = np.zeros(sub.shape[:2], bool)
        if sat is not None:
            sel |= (mx - mn) / np.maximum(mx, 1) > sat
        if dark is not None:
            sel |= sub.sum(-1) < dark
        m[y0:y1, x0:x1] = sel * 255
    elif colors:
        d = np.min([np.abs(sub - hexrgb(c)).sum(-1) for c in colors], axis=0)
        m[y0:y1, x0:x1] = (d <= tol) * 255
    elif bg:
        d = np.min([np.abs(sub - hexrgb(c)).sum(-1) for c in bg], axis=0)
        m[y0:y1, x0:x1] = (d > tol) * 255
    else:
        m[y0:y1, x0:x1] = 255
    if grow:
        m = cv2.dilate(m, np.ones((3, 3), np.uint8), iterations=grow)
        # 번짐은 box 밖으로 나가지 않게
        clip = np.zeros_like(m); clip[y0:y1, x0:x1] = 255; m &= clip
    for kb in keep or ():
        m[kb[1]:kb[3], kb[0]:kb[2]] = 0
    img = cv2.inpaint(np.asarray(canvas)[:, :, ::-1].copy(), m, radius, cv2.INPAINT_TELEA)
    return Image.fromarray(img[:, :, ::-1])


def fill(canvas, box, color):
    ImageDraw.Draw(canvas).rectangle((box[0], box[1], box[2] - 1, box[3] - 1), fill=hexrgb(color))
    return canvas


def recolor(canvas, box, keep, color, tol=20):
    """box 안에서 keep 색들과 모두 먼 픽셀을 color 로 칠함 (단색 바탕 + 테두리만 남기기)"""
    a = np.asarray(canvas).copy()
    x0, y0, x1, y1 = box
    sub = a[y0:y1, x0:x1].astype(np.int32)
    d = np.min([np.abs(sub - hexrgb(c)).sum(-1) for c in keep], axis=0)
    a[y0:y1, x0:x1][d > tol] = hexrgb(color)
    return Image.fromarray(a)


def hstretch(canvas, box, src_x):
    """box 의 각 행을 src_x 열의 색으로 채움 (가로 줄무늬 막대용)"""
    a = np.asarray(canvas).copy()
    x0, y0, x1, y1 = box
    a[y0:y1, x0:x1] = a[y0:y1, src_x:src_x + 1]
    return Image.fromarray(a)


def copy(canvas, box, dx, dy):
    """box 영역을 (dx,dy) 만큼 떨어진 곳의 픽셀로 덮음"""
    x0, y0, x1, y1 = box
    canvas.paste(canvas.crop((x0 + dx, y0 + dy, x1 + dx, y1 + dy)), (x0, y0))
    return canvas


# ---------------------------------------------------------------- 글자
def text_layer(runs, size, strokes=(), shadow=None, spacing=0, fname='jua'):
    """runs: [(문자열, {fill, strokes?})…] 또는 문자열. strokes: [(굵기, 색)] 바깥 → 안쪽.
    반환: RGBA 레이어 (여백 포함), 잉크 bbox"""
    if isinstance(runs, str):
        runs = [(runs, {})]
    f = font(fname, size)
    fb = font(FALLBACK, size)
    fof = lambda ch: f if has_glyph(fname, ch) else fb
    pad = 4 + max([w for w, _ in strokes] + [0]) + (max(abs(shadow[0]), abs(shadow[1])) if shadow else 0)
    # 글자 위치
    chars, x = [], 0
    for s, st in runs:
        for ch in s:
            if has_glyph(fname, ch):
                chars.append((x, ch, st))
                x += f.getlength(ch) + spacing
            else:
                # 대체 글리프(전각 「」 등)는 잉크 폭만 차지하게
                l, _, r, _ = fb.getbbox(ch)
                chars.append((x - l + 1, ch, st))
                x += (r - l) + 2 + spacing
    W = int(x - spacing) + pad * 2 + 2
    asc, desc = f.getmetrics()
    H = asc + desc + pad * 2
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)

    def draw(ox, oy, width, colorof):
        for cx, ch, st in chars:
            col = colorof(st)
            if col is None:
                continue
            d.text((pad + cx + ox, pad + oy), ch, font=fof(ch), fill=col, stroke_width=width, stroke_fill=col)

    if shadow:
        sdx, sdy, scol = shadow
        w0 = strokes[0][0] if strokes else 0
        draw(sdx, sdy, w0, lambda st: hexrgb(scol))
    for i, (w, col) in enumerate(strokes):
        draw(0, 0, w, lambda st, i=i, col=col: hexrgb(st['strokes'][i][1]) if 'strokes' in st else hexrgb(col))
    draw(0, 0, 0, lambda st: hexrgb(st.get('fill', '#ffffff')))
    return L, L.getbbox()


def text(canvas, runs, xy, size, anchor='l', strokes=(), shadow=None, spacing=0, maxw=None,
         fill=None, squeeze_min=0.72, font_name='jua', valign='c', dy=0, italic=0.0, rotate=0):
    """xy = (x, y): anchor 'l'|'c'|'r' 기준 x, 세로는 valign 'c' 면 잉크 가운데, 't'/'b' 면 잉크 위/아래가 y.
    maxw 를 넘으면 가로로 좁힘 (squeeze_min 까지), 그래도 넘으면 크기를 줄임"""
    if isinstance(runs, str):
        runs = [(runs, {'fill': fill or '#ffffff'})]
    elif fill:
        runs = [(s, dict({'fill': fill}, **st)) for s, st in runs]
    while True:
        L, bb = text_layer(runs, size, strokes, shadow, spacing, font_name)
        if italic:
            # 기울임: 위쪽을 오른쪽으로 italic*높이 만큼 민다
            h = L.height
            L = L.transform((L.width + int(italic * h) + 1, h), Image.AFFINE,
                            (1, italic, -italic * h, 0, 1, 0), Image.BICUBIC)
            bb = L.getbbox()
        if rotate:
            L = L.rotate(rotate, expand=True, resample=Image.BICUBIC)
            bb = L.getbbox()
        L = L.crop(bb)
        if maxw and L.width > maxw:
            r = maxw / L.width
            if r < squeeze_min:
                size -= 1
                continue
            L = L.resize((maxw, L.height), Image.LANCZOS)
        break
    cy = {'c': L.height / 2, 't': 0, 'b': L.height}[valign]
    x, y = xy
    ox = {'l': x, 'c': x - L.width / 2, 'r': x - L.width}[anchor]
    oy = y - cy + dy
    base = canvas.convert('RGBA')
    base.alpha_composite(L, (int(round(ox)), int(round(oy))))
    return base.convert('RGB')


def paste(canvas, path, box, align='c'):
    """이미지를 box 에 맞춰 (비율 유지) 붙임"""
    im = Image.open(os.path.join(ROOT, path)).convert('RGBA')
    x0, y0, x1, y1 = box
    r = min((x1 - x0) / im.width, (y1 - y0) / im.height)
    im = im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), Image.LANCZOS)
    ox = {'l': x0, 'c': x0 + (x1 - x0 - im.width) // 2, 'r': x1 - im.width}[align]
    oy = y0 + (y1 - y0 - im.height) // 2
    base = canvas.convert('RGBA')
    base.alpha_composite(im, (ox, oy))
    return base.convert('RGB')


# ---------------------------------------------------------------- 실행
def load(files):
    parts = [(rel, Image.open(os.path.join(JP, rel)).convert('RGB'), x, y) for rel, x, y in files]
    W = max(x + im.width for _, im, x, _ in parts)
    H = max(y + im.height for _, im, _, y in parts)
    c = Image.new('RGB', (W, H), (255, 0, 255))
    for _, im, x, y in parts:
        c.paste(im, (x, y))
    return c, parts


def save(canvas, parts):
    for rel, im, x, y in parts:
        piece = canvas.crop((x, y, x + im.width, y + im.height))
        dst = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if rel.lower().endswith('.gif'):
            piece.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(dst)
        else:
            piece.save(dst, quality=92, subsampling=0)


def run(spec, groups=None):
    sheets = {}
    for item in spec:
        g = item['group']
        if groups and g not in groups:
            continue
        files = item['files'] if 'files' in item else [(item['file'], 0, 0)]
        canvas, parts = load(files)
        before = canvas.copy()
        for op in item['ops']:
            canvas = op(canvas)
        save(canvas, parts)
        sheets.setdefault(g, []).append((before, canvas))
    os.makedirs(os.path.join(ROOT, '_sheets'), exist_ok=True)
    for g, pairs in sheets.items():
        W = max(b.width for b, _ in pairs) * 2
        H = sum(b.height * 4 + 12 for b, _ in pairs)
        s = Image.new('RGB', (W, H), (70, 70, 70))
        y = 0
        for b, a in pairs:
            s.paste(b.resize((b.width * 2, b.height * 2), Image.NEAREST), (0, y)); y += b.height * 2 + 2
            s.paste(a.resize((a.width * 2, a.height * 2), Image.NEAREST), (0, y)); y += a.height * 2 + 10
        s.save(os.path.join(ROOT, '_sheets', f'cmp_{g}.png'))
    print('rendered:', {g: len(p) for g, p in sheets.items()})


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(__file__))
    from img_spec import SPEC
    run(SPEC, set(sys.argv[1:]) or None)
