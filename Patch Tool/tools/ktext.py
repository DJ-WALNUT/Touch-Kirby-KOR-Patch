"""한글 텍스트 합성 도구 (Pillow 필요: pip install pillow).

사양 파일 translation/render/<bank>/<이름>.json 을 읽어,
원본(work/_jp/...) 위에 지우기·글자 찍기를 적용한 결과를 work/... 에 쓴다.

  python tools/ktext.py analyze <work PNG>     팔레트 사용 현황과 글자 덩어리(줄) 위치 출력
  python tools/ktext.py render [이름...]       사양 → work PNG (인자 없으면 전부)
  python tools/ktext.py preview <이름> [배율]  원본|결과 비교 이미지를 work/_preview/ 에 저장
  python tools/ktext.py check [이름...]       work PNG 가 원래 타일 용량 안에 들어가는지 검사 (+스프라이트 공유 조각 표시)

사양 형식 (JSON):
{
  "png": "bank04bin/screentouch.png",
  "ops": [
    {"fill": [x, y, w, h], "idx": 10},                  사각형을 색 인덱스로 채움
    {"clear": [x, y, w, h], "keep": [10, 3], "idx": 10}, 영역 안에서 keep 에 없는 색을 idx 로 바꿈 (글자만 지우기)
    {"copy": [sx, sy, w, h], "to": [dx, dy]},           원본에서 영역 복사 (배경 무늬 복원용)
    {"text": "화면을 터치!", "at": [x, y], "font": "g11b", "fill": 8,
     "outline": 3, "shadow": [1, 1, 5], "align": "left|center|right", "w": 100,
     "spacing": 0, "line_h": 14, "bold": 0|1|2, "valign_box": [y, h]}
  ]
}
 - text 의 "@L001" 형태는 translation/length_table*.md 의 해당 ID 값으로 바뀜 (수기번역 > 자동번역 순)
 - "\n" 으로 여러 줄. at 은 첫 줄 글자 칸의 왼쪽 위(align 에 따라 w 기준 정렬)
 - valign_box: [y, h] 를 주면 전체 줄 묶음을 그 세로 범위 가운데에 놓음
 - 폰트: g7(8px) g9(10px) g11(12px) g11b(12px 굵게) g11c(12px 좁게) g14(15px)
"""
import sys, os, json, re, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image, ImageDraw, ImageFont

import config
ROOT, WORK, SPEC, PREVIEW = config.ROOT, config.WORK, config.SPECS, config.PREVIEW
FONTS = {
    'g7': ('Galmuri7.ttf', 8), 'g9': ('Galmuri9.ttf', 10), 'g11': ('Galmuri11.ttf', 12),
    'g11b': ('Galmuri11-Bold.ttf', 12), 'g11c': ('Galmuri11-Condensed.ttf', 12), 'g14': ('Galmuri14.ttf', 15),
}
_fc = {}


def font(key):
    if key not in _fc:
        fn, sz = FONTS[key]
        _fc[key] = ImageFont.truetype(os.path.join(config.FONTS, fn), sz)
    return _fc[key]


def length_table():
    """translation/length_table*.md 의 | ID | 파일 | 원문 | 자동번역 | 수기번역 | 메모 | 행"""
    out = {}
    for p in sorted(glob.glob(os.path.join(config.TRANSLATION, 'length_table*.md'))):
        for line in open(p, encoding='utf-8'):
            c = [x.strip() for x in line.strip().strip('|').split('|')]
            if len(c) >= 5 and re.match(r'L\d+$', c[0]):
                val = c[4] or c[3]
                out[c[0]] = val.replace('\\n', '\n').replace('<br>', '\n')
    return out


def resolve(text, lt):
    return re.sub(r'@(L\d+)', lambda m: lt.get(m.group(1), m.group(0)), text)


def text_mask(s, fkey, spacing=0, bold=False):
    """글자 한 줄의 1비트 마스크 (w, h, set of (x, y)). 높이는 폰트 ascent 기준 칸."""
    f = font(fkey)
    asc, desc = f.getmetrics()
    W = 4 + sum(int(f.getlength(ch)) + spacing + 1 for ch in s) + 8
    im = Image.new('1', (max(W, 1), asc + desc + 2), 0)
    d = ImageDraw.Draw(im)
    d.fontmode = '1'
    x = 0
    if spacing:
        for ch in s:
            d.text((x, 0), ch, font=f, fill=1)
            x += int(round(f.getlength(ch))) + spacing
    else:
        d.text((0, 0), s, font=f, fill=1)
    px = im.load()
    pts = {(x, y) for y in range(im.height) for x in range(im.width) if px[x, y]}
    if bold:  # 1 = 가로 1px 번짐, 2 = 가로+세로
        pts |= {(x + 1, y) for x, y in pts}
        if bold == 2:
            pts |= {(x, y + 1) for x, y in pts}
    if not pts:
        return 0, asc, set()
    w = max(x for x, _ in pts) + 1
    return w, asc + desc, pts


def draw_text(img, op, lt, warns, name, mask=None):
    s = resolve(op['text'], lt)
    fkey = op.get('font', 'g11b')
    lines = s.split('\n')
    lh = op.get('line_h', font(fkey).getmetrics()[0] + font(fkey).getmetrics()[1])
    x0, y0 = op['at']
    if 'valign_box' in op:
        by, bh = op['valign_box']
        # 실제 픽셀 높이로 가운데 맞춤
        masks = [text_mask(l, fkey, op.get('spacing', 0), op.get('bold', False)) for l in lines]
        ys = [y for i, (_, _, p) in enumerate(masks) for (_, y) in [(0, yy + i * lh) for (_, yy) in p]]
        if ys:
            top, bot = min(ys), max(ys)
            y0 = by + (bh - (bot - top + 1)) // 2 - top
    px = img.load()
    W, H = img.size
    for i, line in enumerate(lines):
        w, h, pts = text_mask(line, fkey, op.get('spacing', 0), op.get('bold', False))
        bw = op.get('w')
        x = x0
        if bw is not None:
            if w > bw:
                warns.append('%s: 넘침 %dpx > %dpx 「%s」' % (name, w, bw, line))
            if op.get('align', 'left') == 'center':
                x = x0 + (bw - w) // 2
            elif op.get('align') == 'right':
                x = x0 + bw - w
        y = y0 + i * lh
        layers = []
        if op.get('shadow'):
            dx, dy, si = op['shadow']
            layers.append(({(a + dx, b + dy) for a, b in pts}, si))
        if op.get('outline') is not None:
            ring = set()
            r8 = op.get('outline8', True)
            for a, b in pts:
                for ddx in (-1, 0, 1):
                    for ddy in (-1, 0, 1):
                        if (ddx or ddy) and (r8 or not (ddx and ddy)):
                            ring.add((a + ddx, b + ddy))
            layers.append((ring - pts, op['outline']))
        layers.append((pts, op['fill']))
        for ps, ci in layers:
            for a, b in ps:
                X, Y = x + a, y + b
                if 0 <= X < W and 0 <= Y < H:
                    px[X, Y] = ci
                    if mask is not None and not mask[X, Y] and ci == op['fill']:
                        warns.append('%s: 편집 불가 영역(스프라이트 밖)에 글자 「%s」 (%d,%d)' % (name, line, X, Y))
                        mask = None
                elif ci == op['fill']:
                    warns.append('%s: 이미지 밖으로 나감 「%s」' % (name, line))
                    break


def apply_spec(spec, name, lt, warns):
    src = os.path.join(WORK, '_jp', spec['png'])
    img = Image.open(src)
    assert img.mode == 'P', src
    orig = img.copy()
    mp = os.path.join(WORK, '_mask', spec['png'])
    mask = Image.open(mp).load() if os.path.exists(mp) else None
    px = img.load()
    op_px = orig.load()
    for op in spec['ops']:
        if 'fill' in op and 'text' not in op:
            x, y, w, h = op['fill']
            for yy in range(y, y + h):
                for xx in range(x, x + w):
                    px[xx, yy] = op['idx']
        elif 'clear' in op:
            x, y, w, h = op['clear']
            keep = set(op['keep'])
            for yy in range(y, y + h):
                for xx in range(x, x + w):
                    if px[xx, yy] not in keep:
                        px[xx, yy] = op['idx']
        elif 'copy' in op:
            sx, sy, w, h = op['copy']
            dx, dy = op['to']
            for yy in range(h):
                for xx in range(w):
                    px[dx + xx, dy + yy] = op_px[sx + xx, sy + yy]
        elif 'text' in op:
            draw_text(img, op, lt, warns, name, mask)
    return img


def spec_files(names):
    allf = sorted(glob.glob(os.path.join(SPEC, '*', '*.json')))
    if not names:
        return allf
    return [f for f in allf if any(n in f for n in names)]


def cmd_render(args):
    lt = length_table()
    warns = []
    n = 0
    for f in spec_files(args):
        spec = json.load(open(f, encoding='utf-8'))
        name = os.path.relpath(f, SPEC)
        img = apply_spec(spec, name, lt, warns)
        img.save(os.path.join(WORK, spec['png']), transparency=0)
        n += 1
    for w in warns:
        print('  경고:', w)
    print('렌더 %d개, 경고 %d개' % (n, len(warns)))
    return warns


def cmd_preview(args):
    name = args[0]
    scale = int(args[1]) if len(args) > 1 else 3
    f = spec_files([name])[0]
    spec = json.load(open(f, encoding='utf-8'))
    warns = []
    img = apply_spec(spec, name, length_table(), warns)
    a = Image.open(os.path.join(WORK, '_jp', spec['png'])).convert('RGBA')
    b = img.convert('RGBA')
    W, H = a.size
    out = Image.new('RGBA', (W * 2 + 6, H), (255, 0, 255, 255))
    bg = Image.new('RGBA', (W, H), (60, 60, 70, 255))
    out.paste(Image.alpha_composite(bg, a), (0, 0))
    out.paste(Image.alpha_composite(bg, b), (W + 6, 0))
    out = out.resize((out.width * scale, out.height * scale), Image.NEAREST)
    os.makedirs(PREVIEW, exist_ok=True)
    p = os.path.join(PREVIEW, os.path.basename(f)[:-5] + '.png')
    out.save(p)
    for w in warns:
        print('  경고:', w)
    print(p)


def cmd_analyze(args):
    p = args[0]
    if not os.path.isabs(p) and not os.path.exists(p):
        p = os.path.join(WORK, '_jp', p)
    img = Image.open(p)
    W, H = img.size
    px = img.load()
    pal = img.getpalette()
    from collections import Counter
    cnt = Counter(px[x, y] for y in range(H) for x in range(W))
    print('크기 %dx%d' % (W, H))
    print('색 사용: ' + ', '.join('%d(%02x%02x%02x)x%d' % (i, pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2], c)
                                for i, c in cnt.most_common(24)))
    # 행 단위 덩어리: 투명(0)이 아닌 픽셀이 있는 행 구간
    rows = [any(px[x, y] for x in range(W)) for y in range(H)]
    y = 0
    while y < H:
        if not rows[y]:
            y += 1; continue
        y1 = y
        while y1 < H and rows[y1]:
            y1 += 1
        cols = [x for x in range(W) if any(px[x, yy] for yy in range(y, y1))]
        # 가로로 8px 이상 비면 끊음
        segs = []
        s = p0 = cols[0]
        for x in cols[1:]:
            if x - p0 > 8:
                segs.append((s, p0)); s = x
            p0 = x
        segs.append((s, p0))
        for a, b in segs:
            c = Counter(px[x, yy] for yy in range(y, y1) for x in range(a, b + 1) if px[x, yy])
            print('  y=%d~%d x=%d~%d  색 %s' % (y, y1 - 1, a, b, dict(c.most_common(6))))
        y = y1


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd != 'check':
        {'render': cmd_render, 'preview': cmd_preview, 'analyze': cmd_analyze}.get(
            cmd, lambda a: print(__doc__))(sys.argv[2:])


# ---------------------------------------------------------------- 용량 검사
def cmd_check(args):
    """work PNG 를 실제로 재삽입해 보고 원래 용량 안에 들어가는지 검사.
    스프라이트는 work/_preview/<이름>_objs.png 에 OAM 오브젝트 테두리를 그림:
    같은 색·번호 = 일본어 원본에서 같은 타일 블록을 공유하던 오브젝트 (한국어도 똑같이 그려야 공유되어 용량 절약)"""
    from ndslib import load_rom
    import kasset, pngio, kfmt
    jp = load_rom(config.ROM_JP)
    man = json.load(open(os.path.join(WORK, 'manifest.json'), encoding='utf-8'))
    for key, m in sorted(man.items()):
        if args and not any(a in ' '.join(m['png']) or a in key for a in args):
            continue
        g = kasset.Group(jp, key, m['kind'])
        pngs = [pngio.read_png(os.path.join(WORK, rel)) for rel in m['png']]
        orig_views = [lay for _, lay, _ in g.views]
        warns = g.apply_all(pngs)
        name = key.rsplit('/', 1)[1]
        if m['kind'] == 'c05':
            cap, used = g.obj['ntile_bytes'], len(g.obj['tiles'])
        elif m['kind'] == 'bg':
            cap, used = g.tile_growth()
        else:
            cap = used = 0
        ok = used <= cap
        print('%-40s %s  용량 %d / 사용 %d 바이트%s' % (name, 'OK  ' if ok else '초과', cap, used,
                                                 '' if ok else '  (%d 바이트 = 타일 %d개 줄여야 함)' % (used - cap, (used - cap) // (32 if g.bpp == 4 else 64))))
        for w in warns:
            if '초과' in w or '공유' in w or '밖' in w:
                print('    ', w)
        if m['kind'] == 'c05':
            # 원본 오브젝트 테두리 오버레이
            jg = kasset.Group(jp, key, 'c05')
            c = jg.obj
            lay = jg.views[0][1]
            tu = c['unit'] if c['bpp'] == 4 else max(1, c['unit'] // 2)
            rel = m['png'][0]
            img = Image.open(os.path.join(WORK, rel)).convert('RGBA')
            bg = Image.new('RGBA', img.size, (60, 60, 70, 255))
            img = Image.alpha_composite(bg, img)
            S = 3
            img = img.resize((img.width * S, img.height * S), Image.NEAREST)
            d = ImageDraw.Draw(img)
            boxes = [(i, kfmt.cell_bbox(o)) for i, o in enumerate(c['cells'])]
            boxes = [(i, b) for i, b in boxes if b]
            pos, W, H = kfmt._grid([(i, b[2] - b[0], b[3] - b[1]) for i, b in boxes])
            use = {}
            for ci, cell in enumerate(c['cells']):
                for a0, a1, a1f, a2 in cell:
                    use.setdefault((a2 & 0x3FF), set()).add(ci)
            shared = {b for b, cs in use.items() if len(cs) > 1}
            palette = [(255, 80, 80), (80, 200, 255), (120, 255, 120), (255, 200, 60), (220, 120, 255), (255, 140, 200), (80, 255, 220)]
            sid = {b: k for k, b in enumerate(sorted(shared))}
            for i, bb in boxes:
                ox, oy = pos[i][0] - bb[0], pos[i][1] - bb[1]
                for a0, a1, a1f, a2 in c['cells'][i]:
                    w, h = kfmt.OBJ_SIZE.get((a0 >> 14, a1 >> 14), (8, 8))
                    x, y = kfmt.s9(a1 & 511) + ox, kfmt.s8(a0 & 255) + oy
                    b = a2 & 0x3FF
                    col = palette[sid[b] % len(palette)] if b in shared else (140, 140, 140)
                    d.rectangle([x * S, y * S, (x + w) * S - 1, (y + h) * S - 1], outline=col)
                    if b in shared:
                        d.text((x * S + 2, y * S + 1), str(sid[b]), fill=col)
            os.makedirs(PREVIEW, exist_ok=True)
            out = os.path.join(PREVIEW, os.path.basename(rel)[:-4] + '_objs.png')
            img.save(out)
            print('     오브젝트 테두리:', out)


if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == 'check':
    cmd_check(sys.argv[2:])
