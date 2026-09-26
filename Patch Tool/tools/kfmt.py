"""터치커비 그래픽 포맷 해석 + 레이아웃 기반 렌더/역변환.

모든 그래픽은 "레이아웃" (8x8 타일 배치 목록) 으로 표현한다.
  배치 = (x, y, buf, tile, hflip, vflip, bank)
렌더링과 PNG 재삽입이 같은 레이아웃을 쓰므로, 뽑은 PNG 를 그대로 다시 넣을 수 있다.

05 셀 컨테이너 헤더 (LE):
  +00 u32  5
  +04 u16  팔레트 색 수 (16 = 4bpp 1뱅크, 256 = 8bpp)
  +06 u16  타일 수 (4bpp 는 32바이트, 8bpp 는 64바이트 단위)
  +08 u16  셀(프레임) 수
  +0A u16  flags  bit0 = 타일영역 LZ77 압축, bit14 = 8bpp
  +0C u32  팔레트 오프셋
  +10 u32  타일 오프셋 (파일 끝까지 타일 데이터)
  +14 u32  셀 테이블 오프셋 (u32 x 셀수, 각 셀 OAM 목록 시작. 오름차순이 아닐 수 있음,
           셀의 끝 = 더 큰 오프셋 중 가장 가까운 것) + u32 0
  +18 ...  OAM 엔트리 8바이트: attr0, attr1, attr1(좌우반전 표시용), attr2
           attr2 타일번호 단위는 파일마다 128B 또는 64B (detect_unit)

06 애니메이션 컨테이너 (프레임마다 타일 블록이 따로 있음):
  +00 u32  6
  +04 u32  프레임 수
  +08 u32  프레임 테이블 오프셋 (u32 x 프레임수 -> 프레임 레코드)
  +0C u16  팔레트 바이트 수 (0x20 = 4bpp 16색, 0x200 = 8bpp 256색)
  +0E      팔레트
  ...      타일 블록: u16 크기, 데이터(비압축), 2바이트 패딩
  프레임 레코드 12바이트: u32 OAM목록 오프셋, u32 0x0C, u32 타일블록 오프셋

BG: chr_(타일) + col_(팔레트) + scr_(스크린맵, 16bit 엔트리) 세트. 각각 LZ77 압축일 수 있음.

bmp_ 큰 그림 (비압축, 예: bmp_goalkinkei = 골 게임 앞 배경 4000x528):
  +00 u16 가로(px)  +02 u16 세로(px)  +04 u16 색 수  +06 u16 타일 수
  +08      팔레트 (색 수 x 2)
  ...      8bpp 타일 (타일 수 x 64)
  ...      맵 u16 x (가로/8 x 세로/8), 행 우선. bit0-10 타일, bit14 좌우반전, bit15 상하반전
"""
import struct
from ndslib import lz77, bgr555

OBJ_SIZE = {  # (shape, size) -> (w, h)
    (0, 0): (8, 8), (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
    (1, 0): (16, 8), (1, 1): (32, 8), (1, 2): (32, 16), (1, 3): (64, 32),
    (2, 0): (8, 16), (2, 1): (8, 32), (2, 2): (16, 32), (2, 3): (32, 64),
}
CHECKER = [(200, 200, 200), (160, 160, 160)]


def s9(v):
    return v - 512 if v & 256 else v


def s8(v):
    return v - 256 if v & 128 else v


def pal_from(b, n=None):
    n = n or len(b) // 2
    return [bgr555(struct.unpack_from('<H', b, i * 2)[0]) for i in range(min(n, len(b) // 2))]


def pal_to_bytes(pal):
    out = bytearray()
    for r, g, b in pal:
        out += struct.pack('<H', (r * 31 // 255) | ((g * 31 // 255) << 5) | ((b * 31 // 255) << 10))
    return bytes(out)


# 팔레트를 못 찾았을 때 쓰는 식별용 고대비 16색 (0 = 투명)
DEBUG16 = [(0, 0, 0), (16, 16, 16), (255, 255, 255), (230, 40, 40), (40, 110, 230), (40, 180, 60),
           (250, 200, 30), (200, 60, 200), (30, 200, 200), (120, 120, 120), (190, 190, 190),
           (140, 70, 20), (255, 140, 180), (90, 40, 160), (170, 230, 90), (255, 120, 0)]


def full_palette(pal, bpp):
    """PNG 용 256색 팔레트. 원본에 없는 뱅크는 식별용 고대비 색으로 채움."""
    out = list(pal[:256])
    k = len(out)
    while len(out) < 256:
        out.append(DEBUG16[len(out) % 16])
    return out, k


# ---------------------------------------------------------------- 타일
def tile_get(buf, t, bpp):
    """타일 t 의 64픽셀 값 (범위 밖이면 None)"""
    if bpp == 4:
        b = buf[t * 32: t * 32 + 32]
        if len(b) < 32:
            return None
        out = []
        for x in b:
            out.append(x & 15); out.append(x >> 4)
        return out
    b = buf[t * 64: t * 64 + 64]
    return list(b) if len(b) == 64 else None


def tile_put(buf, t, bpp, pix):
    if bpp == 4:
        for i in range(32):
            buf[t * 32 + i] = (pix[i * 2] & 15) | ((pix[i * 2 + 1] & 15) << 4)
    else:
        buf[t * 64: t * 64 + 64] = bytes(pix)


def flip(pix, hf, vf):
    if not hf and not vf:
        return list(pix)
    out = [0] * 64
    for k in range(64):
        x, y = k % 8, k // 8
        sx = 7 - x if hf else x
        sy = 7 - y if vf else y
        out[k] = pix[sy * 8 + sx]
    return out


# ---------------------------------------------------------------- 레이아웃
class Layout:
    """bufs: {이름: bytearray}, bpp, pal. pl: [(x, y, buf, tile, hf, vf, bank)] 아래→위 순서"""

    def __init__(self, w, h, bpp, pal, bufs):
        self.w, self.h, self.bpp, self.pal, self.bufs = w, h, bpp, pal, bufs
        self.pl = []

    def add(self, x, y, buf, tile, hf=0, vf=0, bank=0):
        self.pl.append((x, y, buf, tile, hf, vf, bank))

    def render(self):
        """반환 Canvas: idx = PNG 팔레트 인덱스 (-1 = 배치 없음, 0 = 투명)"""
        cv = Canvas(self.w, self.h, self.pal)
        for (x, y, b, t, hf, vf, bank) in self.pl:
            pix = tile_get(self.bufs[b], t, self.bpp)
            if pix is None:
                continue
            pix = flip(pix, hf, vf)
            for k, v in enumerate(pix):
                px, py = x + k % 8, y + k // 8
                if not (0 <= px < self.w and 0 <= py < self.h):
                    continue
                o = py * self.w + px
                if v:
                    cv.idx[o] = v + bank * 16 if self.bpp == 4 else v
                elif cv.idx[o] < 0:
                    cv.idx[o] = 0
        return cv


class Canvas:
    def __init__(self, w, h, pal):
        self.w, self.h, self.pal = w, h, pal
        self.idx = [-1] * (w * h)

    def rgb(self, scale=1):
        W, H = self.w * scale, self.h * scale
        buf = bytearray(W * H * 3)
        for y in range(H):
            row = (y // scale) * self.w
            for x in range(W):
                i = self.idx[row + x // scale]
                if i <= 0:
                    c = CHECKER[((x // (4 * scale)) + (y // (4 * scale))) % 2]
                elif i < len(self.pal):
                    c = self.pal[i]
                else:
                    c = (255, 0, 255)
                o = (y * W + x) * 3
                buf[o:o + 3] = bytes(c)
        return W, H, buf


# ---------------------------------------------------------------- 05 container
def parse_container(data):
    if len(data) < 0x18 or struct.unpack_from('<I', data, 0)[0] != 5:
        return None
    ncol, ntile, ncell, flags = struct.unpack_from('<HHHH', data, 4)
    po, to, co = struct.unpack_from('<III', data, 0x0C)
    bpp = 8 if (flags & 0x4000 or ncol == 256) else 4
    tiles = lz77(data[to:]) if flags & 1 else data[to:]
    offs = [struct.unpack_from('<I', data, co + i * 4)[0] for i in range(ncell)]
    # 셀 테이블 오프셋은 오름차순이 아닐 수 있다. 셀의 끝 = 자기보다 큰 오프셋 중 가장 가까운 것 (없으면 테이블 시작)
    starts = sorted(set(offs))
    cells = []
    for o in offs:
        end = next((x for x in starts if x > o), co)
        cells.append([struct.unpack_from('<HHHH', data, p) for p in range(o, end, 8)])
    c = {'ncol': ncol, 'ntile': ntile, 'flags': flags, 'bpp': bpp,
         'pal': pal_from(data[po:po + ncol * 2]), 'tiles': bytearray(tiles), 'cells': cells,
         'pal_off': po, 'tile_off': to, 'cell_off': co, 'cell_offs': offs, 'oam_patch': {}}
    c['unit'] = detect_unit(cells, bpp, len(tiles))
    c['ntile_bytes'] = len(tiles)
    # 원본에서 어떤 OAM 이든 참조하는 타일 (이 밖의 타일은 코드가 직접 쓸 수 있으므로 건드리지 않음)
    tu = c['unit'] if bpp == 4 else max(1, c['unit'] // 2)
    ref = set()
    for cell in cells:
        for a0, a1, a1f, a2 in cell:
            w, h = OBJ_SIZE.get((a0 >> 14, a1 >> 14), (8, 8))
            bs = (a2 & 0x3FF) * tu
            ref.update(range(bs, bs + w * h // 64))
    c['orig_ref'] = ref
    return c


def build_container(orig, c):
    """타일 데이터, 바뀐 OAM attr2, 타일 수를 반영한 05 컨테이너 바이트 (타일 영역은 파일 끝)"""
    to = c['tile_off']
    head = bytearray(orig[:to])
    for off, a2 in c['oam_patch'].items():
        struct.pack_into('<H', head, off, a2)
    struct.pack_into('<H', head, 6, len(c['tiles']) // (32 if c['bpp'] == 4 else 64))  # 타일 수는 bpp 기준
    t = bytes(c['tiles'])
    if c['flags'] & 1:
        from ndslib import lz77_compress
        t = lz77_compress(t)
    return bytes(head) + t


def detect_unit(cells, bpp, tile_bytes):
    """attr2 타일번호 1 당 4bpp 타일 수. 데이터 범위 안에 들어가는 가장 큰 값 (128B=4, 64B=2, 32B=1)"""
    have = tile_bytes // 32
    for unit in (4, 2, 1):
        m = 0
        for cell in cells:
            for a0, a1, a1f, a2 in cell:
                w, h = OBJ_SIZE.get((a0 >> 14, a1 >> 14), (8, 8))
                m = max(m, (a2 & 0x3FF) * unit + w * h // 64 * (bpp // 4))
        if m <= have:
            return unit
    return 1


def cell_bbox(oams):
    xs, ys = [], []
    for a0, a1, a1f, a2 in oams:
        w, h = OBJ_SIZE.get((a0 >> 14, a1 >> 14), (8, 8))
        x, y = s9(a1 & 511), s8(a0 & 255)
        xs += [x, x + w]; ys += [y, y + h]
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _add_oams(lay, ox, oy, oams, buf, bpp, unit, cell=None):
    """cell 을 주면 배치마다 (셀, OAM 번호, 오브젝트 안 타일 번호) 를 lay.orefs 에 기록"""
    tu = unit if bpp == 4 else max(1, unit // 2)
    for j in range(len(oams) - 1, -1, -1):  # 앞 엔트리가 위에 그려짐
        a0, a1, a1f, a2 = oams[j]
        w, h = OBJ_SIZE.get((a0 >> 14, a1 >> 14), (8, 8))
        x, y = s9(a1 & 511), s8(a0 & 255)
        hf, vf = (a1 >> 12) & 1, (a1 >> 13) & 1
        base = (a2 & 0x3FF) * tu
        bank = (a2 >> 12) if bpp == 4 else 0
        tw, th = w // 8, h // 8
        for ty in range(th):
            for tx in range(tw):
                dx = (tw - 1 - tx) if hf else tx
                dy = (th - 1 - ty) if vf else ty
                lay.add(ox + x + dx * 8, oy + y + dy * 8, buf, base + ty * tw + tx, hf, vf, bank)
                if cell is not None:
                    lay.orefs.append((cell, j, ty * tw + tx))


def _grid(items, maxw=512, pad=4):
    """items: [(key, w, h)] -> {key: (x, y)}, W, H"""
    x = y = rh = W = 0
    pos = {}
    for k, w, h in items:
        if x and x + w > maxw:
            x, y, rh = 0, y + rh + pad, 0
        pos[k] = (x, y); x += w + pad; rh = max(rh, h); W = max(W, x)
    return pos, max(W, 8), max(y + rh, 8)


def layout_container(c):
    boxes = [(i, cell_bbox(o)) for i, o in enumerate(c['cells'])]
    boxes = [(i, b) for i, b in boxes if b]
    if not boxes:
        return None
    pos, W, H = _grid([(i, b[2] - b[0], b[3] - b[1]) for i, b in boxes])
    lay = Layout(W, H, c['bpp'], c['pal'], {'t': c['tiles']})
    lay.orefs = []
    # 셀끼리 겹치지 않으니 셀 순서는 무관. 같은 타일을 여러 셀이 공유할 수 있음.
    for i, b in boxes:
        x, y = pos[i]
        _add_oams(lay, x - b[0], y - b[1], c['cells'][i], 't', c['bpp'], c['unit'], cell=i)
    return lay


def render_container(c):
    lay = layout_container(c)
    return lay.render() if lay else None


# ---------------------------------------------------------------- 06 container
def parse_container6(data):
    if len(data) < 0x10 or struct.unpack_from('<I', data, 0)[0] != 6:
        return None
    nf, fto = struct.unpack_from('<II', data, 4)
    pbytes = struct.unpack_from('<H', data, 0x0C)[0]
    pal = pal_from(data[0x0E:0x0E + pbytes])
    bpp = 8 if pbytes > 32 else 4
    recs = []
    for i in range(nf):
        ro = struct.unpack_from('<I', data, fto + i * 4)[0]
        oo, _, bo = struct.unpack_from('<III', data, ro)
        recs.append((oo, bo, ro))
    starts = sorted(set(r[0] for r in recs))
    first_rec = min(r[2] for r in recs)
    frames, blocks = [], {}
    for oo, bo, ro in recs:
        nxt = [s for s in starts if s > oo]
        end = nxt[0] if nxt else first_rec
        oams = [struct.unpack_from('<HHHH', data, p) for p in range(oo, end, 8)]
        if bo not in blocks:
            size = struct.unpack_from('<H', data, bo)[0]
            blocks[bo] = bytearray(data[bo + 2: bo + 2 + size])
        frames.append({'oams': oams, 'block': bo,
                       'unit': detect_unit([oams], bpp, len(blocks[bo]))})
    return {'bpp': bpp, 'pal': pal, 'frames': frames, 'blocks': blocks}


def build_container6(orig, c6):
    out = bytearray(orig)
    for bo, buf in c6['blocks'].items():
        out[bo + 2: bo + 2 + len(buf)] = buf
    return bytes(out)


def layout_container6(c6):
    items = []
    for i, f in enumerate(c6['frames']):
        bb = cell_bbox(f['oams'])
        if bb:
            items.append((i, bb))
    if not items:
        return None
    pos, W, H = _grid([(i, b[2] - b[0], b[3] - b[1]) for i, b in items])
    bufs = {str(bo): b for bo, b in c6['blocks'].items()}
    lay = Layout(W, H, c6['bpp'], c6['pal'], bufs)
    for i, b in items:
        f = c6['frames'][i]
        x, y = pos[i]
        _add_oams(lay, x - b[0], y - b[1], f['oams'], str(f['block']), c6['bpp'], f['unit'])
    return lay


def render_container6(c6):
    lay = layout_container6(c6)
    return lay.render() if lay else None


# ---------------------------------------------------------------- bmp_ 큰 그림
def parse_bmp(data):
    if len(data) < 8:
        return None
    w, h, nc, nt = struct.unpack_from('<4H', data)
    to = 8 + nc * 2
    mo = to + nt * 64
    if not w or not h or w % 8 or h % 8 or nc > 256 or mo + (w // 8) * (h // 8) * 2 != len(data):
        return None
    return {'w': w, 'h': h, 'pal': pal_from(data[8:to]), 'tiles': bytearray(data[to:mo]),
            'map': struct.unpack_from('<%dH' % ((w // 8) * (h // 8)), data, mo), 'tile_off': to}


def build_bmp(orig, b):
    """타일만 바꿈 (맵·팔레트·크기는 원본 그대로)"""
    to = b['tile_off']
    assert len(b['tiles']) == len(orig) - to - len(b['map']) * 2, 'bmp 타일 수가 바뀜'
    return orig[:to] + bytes(b['tiles']) + orig[to + len(b['tiles']):]


def layout_bmp(b):
    lay = Layout(b['w'], b['h'], 8, b['pal'], {'chr': b['tiles']})
    tw = b['w'] // 8
    for i, e in enumerate(b['map']):
        lay.add(i % tw * 8, i // tw * 8, 'chr', e & 0x7FF, (e >> 14) & 1, (e >> 15) & 1, 0)
    return lay


# ---------------------------------------------------------------- BG (chr+col+scr)
def scr_dims(n):
    if n == 2048:
        return 64, 32
    if n == 4096:
        return 64, 64
    return 32, max(1, n // 32)


def scr_pos(i, tw):
    """맵 엔트리 번호 -> (타일 x, 타일 y). 32칸 넘는 맵은 32x32 블록 순서"""
    if tw > 32:
        blk, r = divmod(i, 1024)
        return (blk % (tw // 32)) * 32 + r % 32, (blk // (tw // 32)) * 32 + r // 32
    return i % tw, i // tw


def layout_bg(chr_, pal, scr, bpp):
    n = len(scr) // 2
    ent = struct.unpack_from('<%dH' % n, scr)
    tw, th = scr_dims(n)
    lay = Layout(tw * 8, th * 8, bpp, pal, {'chr': chr_})
    for i, e in enumerate(ent):
        mx, my = scr_pos(i, tw)
        lay.add(mx * 8, my * 8, 'chr', e & 0x3FF, (e >> 10) & 1, (e >> 11) & 1,
                (e >> 12) if bpp == 4 else 0)
    return lay


def render_bg(chr_, pal, scr, bpp):
    return layout_bg(chr_, pal, scr, bpp).render()


def guess_bg_bpp(chr_, pal, scr):
    n = len(scr) // 2
    ent = struct.unpack_from('<%dH' % n, scr)
    maxt = max(e & 0x3FF for e in ent)
    if any(e >> 12 for e in ent):
        return 4
    if pal is not None and len(pal) >= 256 and (maxt + 1) * 64 <= len(chr_):
        return 8
    if (maxt + 1) * 32 <= len(chr_) < (maxt + 1) * 64:
        return 4
    return 8 if pal is not None and len(pal) >= 256 else 4


def layout_tilesheet(chr_, pal, bpp, per_row=32):
    tb = 32 if bpp == 4 else 64
    n = len(chr_) // tb
    if n == 0:
        return None
    rows = (n + per_row - 1) // per_row
    lay = Layout(per_row * 8, rows * 8, bpp, pal, {'chr': chr_})
    for t in range(n):
        lay.add((t % per_row) * 8, (t // per_row) * 8, 'chr', t)
    return lay


def render_tilesheet(chr_, pal, bpp, per_row=32):
    lay = layout_tilesheet(chr_, pal, bpp, per_row)
    return lay.render() if lay else None
