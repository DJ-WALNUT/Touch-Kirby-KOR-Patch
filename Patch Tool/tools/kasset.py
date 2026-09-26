"""에셋 모델: ROM 파일 -> 편집용 뷰(레이아웃) -> 수정된 파일 바이트.

group_of(rom, name) 으로 묶음 단위를 정하고(BG 는 chr 하나 + scr 여러 개),
load_group() 이 레이아웃 뷰 목록을, apply_edits() 가 PNG 수정분을 반영한 새 파일 바이트를 만든다.
"""
import re, struct
from ndslib import decomp, lz77_compress
import kfmt

# 타일 용량이 모자랄 때 거의 같은 타일(최대 N픽셀 차이)을 합쳐도 되는 그래픽 (눈에 안 띄는 배경 격자 등)
LOSSY_MERGE = {'chr_title.bin': 1}

# 이름 규칙으로 못 찾는 chr <-> scr 짝
EXTRA_SCR = {
    'z_chr_ed04f.bin': ['z_scr_ed04af.bin', 'z_scr_ed04bf.bin'],
    'chr_chgmedaltopbgs.bin': ['scr_chgmedalmesbgs.bin', 'scr_chgmedaliconbgs.bin'],
    'chr_configpagebg.bin': ['scr_configpictopagebg.bin'],
    'chr_pausetrialfont.bin': ['scr_pauselinebg.bin', 'scr_pausetimebg.bin'],
}
SCR_TO_CHR = {s: c for c, l in EXTRA_SCR.items() for s in l}

# 레슨 텍스트/그림 캔버스 (타일 16개 폭). 게임은 공용 z_chr_lesson 위 0x170 번 타일부터 (실기 사진으로 확인) 이 캔버스를 올리고
# 맵(텍스트 페이지는 코드 안, 그림 페이지는 z_scr_lessonNN_M)으로 배치한다
TILESHEET_WIDTH = [(re.compile(r'z_chr_lesson\d\d_\d\.bin$'), 16)]


def dec(rom, n):
    return decomp(rom[n])


def stem_of(base):
    return re.sub(r'^(z_)?(chr|scr|col)_', '', base[:-4])


def find_pal(rom, d, stem):
    """col_<stem> 정확 일치 > stem 의 접두사인 col_ 중 가장 긴 것"""
    best = None
    for n in rom:
        if not n.startswith(d):
            continue
        m = re.match(r'(z_)?col_(.+)\.bin$', n[len(d):])
        if not m:
            continue
        cs = m.group(2)
        if cs == stem:
            return n
        if stem.startswith(cs) and (best is None or len(cs) > best[0]):
            best = (len(cs), n)
    return best[1] if best else None


def find_chr(rom, d, stem, base=None):
    if base in SCR_TO_CHR:
        return d + SCR_TO_CHR[base]
    s = stem
    while s:
        for pre in ('chr_', 'z_chr_'):
            if d + pre + s + '.bin' in rom:
                return d + pre + s + '.bin'
        s2 = re.sub(r'(_?\d+)$', '', s)
        if s2 == s:
            break
        s = s2
    return None


def find_scrs(rom, d, stem, base=None):
    if base in EXTRA_SCR:
        return [d + x for x in EXTRA_SCR[base]]
    for pre in ('scr_', 'z_scr_'):
        if d + pre + stem + '.bin' in rom:
            return [d + pre + stem + '.bin']
    return sorted(n for n in rom if n.startswith((d + 'scr_' + stem + '_', d + 'z_scr_' + stem + '_')))


def group_of(rom, name):
    """반환: (그룹키, 종류). 종류: c05 c06 bg sheet pal skip"""
    d, base = name.rsplit('/', 1)
    d += '/'
    data, _ = dec(rom, name)
    if kfmt.parse_container(data):
        return name, 'c05'
    if kfmt.parse_container6(data):
        return name, 'c06'
    if base.startswith('col_'):
        return name, 'pal'
    if base.startswith('bmp_') and kfmt.parse_bmp(data):
        return name, 'bmp'
    if base.startswith(('map_', 'bmp_')):
        return name, 'skip'
    stem = stem_of(base)
    if 'scr_' in base:
        if base.startswith('z_scr_lesson'):
            return name, 'skip'  # 레슨 그림 페이지 맵 (캔버스 쪽에서 편집)
        c = find_chr(rom, d, stem, base)
        return (c, 'bg') if c else (name, 'skip')
    if base.startswith(('chr_', 'z_chr_')):
        if any(rx.search(name) for rx, _ in TILESHEET_WIDTH):
            return name, 'sheet'  # 레슨 캔버스: 맵이 공용 타일 위에 겹쳐 쓰므로 캔버스 그대로 편집
        return name, ('bg' if find_scrs(rom, d, stem, base) else 'sheet')
    return name, 'skip'


class Group:
    """편집 단위. views: [(라벨, Layout, meta)]"""

    def __init__(self, rom, key, kind):
        self.rom, self.key, self.kind = rom, key, kind
        self.views = []
        self.files = [key]
        self.pal_name = None
        d, base = key.rsplit('/', 1)
        d += '/'
        data, comp = dec(rom, key)
        self.comp = {key: comp}
        if kind == 'c05':
            self.obj = kfmt.parse_container(data)
            self.raw = data
            lay = kfmt.layout_container(self.obj)
            if lay:
                self.views.append(('', lay, None))
            self.bpp = self.obj['bpp']
        elif kind == 'c06':
            self.obj = kfmt.parse_container6(data)
            self.raw = data
            lay = kfmt.layout_container6(self.obj)
            if lay:
                self.views.append(('', lay, None))
            self.bpp = self.obj['bpp']
        elif kind == 'bmp':
            self.obj = kfmt.parse_bmp(data)
            self.raw = data
            self.views.append(('', kfmt.layout_bmp(self.obj), None))
            self.bpp = 8
        elif kind in ('bg', 'sheet'):
            stem = stem_of(base)
            self.chr = bytearray(data)
            pn = find_pal(rom, d, stem)
            self.pal_name = pn
            pal = kfmt.pal_from(dec(rom, pn)[0]) if pn else []
            self.scrs = {}
            if kind == 'bg':
                for sn in find_scrs(rom, d, stem, base):
                    sd, sc = dec(rom, sn)
                    self.scrs[sn] = bytearray(sd)
                    self.comp[sn] = sc
                    self.files.append(sn)
                first = next(iter(self.scrs.values()))
                self.bpp = kfmt.guess_bg_bpp(self.chr, pal if pn else None, first)
                if self.bpp == 4 and pal:
                    # 팔레트 파일이 맵이 쓰는 뱅크보다 짧으면, 맵의 가장 낮은 뱅크부터 로드된 것으로 봄
                    banks = {e >> 12 for sd in self.scrs.values()
                             for e in struct.unpack_from('<%dH' % (len(sd) // 2), sd)}
                    if max(banks) >= len(pal) // 16:
                        pal = [(0, 0, 0)] * (16 * min(banks)) + pal
                fullpal, _ = kfmt.full_palette(pal, self.bpp)
                for sn, sd in self.scrs.items():
                    lay = kfmt.layout_bg(self.chr, fullpal, sd, self.bpp)
                    # 배치마다 맵 엔트리 번호 기록 (새 타일 할당용)
                    lay.refs = [(sn, i) for i in range(len(sd) // 2)]
                    self.views.append((sn.rsplit('/', 1)[1][:-4], lay, sn))
            else:
                if any(rx.search(key) for rx, _ in TILESHEET_WIDTH):
                    pal = []  # 레슨 캔버스: 실제 뱅크는 맵이 정함 -> 식별용 팔레트로 표시
                self.bpp = 8 if len(pal) >= 256 and len(self.chr) % 64 == 0 else 4
                fullpal, _ = kfmt.full_palette(pal, self.bpp)
                per_row = 32
                for rx, w in TILESHEET_WIDTH:
                    if rx.search(key):
                        per_row = w
                lay = kfmt.layout_tilesheet(self.chr, fullpal, self.bpp, per_row)
                if lay:
                    self.views.append(('', lay, None))
        # 모든 뷰의 팔레트를 256색으로 통일 (PNG 인덱스 = 뱅크*16 + 값)
        for _, lay, _ in self.views:
            lay.pal, _ = kfmt.full_palette(lay.pal, self.bpp)

    # ------------------------------------------------------------ 재삽입
    def _wants(self, vi, png, warn):
        """뷰 하나의 PNG -> [(배치번호, buf, tile, 원하는 타일 내용)]. png 가 None 이면 원본 그대로."""
        lbl, lay, _ = self.views[vi]
        out = []
        if png is None:
            for pi, (x, y, b, t, hf, vf, bank) in enumerate(lay.pl):
                cur = kfmt.tile_get(lay.bufs[b], t, lay.bpp)
                if cur is not None:
                    out.append((pi, b, t, tuple(cur)))
            return out
        w, h, idx, rgba = png
        if (w, h) != (lay.w, lay.h):
            raise ValueError('크기 불일치: PNG %dx%d, 원본 %dx%d' % (w, h, lay.w, lay.h))
        # 1. 픽셀마다 가장 위 배치(top), 그 아래에서 보이는 값(below), 현재 화면 값(shown)
        #    바뀐 픽셀은 가장 위 레이어에만 쓴다 (아래 공용 틀 스프라이트가 메시지마다 복제되는 것 방지).
        #    바뀐 값이 아래 레이어가 보여 주는 값과 같으면 위 레이어를 투명하게 만든다.
        #    투명으로 지운 픽셀은 모든 레이어에서 비운다.
        is_bg = hasattr(lay, 'refs')
        top = [-1] * (w * h)
        shown = [0] * (w * h)
        below = [0] * (w * h)
        bpp = lay.bpp
        for pi, (x, y, b, t, hf, vf, bank) in enumerate(lay.pl):
            pix = kfmt.tile_get(lay.bufs[b], t, bpp)
            if pix is None:
                continue
            pix = kfmt.flip(pix, hf, vf)
            for k in range(64):
                px, py = x + k % 8, y + k // 8
                if 0 <= px < w and 0 <= py < h:
                    o = py * w + px
                    below[o] = shown[o]
                    top[o] = pi
                    if pix[k]:
                        shown[o] = pix[k] + (bank * 16 if bpp == 4 else 0)
        # 2. 배치 밖에 그린 픽셀 경고
        outside = sum(1 for o in range(w * h)
                      if top[o] < 0 and rgba[o][3] >= 128 and not (idx and idx[o] == 0))
        if outside:
            warn.append('%s: 편집 가능 영역(스프라이트/타일) 밖 픽셀 %d개는 무시됨' % (lbl or 'view', outside))
        # 3. 배치별 원하는 타일 내용
        pal = lay.pal
        cache = {}

        def new_index(o):
            """PNG 픽셀 -> 팔레트 인덱스(0 = 투명). RGB PNG 는 None (색 비교로 처리)"""
            if rgba[o][3] < 128 or (idx is not None and idx[o] == 0):
                return 0
            return idx[o] if idx is not None else None

        def same(o, pal_i):
            ni = new_index(o)
            if ni is not None:
                return ni == pal_i
            if pal_i == 0:
                return rgba[o][3] < 128
            return rgba[o][3] >= 128 and tuple(rgba[o][:3]) == tuple(pal[pal_i])

        def to_val(o, bank):
            r, g, b, a = rgba[o]
            if a < 128 or (idx is not None and idx[o] == 0):
                return 0
            if idx is not None:
                i = idx[o]
                if bpp == 8:
                    return i
                if i // 16 == bank:
                    return i % 16
                r, g, b = pal[i] if i < len(pal) else (r, g, b)
            key = (r, g, b, bank)
            if key in cache:
                return cache[key]
            lo = bank * 16 if bpp == 4 else 0
            hi = lo + (16 if bpp == 4 else 256)
            best, bd = 1, 1 << 30
            for j in range(lo + 1, hi):
                pr, pg, pb = pal[j]
                dd = (pr - r) ** 2 + (pg - g) ** 2 + (pb - b) ** 2
                if dd < bd:
                    best, bd = j, dd
            v = best - lo
            cache[key] = v
            return v

        for pi, (x, y, b, t, hf, vf, bank) in enumerate(lay.pl):
            cur = kfmt.tile_get(lay.bufs[b], t, bpp)
            if cur is None:
                continue
            new = kfmt.flip(cur, hf, vf)
            for k in range(64):
                px, py = x + k % 8, y + k // 8
                if not (0 <= px < w and 0 <= py < h):
                    continue
                o = py * w + px
                if same(o, shown[o]):
                    continue
                if top[o] != pi:
                    if same(o, 0):
                        new[k] = 0  # 투명하게 지우는 곳은 아래 레이어까지 비움
                    continue
                if below[o] and same(o, below[o]):
                    new[k] = 0
                else:
                    new[k] = to_val(o, bank)
            if is_bg and bpp == 4:
                # BG: 원래 뱅크로 색을 정확히 못 그리면, 오차가 가장 적은 뱅크로 바꾼다 (맵 엔트리의 팔레트 비트)
                cells = [(py * w + px) for k in range(64)
                         for px, py in [(x + k % 8, y + k // 8)] if 0 <= px < w and 0 <= py < h]
                nb = self._best_bank(cells, rgba, idx, pal, bank)
                if nb != bank:
                    new = [to_val(o, nb) for o in cells] if len(cells) == 64 else new
                    self._newbank[(vi, pi)] = nb
            out.append((pi, b, t, tuple(kfmt.flip(new, hf, vf))))
        return out

    def _best_bank(self, cells, rgba, idx, pal, bank):
        """8x8 칸의 목표 색을 가장 정확히 표현하는 16색 뱅크. 원래 뱅크가 정확하면 그대로"""
        want = []
        for o in cells:
            r, g, b, a = rgba[o]
            if a < 128 or (idx is not None and idx[o] == 0):
                continue
            want.append(tuple(pal[idx[o]]) if idx is not None and idx[o] < len(pal) else (r, g, b))
        if not want:
            return bank
        nbank = min(16, len(pal) // 16)

        def err(bk):
            cols = [pal[bk * 16 + j] for j in range(1, 16)]
            e = 0
            for c in want:
                w_ = 0.05 if c[0] == c[1] == c[2] else 1  # 회색(안티앨리어싱)보다 유채색 정확도 우선
                e += w_ * min((c[0] - q[0]) ** 2 + (c[1] - q[1]) ** 2 + (c[2] - q[2]) ** 2 for q in cols)
            return e
        e0 = err(bank)
        if e0 == 0:
            return bank
        best = min(range(nbank), key=lambda bk: (err(bk), bk != bank))
        return best if err(best) < e0 else bank

    def apply_all(self, pngs):
        """pngs: 뷰마다 PNG(w, h, idx|None, rgba) 또는 None(변경 없음).
        같은 chr 를 쓰는 모든 맵을 함께 계산해야 공유 타일이 다른 화면에서 깨지지 않는다. 반환: 경고 목록"""
        warn = []
        self._newbank = {}
        want = {}  # (buf, tile) -> [((view, 배치), 내용)]
        for vi, png in enumerate(pngs):
            for pi, b, t, c in self._wants(vi, png, warn):
                want.setdefault((b, t), []).append(((vi, pi), c))
        if self.kind == 'c05':
            self._resolve_sprites(want, warn)
        elif self.kind == 'bg':
            self._resolve_bg(want, warn)
        elif self.kind == 'bmp':
            # 타일을 늘릴 수 없으므로 제자리에만 쓴다. 여러 곳이 같이 쓰는 타일을 한 곳만 바꾸면 실패
            lay0 = self.views[0][1]
            for (b, t), lst in want.items():
                cs = {c for _, c in lst}
                if len(cs) > 1:
                    x, y = lay0.pl[lst[0][0][1]][:2]
                    raise ValueError('공유 타일 %d (%d,%d 등 %d곳): 한 곳만 바꿀 수 없음' % (t, x, y, len(lst)))
                c = cs.pop()
                if c != tuple(kfmt.tile_get(lay0.bufs[b], t, 8)):
                    kfmt.tile_put(lay0.bufs[b], t, 8, c)
        else:
            lay0 = self.views[0][1]
            for (b, t), lst in want.items():
                cs = {c for _, c in lst}
                cur = tuple(kfmt.tile_get(lay0.bufs[b], t, lay0.bpp))
                changed = [c for c in cs if c != cur]
                if changed:
                    kfmt.tile_put(lay0.bufs[b], t, lay0.bpp, changed[0])
                if len(changed) > 1:
                    warn.append('공유 타일 %d: 서로 다르게 편집됨 (첫 번째 편집 적용)' % t)
        return warn

    # ---- 스프라이트 (05): OAM 오브젝트 단위로 처리
    def _resolve_sprites(self, want, warn):
        c = self.obj
        lay = self.views[0][1]
        bpp, unit = c['bpp'], c['unit']
        tiles = c['tiles']
        tb = 32 if bpp == 4 else 64
        tu = unit if bpp == 4 else max(1, unit // 2)   # attr2 1 당 (bpp 기준) 타일 수
        desired = {}
        for (b, t), lst in want.items():
            for (vi, pi), cont in lst:
                desired[pi] = cont
        # 오브젝트별 원하는 타일 목록. 여러 셀이 같은 OAM 레코드를 공유할 수 있으므로 파일 위치로 묶는다.
        objs = {}   # OAM 레코드 파일 위치 -> {k: 내용}
        where = {}  # 파일 위치 -> [(cell, j)]
        clash = 0
        for pi, (cell, j, k) in enumerate(lay.orefs):
            if pi not in desired:
                continue
            off = c['cell_offs'][cell] + j * 8
            if (cell, j) not in where.setdefault(off, []):
                where[off].append((cell, j))
            ks = objs.setdefault(off, {})
            if k in ks and ks[k] != desired[pi]:
                clash += 1
                continue
            ks[k] = desired[pi]
        if clash:
            warn.append('같은 OAM 레코드를 쓰는 셀끼리 편집이 다름: 타일 %d개 (첫 편집 적용)' % clash)
        objs = {off: tuple(ks[k] for k in range(len(ks))) for off, ks in objs.items() if set(ks) == set(range(len(ks)))}
        over = self._pack_sprites(objs, where, warn)
        if over:
            # 원래 영역에 안 들어가는 블록은 끝에 추가 (게임이 원래 크기만큼만 VRAM 을 잡으면 깨짐 → 번역 배치를 고쳐야 함)
            for off in over:
                bs = self._alloc_block(tiles, bpp, tu, objs[off])
                self._set_obj_base(off, where, bs // tu)
            warn.append('타일 용량 초과: 블록 %d개를 원래 영역 밖에 추가함 (%d -> %d 바이트) — 게임에서 깨질 수 있음'
                        % (len(over), c['ntile_bytes'], len(tiles)))
        # 레이아웃 갱신 (다시 그릴 때 새 번호 반영)
        self.views[0] = (self.views[0][0], kfmt.layout_container(c), None)

    def _obj_list(self):
        """[(OAM 위치, cell, j, n타일, base)] 전체 오브젝트"""
        c = self.obj
        tu = c['unit'] if c['bpp'] == 4 else max(1, c['unit'] // 2)
        out = []
        for ci, cell in enumerate(c['cells']):
            for j, (a0, a1, a1f, a2) in enumerate(cell):
                w, h = kfmt.OBJ_SIZE.get((a0 >> 14, a1 >> 14), (8, 8))
                out.append((c['cell_offs'][ci] + j * 8, ci, j, w * h // 64, (a2 & 0x3FF) * tu))
        return out

    def _set_obj_base(self, off, where, idx):
        c = self.obj
        for cell, j in where[off]:
            a0, a1, a1f, a2 = c['cells'][cell][j]
            na2 = (a2 & 0xFC00) | idx
            c['cells'][cell][j] = (a0, a1, a1f, na2)
        c['oam_patch'][off + 6] = na2

    def _pack_sprites(self, objs, where, warn):
        """objs {OAM 위치: 원하는 블록 내용}. 원래 타일 영역 안에 배치하고 attr2 갱신. 반환: 못 넣은 OAM 위치 목록"""
        c = self.obj
        bpp = c['bpp']
        tiles = c['tiles']
        tb = 32 if bpp == 4 else 64
        tu = c['unit'] if bpp == 4 else max(1, c['unit'] // 2)
        total = c['ntile_bytes'] // tb
        cur = lambda t: tuple(kfmt.tile_get(tiles, t, bpp))
        allobj = self._obj_list()
        base_of = {o[0]: o[4] for o in allobj}
        pinned = set()
        for off, ci, j, n, bs in allobj:
            if off not in objs:
                pinned.update(range(bs, bs + n))  # 편집 대상이 아닌 오브젝트는 제자리 고정
        # 원본에서 OAM 이 참조하던 타일은 회수 가능, 그 밖(코드가 쓸 수 있음)과 고정 오브젝트 타일은 보호
        free = c['orig_ref'] - pinned
        occ = {t: cur(t) for t in range(total) if t not in free}

        def fits(bs, cont):
            return bs + len(cont) <= total and all(occ.get(bs + k, cont[k]) == cont[k] for k in range(len(cont)))

        def put(bs, cont):
            for k in range(len(cont)):
                occ[bs + k] = cont[k]

        placed = {}
        order = sorted(objs, key=lambda o: (-len(objs[o]), o))
        for off in order:  # 1) 원래 자리에 그대로 둘 수 있으면 그대로
            bs, cont = base_of[off], objs[off]
            if all(cur(bs + k) == cont[k] for k in range(len(cont))) and fits(bs, cont):
                placed[off] = bs
                put(bs, cont)
        by_cont = {}
        for off, bs in placed.items():
            by_cont.setdefault(objs[off], bs)
        over = []
        for off in order:  # 2) 같은 내용이 이미 있으면 공유, 없으면 빈 정렬 위치
            if off in placed:
                continue
            cont = objs[off]
            bs = by_cont.get(cont)
            if bs is None:
                bs = next((x for x in range(0, total - len(cont) + 1, tu) if fits(x, cont)), None)
            if bs is None:
                over.append(off)
                continue
            placed[off] = bs
            by_cont.setdefault(cont, bs)
            put(bs, cont)
        for t, cn in occ.items():
            kfmt.tile_put(tiles, t, bpp, cn)
        moved = 0
        for off, bs in placed.items():
            if bs != base_of[off]:
                moved += 1
                self._set_obj_base(off, where, bs // tu)
        if moved:
            warn.append('스프라이트 블록 %d개를 원래 영역 안에서 재배치함' % moved)
        return over

    def _alloc_block(self, tiles, bpp, tu, cont):
        """같은 내용 블록이 정렬 위치에 이미 있으면 재사용, 없으면 끝에 정렬해서 추가. 반환: bpp 기준 타일 번호"""
        tb = 32 if bpp == 4 else 64
        n = len(cont)
        total = len(tiles) // tb
        for base in range(0, total - n + 1, tu):
            if all(tuple(kfmt.tile_get(tiles, base + k, bpp)) == cont[k] for k in range(n)):
                return base
        base = -(-total // tu) * tu
        tiles.extend(b'\0' * ((base + n) * tb - len(tiles)))
        for k in range(n):
            kfmt.tile_put(tiles, base + k, bpp, cont[k])
        return base

    # ---- BG
    def _resolve_bg(self, want, warn):
        lay0 = self.views[0][1]
        bufs, bpp = lay0.bufs, lay0.bpp
        orig_len = len(self.chr)
        allocs = []
        # 1차: 제자리 쓰기 결정
        for (b, t), lst in want.items():
            cur = tuple(kfmt.tile_get(bufs[b], t, bpp))
            groups = {}
            for ref, c in lst:
                groups.setdefault(c, []).append(ref)
            if len(groups) == 1:
                c = next(iter(groups))
                if c != cur:
                    kfmt.tile_put(bufs[b], t, bpp, c)
                continue
            # 원본 내용을 원하는 쪽이 타일을 유지, 나머지는 새 타일
            keep = cur if cur in groups else max(groups, key=lambda c: len(groups[c]))
            if keep != cur:
                kfmt.tile_put(bufs[b], t, bpp, keep)
            for c, refs in groups.items():
                if c != keep:
                    allocs.append((b, c, refs))
        # 2차: 새 타일 할당. 이 그룹의 맵들이 쓰던 타일 중 편집 후 아무도 안 쓰게 된 것은 빈자리로 재활용.
        # 원래부터 맵에 안 쓰이던 타일은 코드가 쓸 수도 있으니 건드리지 않음.
        moving = {ref for _, _, refs in allocs for ref in refs}
        used_before, used_after = set(), set()
        for (b, t), lst in want.items():
            for ref, c in lst:
                used_before.add(t)
                if ref not in moving:
                    used_after.add(t)
        free = sorted(used_before - used_after - {0})
        for b, c, refs in allocs:
            nt = self._alloc_tile(bufs[b], bpp, c, free)
            for vi, pi in refs:
                self._set_entry(vi, pi, nt, None, None)
        # 3차: 원래 크기를 넘으면 반전 포함 중복 타일을 합쳐 다시 배치
        if len(self.chr) > orig_len:
            self._repack(used_before, orig_len, warn)
        # 팔레트 뱅크를 바꾼 맵 엔트리 반영
        for (vi, pi), nb in self._newbank.items():
            lay = self.views[vi][1]
            sn, ei = lay.refs[pi]
            e = struct.unpack_from('<H', self.scrs[sn], ei * 2)[0]
            struct.pack_into('<H', self.scrs[sn], ei * 2, (e & 0x0FFF) | (nb << 12))
            x, y, bb, t, hf, vf, _ = lay.pl[pi]
            lay.pl[pi] = (x, y, bb, t, hf, vf, nb)
        if self._newbank:
            warn.append('팔레트 뱅크를 바꾼 타일 %d개' % len(self._newbank))

    def _lossy_merge(self, uniq, need, maxd, warn):
        """uniq {정규형: 사용 횟수} 에서 차이가 maxd 픽셀 이하인 쌍을 need 개 합친다.
        반환 {없앨 정규형: (남길 정규형, h, v)}  (없앨 것 ≈ flip(남길 것, h, v))"""
        keys = list(uniq)
        cand = []
        for i, a in enumerate(keys):
            va = [(tuple(kfmt.flip(list(a), h, v)), h, v) for h in (0, 1) for v in (0, 1)]
            for b in keys[i + 1:]:
                for fa, h, v in va:
                    dd = sum(1 for p, q in zip(fa, b) if p != q)
                    if dd <= maxd:
                        # 덜 쓰이는 쪽을 없앰
                        if uniq[b] <= uniq[a]:
                            cand.append((dd, uniq[b], b, (a, h, v)))
                        else:
                            cand.append((dd, uniq[a], a, (b, h, v)))
                        break
        cand.sort(key=lambda c: (c[0], c[1]))
        remap, touched = {}, set()
        for dd, cnt, gone, (keep, h, v) in cand:
            if len(remap) >= need:
                break
            if gone in touched or keep in touched:
                continue
            remap[gone] = (keep, h, v)
            touched.update((gone, keep))
        if remap:
            warn.append('용량 맞춤: 거의 같은 타일 %d쌍을 합침 (각 %d픽셀 이하 차이)' % (len(remap), maxd))
        return remap

    def _set_entry(self, vi, pi, t, hf, vf):
        lay = self.views[vi][1]
        sn, ei = lay.refs[pi]
        e = struct.unpack_from('<H', self.scrs[sn], ei * 2)[0]
        x, y, bb, _, ohf, ovf, bank = lay.pl[pi]
        if hf is None:
            hf, vf = ohf, ovf
        e = (e & 0xF000) | (vf << 11) | (hf << 10) | t
        struct.pack_into('<H', self.scrs[sn], ei * 2, e)
        lay.pl[pi] = (x, y, bb, t, hf, vf, bank)

    def _repack(self, used_orig, orig_len, warn):
        bpp = self.bpp
        tb = 32 if bpp == 4 else 64
        chr_ = self.chr
        before = len(chr_)
        tile0 = tuple(kfmt.tile_get(chr_, 0, bpp))
        # 모든 배치의 화면상 내용 -> 반전 정규형
        items = []
        for vi, (_, lay, _) in enumerate(self.views):
            for pi, (x, y, b, t, hf, vf, bank) in enumerate(lay.pl):
                d = tuple(kfmt.flip(kfmt.tile_get(chr_, t, bpp), hf, vf))
                best = None
                for fh in (0, 1):
                    for fv in (0, 1):
                        s = tuple(kfmt.flip(list(d), fh, fv))
                        if best is None or s < best[0]:
                            best = (s, fh, fv)
                items.append((vi, pi, d, best))
        # 슬롯: 원래 맵이 쓰던 타일 번호 (0 제외) + 필요하면 끝에 추가
        orig_n = orig_len // tb
        slots = sorted(t for t in used_orig if 0 < t < orig_n)
        # 용량이 모자라고 허용된 그래픽이면, 거의 같은 정규형끼리 합친다 (차이 픽셀 수가 적은 쌍부터)
        maxd = LOSSY_MERGE.get(self.key.rsplit('/', 1)[1], 0)
        uniq = {}
        for vi, pi, d, (s, fh, fv) in items:
            if d != tile0 and s != tile0:
                uniq[s] = uniq.get(s, 0) + 1
        need = len(uniq) - len(slots)
        if maxd and need > 0:
            remap = self._lossy_merge(uniq, need, maxd, warn)
            if remap:
                new_items = []
                for vi, pi, d, (s, fh, fv) in items:
                    if s in remap:
                        a, h, v = remap[s]
                        new_items.append((vi, pi, tuple(kfmt.flip(list(a), h ^ fh, v ^ fv)), (a, h ^ fh, v ^ fv)))
                    else:
                        new_items.append((vi, pi, d, (s, fh, fv)))
                items = new_items
        orig_content = {t: tuple(kfmt.tile_get(chr_, t, bpp)) for t in slots}
        by_content = {}
        assign = {}
        # 반전 정규형(s) 기준으로만 합친다 (반전 관계인 타일은 한 장으로). 원래 자리에 같은 정규형이 있으면 그 자리 유지
        for t in slots:
            c = orig_content[t]
            s_ = min(tuple(kfmt.flip(list(c), fh, fv)) for fh in (0, 1) for fv in (0, 1))
            by_content.setdefault(s_, t)
        for vi, pi, d, (s, fh, fv) in items:
            if d == tile0 or s == tile0:
                continue
            if s in by_content and s not in assign:
                assign[s] = by_content[s]
        taken = set(assign.values())
        pool = [t for t in slots if t not in taken]
        new_chr = bytearray(chr_[:orig_len])
        for s_, t in assign.items():
            kfmt.tile_put(new_chr, t, bpp, s_)  # 반전 관계였던 자리는 정규형으로 다시 씀
        for vi, pi, d, (s, fh, fv) in items:
            if d == tile0:
                self._set_entry(vi, pi, 0, 0, 0)
                continue
            if s not in assign:
                if pool:
                    t = pool.pop(0)
                else:
                    t = len(new_chr) // tb
                    if t >= 1024:
                        raise ValueError('BG 타일 1024개 초과')
                    new_chr.extend(b'\0' * tb)
                kfmt.tile_put(new_chr, t, bpp, s)
                assign[s] = t
            self._set_entry(vi, pi, assign[s], fh, fv)
        self.chr[:] = new_chr
        warn.append('타일 재배치: %d -> %d 바이트 (원래 %d)' % (before, len(new_chr), orig_len))

    def _alloc_tile(self, buf, bpp, content, free=()):
        """같은 내용의 타일 재사용 > 빈자리(free, 소모됨) > 끝에 추가"""
        tb = 32 if bpp == 4 else 64
        n = len(buf) // tb
        free_set = set(free)
        for t in range(n):
            if t not in free_set and tuple(kfmt.tile_get(buf, t, bpp)) == content:
                return t
        if free:
            t = free.pop(0)
            kfmt.tile_put(buf, t, bpp, content)
            return t
        if n >= 1024:
            raise ValueError('BG 타일 1024개 초과')
        buf.extend(b'\0' * tb)
        kfmt.tile_put(buf, n, bpp, content)
        return n

    def tile_growth(self):
        if self.kind in ('bg', 'sheet'):
            o, _ = dec(self.rom, self.key)
            return len(o), len(self.chr)
        return None

    def output(self):
        """반환 {파일명: 원본 ROM 에 넣을 바이트(압축 포함)}"""
        out = {}
        if self.kind == 'c05':
            out[self.key] = kfmt.build_container(self.raw, self.obj)
        elif self.kind == 'c06':
            out[self.key] = kfmt.build_container6(self.raw, self.obj)
        elif self.kind == 'bmp':
            out[self.key] = kfmt.build_bmp(self.raw, self.obj)
        else:
            out[self.key] = bytes(self.chr)
            for sn, sd in self.scrs.items():
                out[sn] = bytes(sd)
        res = {}
        for n, data in out.items():
            orig, comp = dec(self.rom, n)
            if data == orig:
                continue
            if self.kind in ('bg', 'sheet'):
                if comp == 'LZ77':
                    data = lz77_compress(data)
                elif comp:
                    raise ValueError('%s: %s 재압축 미지원' % (n, comp))
            res[n] = data
        return res
