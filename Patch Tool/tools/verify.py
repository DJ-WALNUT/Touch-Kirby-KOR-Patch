"""빌드된 ROM 에서 그래픽을 다시 뽑아 work/ PNG 와 픽셀 단위로 비교.

  python tools/verify.py            out/Touch Kirby (KR).nds 검사
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from ndslib import load_rom
import kasset, pngio, kfmt

import config
ROOT, WORK = config.ROOT, config.WORK


def main():
    kr = load_rom(config.OUT_ROM)
    jp = load_rom(config.ROM_JP)
    man = json.load(open(os.path.join(WORK, 'manifest.json'), encoding='utf-8'))
    bad = 0
    total = 0
    for key, m in sorted(man.items()):
        g = kasset.Group(kr, key, m['kind'])
        if m['kind'] == 'c05':
            # 타일 번호 단위는 게임이 고정으로 쓰는 값 = 원본에서 판별한 값 (타일이 늘면 자동 판별이 바뀔 수 있음)
            g.obj['unit'] = kfmt.parse_container(kasset.dec(jp, key)[0])['unit']
            g.views[0] = ('', kfmt.layout_container(g.obj), None)
        for vi, rel in enumerate(m['png']):
            w, h, idx, rgba = pngio.read_png(os.path.join(WORK, rel))
            mask = pngio.read_png(os.path.join(WORK, '_mask', rel))[2]
            lay = g.views[vi][1]
            cv = lay.render()
            pal = lay.pal

            def differs(o):
                a, b = max(0, cv.idx[o]), (idx[o] if idx else 0)
                if a == b:
                    return False
                if a == 0 or b == 0:
                    return True
                # 4bpp 에서 뱅크만 다르고 같은 색 번호 + 같은 색이면 동일 취급 (팔레트 없는 그래픽)
                return not (a % 16 == b % 16 and pal[a] == pal[b])
            diff = sum(1 for o in range(w * h) if mask[o] and differs(o))
            total += 1
            if diff:
                bad += 1
                print('  불일치 %-60s %d px' % (rel, diff))
    print('검사 %d장, 불일치 %d장' % (total, bad))


if __name__ == '__main__':
    main()
