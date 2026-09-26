import struct

# ---------- NDS filesystem ----------
def load_rom(path):
    d = open(path, 'rb').read()
    fnto, fnts, fato, fats = struct.unpack_from('<IIII', d, 0x40)
    fat = [struct.unpack_from('<II', d, fato + i*8) for i in range(fats//8)]
    files = []
    def sub(did, pre):
        off, ff, par = struct.unpack_from('<IHH', d, fnto + did*8)
        p = fnto + off; fid = ff
        while True:
            t = d[p]; p += 1
            if t == 0: break
            if t < 0x80:
                n = d[p:p+t].decode('ascii', 'replace'); p += t
                files.append((pre+n, fid)); fid += 1
            else:
                l = t & 0x7F
                n = d[p:p+l].decode('ascii', 'replace'); p += l
                s = struct.unpack_from('<H', d, p)[0]; p += 2
                sub(s & 0xFFF, pre + n + '/')
    sub(0, '/')
    return {n: d[fat[f][0]:fat[f][1]] for n, f in files if f < len(fat)}

# ---------- Nintendo compression ----------
def lz77(d):
    size = struct.unpack_from('<I', d, 0)[0] >> 8
    out = bytearray(); p = 4
    while len(out) < size and p < len(d):
        fl = d[p]; p += 1
        for i in range(8):
            if len(out) >= size: break
            if fl & (0x80 >> i):
                if p + 1 >= len(d): return bytes(out)
                b1, b2 = d[p], d[p+1]; p += 2
                ln = (b1 >> 4) + 3
                disp = (((b1 & 0xF) << 8) | b2) + 1
                if disp > len(out): return bytes(out)
                for _ in range(ln):
                    out.append(out[-disp])
            else:
                if p >= len(d): return bytes(out)
                out.append(d[p]); p += 1
    return bytes(out)

def lz11(d):
    size = struct.unpack_from('<I', d, 0)[0] >> 8
    p = 4
    if size == 0:
        size = struct.unpack_from('<I', d, 4)[0]; p = 8
    out = bytearray()
    while len(out) < size and p < len(d):
        fl = d[p]; p += 1
        for i in range(8):
            if len(out) >= size or p >= len(d): break
            if fl & (0x80 >> i):
                a = d[p]; ind = a >> 4
                if ind == 1:
                    if p+3 >= len(d): return bytes(out)
                    ln = (((a & 0xF) << 12) | (d[p+1] << 4) | (d[p+2] >> 4)) + 0x111
                    disp = (((d[p+2] & 0xF) << 8) | d[p+3]) + 1; p += 4
                elif ind == 0:
                    if p+2 >= len(d): return bytes(out)
                    ln = (((a & 0xF) << 4) | (d[p+1] >> 4)) + 0x11
                    disp = (((d[p+1] & 0xF) << 8) | d[p+2]) + 1; p += 3
                else:
                    if p+1 >= len(d): return bytes(out)
                    ln = ind + 1
                    disp = (((a & 0xF) << 8) | d[p+1]) + 1; p += 2
                if disp > len(out): return bytes(out)
                for _ in range(ln):
                    out.append(out[-disp])
            else:
                out.append(d[p]); p += 1
    return bytes(out)

def rle(d):
    size = struct.unpack_from('<I', d, 0)[0] >> 8
    out = bytearray(); p = 4
    while len(out) < size and p < len(d):
        f = d[p]; p += 1
        if f & 0x80:
            ln = (f & 0x7F) + 3
            if p >= len(d): break
            out.extend(bytes([d[p]]) * ln); p += 1
        else:
            ln = f + 1
            out.extend(d[p:p+ln]); p += ln
    return bytes(out)

def decomp(d):
    """returns (data, label). label '' = not compressed."""
    if len(d) < 8: return d, ''
    t = d[0]; size = struct.unpack_from('<I', d, 0)[0] >> 8
    if not (0 < size < 32*1024*1024): return d, ''
    try:
        if t == 0x10:
            r = lz77(d)
            if len(r) >= size * 0.9: return r, 'LZ77'
        elif t == 0x11:
            r = lz11(d)
            if len(r) >= size * 0.9: return r, 'LZ11'
        elif t == 0x30:
            r = rle(d)
            if len(r) >= size * 0.9: return r, 'RLE'
    except Exception:
        pass
    return d, ''

# ---------- PNG ----------
import zlib
def write_png(path, w, h, rgb):
    raw = b''.join(b'\x00' + bytes(rgb[y*w*3:(y+1)*w*3]) for y in range(h))
    def ch(t, dd):
        return struct.pack('>I', len(dd)) + t + dd + struct.pack('>I', zlib.crc32(t+dd) & 0xffffffff)
    open(path, 'wb').write(
        b'\x89PNG\r\n\x1a\n'
        + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
        + ch(b'IDAT', zlib.compress(raw, 6)) + ch(b'IEND', b''))

def bgr555(v):
    return ((v & 31)*255//31, ((v >> 5) & 31)*255//31, ((v >> 10) & 31)*255//31)

CHECKER = [(200,200,200),(160,160,160)]

def render_tiles(tiles, pal, per_row=32, scale=2):
    n = len(tiles)//32
    if n == 0: return None
    rows = (n + per_row - 1)//per_row
    W, H = per_row*8, rows*8
    buf = bytearray(W*H*3)
    # checkerboard background for index 0
    for y in range(H):
        for x in range(W):
            c = CHECKER[((x//4)+(y//4)) % 2]
            o = (y*W+x)*3; buf[o:o+3] = bytes(c)
    for t in range(n):
        tx, ty = (t % per_row)*8, (t//per_row)*8
        base = t*32
        for i in range(32):
            byte = tiles[base+i]; px = i*2
            for k, val in ((0, byte & 0xF), (1, byte >> 4)):
                if val == 0: continue
                x, y = tx + (px+k) % 8, ty + (px+k)//8
                o = (y*W+x)*3
                buf[o], buf[o+1], buf[o+2] = pal[val]
    if scale > 1:
        SW, SH = W*scale, H*scale
        s = bytearray(SW*SH*3)
        for y in range(SH):
            sy = y//scale
            for x in range(SW):
                sx = x//scale
                o, so = (sy*W+sx)*3, (y*SW+x)*3
                s[so:so+3] = buf[o:o+3]
        return SW, SH, s
    return W, H, buf


def lz77_compress(src):
    """Nintendo LZ77 (0x10) 압축. VRAM 안전(거리 >= 2). 해시 체인 탐색."""
    n = len(src)
    out = bytearray(struct.pack('<I', (n << 8) | 0x10))
    heads = {}
    prev = [-1] * n
    i = 0

    def insert(p):
        if p + 3 <= n:
            k = src[p:p + 3]
            prev[p] = heads.get(k, -1)
            heads[k] = p

    while i < n:
        flag_pos = len(out); out.append(0); flag = 0
        for bit in range(8):
            if i >= n:
                break
            best_len, best_d = 0, 0
            if i + 3 <= n:
                cand = heads.get(src[i:i + 3], -1)
                tries = 0
                maxl = min(18, n - i)
                while cand >= 0 and i - cand <= 4096 and tries < 256:
                    d = i - cand
                    if d >= 2:
                        l = 0
                        while l < maxl and src[cand + l] == src[i + l]:
                            l += 1
                        if l > best_len:
                            best_len, best_d = l, d
                            if l == maxl:
                                break
                    cand = prev[cand]; tries += 1
            if best_len >= 3:
                flag |= 0x80 >> bit
                v = ((best_len - 3) << 12) | (best_d - 1)
                out += bytes([v >> 8, v & 0xFF])
                for p in range(i, i + best_len):
                    insert(p)
                i += best_len
            else:
                out.append(src[i]); insert(i); i += 1
        out[flag_pos] = flag
    while len(out) % 4:
        out.append(0)
    return bytes(out)
