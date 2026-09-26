"""의존성 없는 PNG 입출력. 편집용으로 인덱스(팔레트) PNG 를 쓰고, 어떤 PNG 든 읽는다."""
import struct, zlib


def _chunk(t, d):
    return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)


def write_indexed(path, w, h, pix, pal, transparent0=True):
    """pix: 길이 w*h 의 팔레트 인덱스(0..255). pal: [(r,g,b)] 최대 256"""
    pal = list(pal)[:256] or [(0, 0, 0)]
    raw = b''.join(b'\x00' + bytes(pix[y * w:(y + 1) * w]) for y in range(h))
    out = b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 3, 0, 0, 0))
    out += _chunk(b'PLTE', b''.join(bytes(c) for c in pal))
    if transparent0:
        out += _chunk(b'tRNS', b'\x00')
    out += _chunk(b'IDAT', zlib.compress(raw, 9)) + _chunk(b'IEND', b'')
    open(path, 'wb').write(out)


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def read_png(path):
    """반환: (w, h, idx, rgba)
       idx  : 인덱스 PNG 이면 픽셀 인덱스 리스트, 아니면 None
       rgba : [(r,g,b,a)] 리스트 (항상)"""
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n', 'PNG 아님'
    p = 8; idat = b''; pal = []; trns = b''
    while p < len(d):
        ln = struct.unpack_from('>I', d, p)[0]; t = d[p + 4:p + 8]; body = d[p + 8:p + 8 + ln]
        p += 12 + ln
        if t == b'IHDR':
            w, h, bd, ct, _, _, il = struct.unpack('>IIBBBBB', body)
        elif t == b'PLTE':
            pal = [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]
        elif t == b'tRNS':
            trns = body
        elif t == b'IDAT':
            idat += body
        elif t == b'IEND':
            break
    assert il == 0, '인터레이스 PNG 미지원'
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    if bd == 16:
        raise ValueError('16비트 PNG 미지원: 8비트로 저장하세요')
    bpp_bits = ch * bd
    stride = (w * bpp_bits + 7) // 8
    fb = max(1, bpp_bits // 8)
    raw = zlib.decompress(idat)
    rows = []; prev = bytearray(stride); o = 0
    for y in range(h):
        f = raw[o]; line = bytearray(raw[o + 1:o + 1 + stride]); o += 1 + stride
        for i in range(stride):
            a = line[i - fb] if i >= fb else 0
            b = prev[i]; c = prev[i - fb] if i >= fb else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif f == 4: line[i] = (line[i] + _paeth(a, b, c)) & 255
        rows.append(line); prev = line
    idx = [] if ct == 3 else None
    rgba = []
    for line in rows:
        if bd < 8:
            vals = []
            per = 8 // bd
            for x in range(w):
                byte = line[x // per]
                sh = 8 - bd * (x % per + 1)
                vals.append((byte >> sh) & ((1 << bd) - 1))
        else:
            vals = line
        for x in range(w):
            if ct == 3:
                i = vals[x]; idx.append(i)
                r, g, b = pal[i] if i < len(pal) else (0, 0, 0)
                a = trns[i] if i < len(trns) else 255
                rgba.append((r, g, b, a))
            elif ct == 0:
                v = vals[x]; v = v * 255 // ((1 << bd) - 1); rgba.append((v, v, v, 255))
            elif ct == 2:
                rgba.append((vals[x * 3], vals[x * 3 + 1], vals[x * 3 + 2], 255))
            elif ct == 4:
                v = vals[x * 2]; rgba.append((v, v, v, vals[x * 2 + 1]))
            else:
                rgba.append(tuple(vals[x * 4:x * 4 + 4]))
    return w, h, idx, rgba
