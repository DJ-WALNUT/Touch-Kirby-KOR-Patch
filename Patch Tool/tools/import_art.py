"""외부 그림(고해상도 PNG 등)을 게임용 인덱스 PNG 로 변환해 work/ 에 넣는다 (Pillow 필요).

  python tools/import_art.py <그림.png> <work 기준 경로> [--screen-h 192] [--keep-bank]
  예) python tools/import_art.py assets/title/title_design.png bank04bin/chr_title__scr_title.png

  - 그림 크기가 게임 PNG 의 정수배가 아니어도 됨: 게임 픽셀 칸의 중심을 샘플링해 줄인다
  - 8x8 타일마다 그 칸의 색을 가장 정확히 표현하는 16색 팔레트 뱅크를 골라 인덱스로 바꾼다
    (원래 뱅크로 정확하면 원래 뱅크 유지, 팔레트에 없는 색은 가장 가까운 색)
  - 팔레트에 없는 회색(벡터 그림 안티앨리어싱)은 가까운 팔레트 회색 또는 흑/백으로 먼저 정리
  - --screen-h: 이 높이 아래(화면 밖) 행은 원본 그대로 둔다 (불필요한 타일 증가 방지)
  - --keep-bank: 타일의 팔레트 뱅크를 절대 바꾸지 않는다 (뱅크 변경은 게임에서 깨질 수 있음, 타이틀은 이 옵션 권장)
  - 결과는 kpatch build 가 그대로 읽는다. 적용 뒤 `ktext.py check` 로 타일 용량을 확인할 것
"""
import os, sys
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
ROOT = config.ROOT


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    src_path, rel = args[0], args[1]
    screen_h = int(sys.argv[sys.argv.index('--screen-h') + 1]) if '--screen-h' in sys.argv else None
    orig = Image.open(os.path.join(config.WORK, '_jp', rel))
    W, H = orig.size
    pal = orig.getpalette()
    P = [tuple(pal[i * 3:i * 3 + 3]) for i in range(len(pal) // 3)]
    op = orig.load()
    src = Image.open(src_path).convert('RGBA')
    sp = src.load()
    sx = src.width / W
    sy = sx  # 가로 배율 기준 (세로가 잘린 그림도 허용)
    palset = set(P[1:])
    grays = sorted({c[0] for c in P[1:] if c[0] == c[1] == c[2]})

    def snap(c):
        """팔레트에 없는 회색(벡터 그림의 안티앨리어싱)은 가까운 팔레트 회색(±12 이내) 또는 흑/백으로 정리"""
        if c in palset or not (c[0] == c[1] == c[2]):
            return c
        v = c[0]
        near = min(grays, key=lambda gv: abs(gv - v)) if grays else None
        if near is not None and abs(near - v) <= 12:
            return (near,) * 3
        return (0, 0, 0) if v < 128 else (255, 255, 255)

    tgt = [[None] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if screen_h is not None and y >= screen_h:
                continue
            X = min(src.width - 1, int((x + 0.5) * sx))
            Y = int((y + 0.5) * sy)
            if Y >= src.height:
                continue
            r, g, b, a = sp[X, Y]
            tgt[y][x] = None if a < 128 else snap((r, g, b))
    out = orig.copy()
    o = out.load()
    nbank = len(P) // 16
    changed_bank = 0
    for ty in range(0, H, 8):
        for tx in range(0, W, 8):
            cells = [(x, y) for y in range(ty, min(H, ty + 8)) for x in range(tx, min(W, tx + 8))]
            if all(tgt[y][x] is None and (screen_h is not None and y >= screen_h) for x, y in cells):
                continue  # 화면 밖: 원본 유지
            want = [tgt[y][x] for x, y in cells if tgt[y][x] is not None]
            ob = max((op[x, y] // 16 for x, y in cells if op[x, y]), key=lambda b: 0, default=0)
            # 원래 칸에서 가장 많이 쓰인 뱅크
            from collections import Counter
            cnt = Counter(op[x, y] // 16 for x, y in cells if op[x, y])
            if cnt:
                ob = cnt.most_common(1)[0][0]

            def near(c, bk):
                """뱅크 안에서 가장 가까운 색. 회색은 뱅크의 무채색 중에서 고른다 (회색이 보라 등으로 바뀌는 것 방지)"""
                best, bd = bk * 16 + 1, 1 << 30
                js = range(1, 16)
                if max(c) - min(c) <= 24:  # 회색에 가까운 색(채도 낮음)은 무채색 후보에서 고른다
                    ach = [j for j in js if P[bk * 16 + j][0] == P[bk * 16 + j][1] == P[bk * 16 + j][2]]
                    if ach:
                        js = ach
                for j in js:
                    q = P[bk * 16 + j]
                    d = (c[0] - q[0]) ** 2 + (c[1] - q[1]) ** 2 + (c[2] - q[2]) ** 2
                    if d < bd:
                        best, bd = bk * 16 + j, d
                return best, bd

            def err(bk):
                # 회색(대부분 안티앨리어싱)은 가중치를 낮춰, 무지개 등 유채색을 정확히 담는 뱅크를 우선
                return sum(near(c, bk)[1] * (0.05 if max(c) - min(c) <= 24 else 1) for c in want)
            bank = ob
            if want and err(ob) > 0 and '--keep-bank' not in sys.argv:
                cand = min(range(nbank), key=lambda bk: (err(bk), bk != ob))
                if err(cand) < err(ob):
                    bank = cand
                    changed_bank += 1
            # 회색 단계가 거의 없는 칸(무지개 막대 줄 등)은 안티앨리어싱 회색을 흑/백으로 깔끔하게 정리
            # (어설픈 근사로 좌우가 비대칭이 되는 것 방지)
            ngray = len({P[bank * 16 + j] for j in range(1, 16)
                         if P[bank * 16 + j][0] == P[bank * 16 + j][1] == P[bank * 16 + j][2]} - {(0, 0, 0), (255, 255, 255)})
            for x, y in cells:
                c = tgt[y][x]
                if c is None:
                    if screen_h is None or y < screen_h:
                        o[x, y] = 0
                    continue
                if ngray < 4 and max(c) - min(c) <= 24 and c not in ((0, 0, 0), (255, 255, 255)) and not (
                        c in [P[bank * 16 + j] for j in range(1, 16)] and op[x, y] and P[op[x, y]] == c):
                    c = (0, 0, 0) if sum(c) / 3 < 128 else (255, 255, 255)
                o[x, y] = near(c, bank)[0]
    dst = os.path.join(config.WORK, rel)
    out.save(dst, transparency=0)
    print('저장:', dst, ' 배율 %.4f, 뱅크를 바꾼 타일 %d개' % (sx, changed_bank))


if __name__ == '__main__':
    main()
