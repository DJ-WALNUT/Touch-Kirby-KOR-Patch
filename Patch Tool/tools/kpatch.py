"""터치커비 한글패치 작업 도구.

  python tools/kpatch.py export  [--cat A] [--force]
      targets.json 의 대상 그래픽을 work/ 에 편집용 PNG 로 추출
      (+ work/_jp/ 원본 사본, work/_mask/ 편집 가능 영역, work/_us/ 미국판 참고 이미지)
      이미 있는 PNG 는 덮어쓰지 않음 (--force 로 덮어씀)
  python tools/kpatch.py build
      work/ 의 PNG 중 원본과 달라진 것만 ROM 에 다시 넣어
      out/Touch Kirby (KR).nds 와 out/TouchKirby_KR.bps 생성
  python tools/kpatch.py selftest
      모든 대상을 강제로 재삽입해 원본과 똑같이 복원되는지 검사
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from ndslib import load_rom, decomp
import kasset, pngio, ndsrom

import config
ROOT, JP, US, WORK, OUT = config.ROOT, config.ROM_JP, config.ROM_US, config.WORK, config.OUT


def targets(cats):
    t = json.load(open(config.TARGETS, encoding='utf-8'))
    groups = {}
    for o in t:
        if (o['group_cat'] in cats or o.get('force')) and o['kind'] in ('c05', 'c06', 'bg', 'sheet', 'bmp'):
            g = groups.setdefault(o['group'], {'kind': o['kind'], 'notes': []})
            if o['note'] not in g['notes'] and o['cat'] == 'A':
                g['notes'].append(o['note'])
    return groups


def png_name(key, label):
    bank, base = key.split('/')[-2:]
    n = base[:-4] + ('__' + label if label else '')
    return bank + '/' + n + '.png'


def export_us(us, key):
    """미국판 참고 이미지 (work/_us/). 배치·번역 참고용"""
    try:
        ug = kasset.Group(us, key, kasset.group_of(us, key)[1])
        for label, lay, _ in ug.views:
            p = os.path.join(WORK, '_us', png_name(key, label))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            cv = lay.render()
            pngio.write_indexed(p, cv.w, cv.h, [max(0, i) for i in cv.idx], lay.pal)
    except Exception as ex:
        print('  (미국판 참고 이미지 실패: %s %s)' % (key, ex))


def cmd_export(args):
    cats = set(args[args.index('--cat') + 1]) if '--cat' in args else {'A'}
    force = '--force' in args
    config.check_rom()
    jp = load_rom(JP)
    us = load_rom(US) if os.path.exists(US) else None  # 미국판은 선택 (비교용 참고 이미지)
    man = {}
    for key, g in sorted(targets(cats).items()):
        grp = kasset.Group(jp, key, g['kind'])
        views = []
        for label, lay, _ in grp.views:
            rel = png_name(key, label)
            path = os.path.join(WORK, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            cv = lay.render()
            pix = [max(0, i) for i in cv.idx]
            if force or not os.path.exists(path):
                pngio.write_indexed(path, cv.w, cv.h, pix, lay.pal)
            # 원본 사본 (ktext 합성의 바탕). 항상 새로 씀
            jp_path = os.path.join(WORK, '_jp', rel)
            os.makedirs(os.path.dirname(jp_path), exist_ok=True)
            pngio.write_indexed(jp_path, cv.w, cv.h, pix, lay.pal)
            # 편집 가능 영역 마스크 (1 = 타일이 있는 곳)
            mk = os.path.join(WORK, '_mask', rel)
            os.makedirs(os.path.dirname(mk), exist_ok=True)
            pngio.write_indexed(mk, cv.w, cv.h, [0 if i < 0 else 1 for i in cv.idx],
                                [(255, 0, 255), (255, 255, 255)], transparent0=False)
            views.append(rel)
        if us is not None:
            export_us(us, key)
        man[key] = {'kind': g['kind'], 'png': views, 'files': grp.files, 'note': ' | '.join(g['notes']),
                    'bpp': grp.bpp, 'palette': grp.pal_name}
    os.makedirs(WORK, exist_ok=True)
    json.dump(man, open(os.path.join(WORK, 'manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('그룹 %d개, PNG %d장 -> %s' % (len(man), sum(len(m['png']) for m in man.values()), WORK))


def collect(jp, man):
    repl, warns, changed = {}, [], []
    for key, m in sorted(man.items()):
        grp = kasset.Group(jp, key, m['kind'])
        if len(grp.views) != len(m['png']):
            raise SystemExit('%s: manifest 가 오래됨. kpatch export 를 다시 실행하세요' % key)
        pngs = []
        for vi, rel in enumerate(m['png']):
            path = os.path.join(WORK, rel)
            png = pngio.read_png(path) if os.path.exists(path) else None
            if png is not None:
                cv = grp.views[vi][1].render()
                w, h, idx, rgba = png
                if idx is not None and (w, h) == (cv.w, cv.h) and idx == [max(0, i) for i in cv.idx]:
                    png = None  # 원본과 같음
            pngs.append(png)
        if all(p is None for p in pngs):
            continue
        try:
            for wmsg in grp.apply_all(pngs):
                warns.append('%s: %s' % (key.rsplit('/', 1)[1], wmsg))
        except ValueError as ex:
            warns.append('%s: 실패 - %s' % (key.rsplit('/', 1)[1], ex))
            continue
        out = grp.output()
        g = grp.tile_growth()
        if g and g[1] > g[0]:
            warns.append('%s: chr 타일 증가 %d -> %d 바이트 (VRAM 여유 확인 필요)' % (key.rsplit('/', 1)[1], g[0], g[1]))
        repl.update(out)
        if out:
            changed.append(key)
    return repl, warns, changed


def cmd_build(args):
    t0 = time.time()
    man = json.load(open(os.path.join(WORK, 'manifest.json'), encoding='utf-8'))
    jp = load_rom(JP)
    repl, warns, changed = collect(jp, man)
    for w in warns:
        print('  경고:', w)
    print('변경 그룹 %d개, 교체 파일 %d개' % (len(changed), len(repl)))
    src = open(JP, 'rb').read()
    rom, log = ndsrom.replace_files(src, repl)
    for path, how, a, b in log:
        print('  %-50s %s %d -> %d' % (path, how, a, b))
    os.makedirs(OUT, exist_ok=True)
    op = config.OUT_ROM
    open(op, 'wb').write(rom)
    bps = ndsrom.make_bps(src, rom, b'Touch! Kirby Korean patch')
    assert ndsrom.apply_bps(src, bps) == rom
    open(config.OUT_BPS, 'wb').write(bps)
    # 검증: 새 ROM 에서 파일을 다시 읽어 일치하는지
    chk = load_rom(op)
    for p, d in repl.items():
        assert chk[p] == d, p
    print('완료: %s (%.1fs)\n      %s (%d 바이트)' % (op, time.time() - t0, config.OUT_BPS, len(bps)))


def cmd_selftest(args):
    """원본 PNG 를 그대로 강제 재삽입 -> 압축 해제 결과가 원본과 같아야 함"""
    man = json.load(open(os.path.join(WORK, 'manifest.json'), encoding='utf-8'))
    jp = load_rom(JP)
    bad = 0
    for key, m in sorted(man.items()):
        grp = kasset.Group(jp, key, m['kind'])
        pngs = []
        for label, lay, _ in grp.views:
            cv = lay.render()
            idx = [max(0, i) for i in cv.idx]
            rgba = [(0, 0, 0, 0) if i == 0 else tuple(lay.pal[i]) + (255,) for i in idx]
            pngs.append((cv.w, cv.h, idx, rgba))
        w = grp.apply_all(pngs)
        if w:
            print('  경고', key, w)
        out = grp.output()
        # 압축 바이트는 달라도 되지만 풀었을 때 같아야 함
        for n, d in out.items():
            a, b = decomp(d)[0], decomp(jp[n])[0]
            ca, cb = kasset.kfmt.parse_container(a), kasset.kfmt.parse_container(b)
            if ca and cb:  # 05 컨테이너는 내부 타일 영역만 압축
                same = a[:ca['tile_off']] == b[:cb['tile_off']] and ca['tiles'] == cb['tiles']
            else:
                same = a == b
            if not same:
                print('  불일치:', n); bad += 1
    print('selftest: 그룹 %d개, 불일치 %d' % (len(man), bad))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    {'export': cmd_export, 'build': cmd_build, 'selftest': cmd_selftest}.get(
        cmd, lambda a: print(__doc__))(sys.argv[2:])
