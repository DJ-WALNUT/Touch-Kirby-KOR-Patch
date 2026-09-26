"""타이틀 화면 크레딧 문구 삽입 (Pillow 필요). import_art 로 타이틀을 넣은 뒤 실행한다.

  python tools/title_credit.py ["문구"] [--y 158] [--preview]

  - 동그라미 줄 아래쪽, 저작권 줄(y 170~) 위에 (기본 y 158) 갈무리7(8px)로 가운데 정렬
  - 타일의 팔레트 뱅크를 바꾸면 게임에서 문구가 깨진다 (실기 확인). 그래서 픽셀마다 그 타일이 원래 쓰는
    뱅크 안에서 목표 회색(106)에 가장 가까운 색을 쓴다 (뱅크 1 → 106, 저작권 줄 뱅크 7 → 90)
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
ROOT = config.ROOT
PNG = os.path.join(config.WORK, 'bank04bin', 'chr_title__scr_title.png')
TEXT = '2026 Korean Patch by WALNUT'
TARGET = (106, 106, 106)
FONT = ('Galmuri7.ttf', 8)    # 갈무리7
BOLD = False                  # True 면 가로 1px 굵게


def main():
    argv = sys.argv[1:]
    args = [a for i, a in enumerate(argv) if not a.startswith('--') and not (i > 0 and argv[i - 1] == '--y')]
    text = args[0] if args else TEXT
    top = int(sys.argv[sys.argv.index('--y') + 1]) if '--y' in sys.argv else 158
    im = Image.open(PNG)
    px = im.load()
    font = ImageFont.truetype(os.path.join(config.FONTS, FONT[0]), FONT[1])
    m = Image.new('1', (256, 20), 0)
    d = ImageDraw.Draw(m)
    d.fontmode = '1'
    d.text((0, 0), text, font=font, fill=1)
    if BOLD:
        mp0 = m.load()
        on = [(x, y) for y in range(m.height) for x in range(m.width) if mp0[x, y]]
        for x, y in on:
            if x + 1 < m.width:
                mp0[x + 1, y] = 1
    bb = m.getbbox()
    w = bb[2] - bb[0]
    ox = (256 - w) // 2 - bb[0]
    oy = top - bb[1]
    mp = m.load()
    pal = im.getpalette()
    from collections import Counter

    def tile_bank(X, Y):
        tx, ty = X // 8 * 8, Y // 8 * 8
        c = Counter(px[x, y] // 16 for x in range(tx, tx + 8) for y in range(ty, ty + 8) if px[x, y])
        return c.most_common(1)[0][0] if c else 0

    def color_in(bk):
        return min(range(bk * 16 + 1, bk * 16 + 16),
                   key=lambda i: sum((pal[i * 3 + k] - TARGET[k]) ** 2 for k in range(3)))
    n = 0
    for y in range(m.height):
        for x in range(m.width):
            if mp[x, y]:
                X, Y = ox + x, oy + y
                if 0 <= X < 256 and 0 <= Y < 192:
                    px[X, Y] = color_in(tile_bank(X, Y))
                    n += 1
    im.save(PNG, transparency=0)
    print('크레딧 삽입: 「%s」 x %d~%d, y %d~%d (%d픽셀)' % (text, ox + bb[0], ox + bb[2] - 1, top, oy + bb[3] - 1, n))
    if '--preview' in sys.argv:
        a = im.convert('RGBA')
        bg = Image.new('RGBA', a.size, (255, 255, 255, 255))
        z = Image.alpha_composite(bg, a).crop((0, 140, 256, 192))
        os.makedirs(config.PREVIEW, exist_ok=True)
        z.resize((z.width * 4, z.height * 4), Image.NEAREST).save(os.path.join(config.PREVIEW, 'title_credit.png'))


if __name__ == '__main__':
    main()
