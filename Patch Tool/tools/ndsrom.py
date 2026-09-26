"""NDS ROM 파일 교체 + BPS 패치 생성."""
import struct, zlib


def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def file_ids(rom):
    """경로 -> 파일 ID"""
    fnto = struct.unpack_from('<I', rom, 0x40)[0]
    out = {}

    def sub(did, pre):
        off, ff, _ = struct.unpack_from('<IHH', rom, fnto + did * 8)
        p = fnto + off; fid = ff
        while True:
            t = rom[p]; p += 1
            if t == 0:
                break
            if t < 0x80:
                out[pre + rom[p:p + t].decode('ascii')] = fid; p += t; fid += 1
            else:
                l = t & 0x7F
                n = rom[p:p + l].decode('ascii'); p += l
                s = struct.unpack_from('<H', rom, p)[0]; p += 2
                sub(s & 0xFFF, pre + n + '/')
    sub(0, '/')
    return out


def replace_files(rom, repl):
    """rom: bytes, repl: {경로: 새 데이터}. 원래 자리에 들어가면 제자리, 아니면 ROM 끝에 추가."""
    rom = bytearray(rom)
    fato = struct.unpack_from('<I', rom, 0x48)[0]
    ids = file_ids(rom)
    used = struct.unpack_from('<I', rom, 0x80)[0]
    cap = len(rom)
    log = []
    for path, data in sorted(repl.items()):
        fid = ids[path]
        s, e = struct.unpack_from('<II', rom, fato + fid * 8)
        if len(data) <= e - s:
            rom[s:e] = data + b'\xFF' * (e - s - len(data))
            struct.pack_into('<II', rom, fato + fid * 8, s, s + len(data))
            log.append((path, 'inplace', e - s, len(data)))
        else:
            ns = (used + 0x1FF) & ~0x1FF
            if ns + len(data) > cap:
                raise ValueError('ROM 용량 부족: %s' % path)
            rom[ns:ns + len(data)] = data
            rom[s:e] = b'\xFF' * (e - s)
            struct.pack_into('<II', rom, fato + fid * 8, ns, ns + len(data))
            used = ns + len(data)
            log.append((path, 'append@%#x' % ns, e - s, len(data)))
    struct.pack_into('<I', rom, 0x80, max(used, struct.unpack_from('<I', rom, 0x80)[0]))
    struct.pack_into('<H', rom, 0x15E, crc16(rom[:0x15E]))
    return bytes(rom), log


# ---------------------------------------------------------------- BPS
def _num(n):
    out = bytearray()
    while True:
        x = n & 0x7F; n >>= 7
        if n == 0:
            out.append(0x80 | x); return bytes(out)
        out.append(x); n -= 1


def make_bps(src, dst, meta=b''):
    """단순 BPS: 같은 위치가 같으면 SourceRead, 다르면 TargetRead"""
    out = bytearray(b'BPS1')
    out += _num(len(src)) + _num(len(dst)) + _num(len(meta)) + meta
    i, n = 0, len(dst)
    ls = len(src)
    while i < n:
        j = i
        while j < n and j < ls and src[j] == dst[j]:
            j += 1
        if j - i >= 4 or (j > i and (j >= n or j >= ls)):
            out += _num(((j - i - 1) << 2) | 0)
            i = j
            continue
        # 다른 구간: 같은 바이트가 32개 이상 이어질 때까지 TargetRead
        j = i; same = 0
        while j < n:
            if j < ls and src[j] == dst[j]:
                same += 1
                if same >= 32:
                    j -= same - 1
                    break
            else:
                same = 0
            j += 1
        else:
            j = n
        if j <= i:
            j = i + 1
        out += _num(((j - i - 1) << 2) | 1) + dst[i:j]
        i = j
    out += struct.pack('<I', zlib.crc32(src) & 0xffffffff)
    out += struct.pack('<I', zlib.crc32(dst) & 0xffffffff)
    out += struct.pack('<I', zlib.crc32(out) & 0xffffffff)
    return bytes(out)


def apply_bps(src, patch):
    """검증용 BPS 적용기"""
    p = 4

    def rd():
        nonlocal p
        data, shift = 0, 1
        while True:
            x = patch[p]; p += 1
            data += (x & 0x7F) * shift
            if x & 0x80:
                return data
            shift <<= 7; data += shift
    ss, ts, ms = rd(), rd(), rd()
    p += ms
    out = bytearray(); sr = tr = 0
    end = len(patch) - 12
    while p < end:
        d = rd(); cmd, ln = d & 3, (d >> 2) + 1
        if cmd == 0:
            out += src[len(out):len(out) + ln]
        elif cmd == 1:
            out += patch[p:p + ln]; p += ln
        elif cmd == 2:
            o = rd(); sr += (-1 if o & 1 else 1) * (o >> 1)
            out += src[sr:sr + ln]; sr += ln
        else:
            o = rd(); tr += (-1 if o & 1 else 1) * (o >> 1)
            for _ in range(ln):
                out.append(out[tr]); tr += 1
    assert len(out) == ts
    assert zlib.crc32(out) & 0xffffffff == struct.unpack_from('<I', patch, len(patch) - 8)[0]
    return bytes(out)
