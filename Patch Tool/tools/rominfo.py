import struct, sys, os
from collections import Counter, defaultdict

MAGICS = {
    b'RGCN':'NCGR 타일그래픽', b'RLCN':'NCLR 팔레트', b'RCSN':'NSCR 스크린맵',
    b'RECN':'NCER 셀', b'RNAN':'NANR 셀애니', b'RTFN':'NFTR 폰트',
    b'CRAN':'NARC 아카이브', b'NARC':'NARC 아카이브', b'BMD0':'NSBMD 3D모델',
    b'BTX0':'NSBTX 텍스처', b'SDAT':'SDAT 사운드', b'RIFF':'RIFF',
    b'RESN':'NSCR?', b'RNCN':'NCEC?',
}
COMP = {0x10:'LZ77', 0x11:'LZ11', 0x24:'Huff4', 0x28:'Huff8', 0x30:'RLE', 0x40:'LZ40'}

def parse(path):
    d = open(path,'rb').read()
    h = {}
    title = d[0:12].rstrip(b'\0').decode('ascii','replace')
    gcode = d[0x0C:0x10].decode('ascii','replace')
    mcode = d[0x10:0x12].decode('ascii','replace')
    ver   = d[0x1E]
    a9o,a9e,a9l,a9s = struct.unpack_from('<IIII', d, 0x20)
    a7o,a7e,a7l,a7s = struct.unpack_from('<IIII', d, 0x30)
    fnto,fnts,fato,fats = struct.unpack_from('<IIII', d, 0x40)
    ov9o,ov9s,ov7o,ov7s = struct.unpack_from('<IIII', d, 0x50)
    used = struct.unpack_from('<I', d, 0x80)[0]

    print(f'=== {os.path.basename(path)} ===')
    print(f'  타이틀     : {title}')
    print(f'  게임코드   : {gcode}   메이커: {mcode}   버전: {ver}')
    print(f'  ROM 크기   : {len(d):,} bytes (사용 {used:,})')
    print(f'  ARM9       : off={a9o:#x} size={a9s:,} load={a9l:#010x}')
    print(f'  ARM7       : off={a7o:#x} size={a7s:,} load={a7l:#010x}')
    print(f'  overlay9   : off={ov9o:#x} size={ov9s:,}  ({ov9s//32} 개)')
    print(f'  FNT        : off={fnto:#x} size={fnts:,}')
    print(f'  FAT        : off={fato:#x} size={fats:,}  -> 파일 {fats//8:,}개')

    # FAT
    fat = []
    for i in range(fats//8):
        s,e = struct.unpack_from('<II', d, fato + i*8)
        fat.append((s,e))

    # FNT
    def subtable(dirid, prefix, out):
        off, firstfile, parent = struct.unpack_from('<IHH', d, fnto + dirid*8)
        p = fnto + off
        fid = firstfile
        while True:
            t = d[p]; p += 1
            if t == 0: break
            if t < 0x80:
                name = d[p:p+t].decode('shift_jis','replace'); p += t
                out.append((prefix + name, fid)); fid += 1
            else:
                ln = t & 0x7F
                name = d[p:p+ln].decode('shift_jis','replace'); p += ln
                sub = struct.unpack_from('<H', d, p)[0]; p += 2
                subtable(sub & 0xFFF, prefix + name + '/', out)
    files = []
    try:
        subtable(0, '/', files)
    except Exception as ex:
        print(f'  !! FNT 파싱 오류: {ex}')

    print(f'  FNT 경로수 : {len(files):,}')

    rows = []
    for name, fid in files:
        if fid >= len(fat): continue
        s,e = fat[fid]
        size = e - s
        head = d[s:s+4] if size >= 4 else b''
        magic = MAGICS.get(head[:4], None)
        if magic is None and size >= 4:
            hdr = struct.unpack_from('<I', d, s)[0] if size>=4 else 0
            cid = hdr & 0xFF; dsize = hdr >> 8
            if cid in COMP and 0 < dsize < 64*1024*1024:
                magic = f'{COMP[cid]} 압축'
        rows.append((name, fid, s, size, magic or '', head))
    return d, rows, (a9o,a9s,ov9o,ov9s)

def report(path):
    d, rows, arm = parse(path)
    print(f'\n  --- 포맷 분포 ---')
    c = Counter(r[4] if r[4] else '(미상)' for r in rows)
    for k,v in c.most_common():
        tot = sum(r[3] for r in rows if (r[4] or '(미상)')==k)
        print(f'    {k:<16} {v:>5}개   {tot:>12,} bytes')

    print(f'\n  --- 최상위 디렉터리 ---')
    dc = defaultdict(lambda:[0,0])
    for name,fid,s,size,mg,hd in rows:
        top = name.split('/')[1] if name.count('/')>1 else '(root)'
        dc[top][0]+=1; dc[top][1]+=size
    for k,(n,sz) in sorted(dc.items(), key=lambda x:-x[1][1]):
        print(f'    {k:<24} {n:>5}개  {sz:>12,} bytes')

    print(f'\n  --- 폰트/텍스트 후보 ---')
    kw = ('font','fnt','msg','text','txt','str','word','lang','mes','talk','name','menu','ui')
    hits = [r for r in rows if any(k in r[0].lower() for k in kw) or r[4].startswith('NFTR')]
    for name,fid,s,size,mg,hd in hits[:40]:
        print(f'    {name:<46} {size:>10,}  {mg:<14} {hd.hex()}')
    if not hits: print('    (이름 기반 후보 없음)')
    return d, rows

for p in sys.argv[1:]:
    report(p)
    print('\n')
