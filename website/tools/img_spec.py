"""글자 이미지 한글화 사양 (tools/render_img.py 가 사용).
각 항목: group(비교 이미지 묶음), file 또는 files=[(경로, x, y)…], ops=[캔버스 → 캔버스 함수…]
좌표·색은 tools/probe.py, tools/bbox.py 로 원본에서 잰 값."""
from render_img import erase, fill, hstretch, copy, text, paste, recolor

E = lambda *a, **k: (lambda c: erase(c, *a, **k))
T = lambda *a, **k: (lambda c: text(c, *a, **k))
F = lambda *a, **k: (lambda c: fill(c, *a, **k))
H = lambda *a, **k: (lambda c: hstretch(c, *a, **k))
C = lambda *a, **k: (lambda c: copy(c, *a, **k))
P = lambda *a, **k: (lambda c: paste(c, *a, **k))
R = lambda *a, **k: (lambda c: recolor(c, *a, **k))

SPEC = []


def add(group, file, *ops, files=None):
    SPEC.append(dict(group=group, ops=list(ops), **({'files': files} if files else {'file': file})))


# ---------------------------------------------------------------- menu/ 메뉴 버튼 (b = 기본, bo = 마우스오버)
# 흰 글자 + 분홍 외곽선 3px (기본 ff99cc / 오버 ff66cc). 글자 왼쪽 x=123, 가운데 y=45
MENU = {1: '「터치! 커비」란?', 2: '기본 조작', 3: '트레이닝 무비', 4: '메인 게임', 5: '보스 게임',
        6: '레인보우 트라이얼', 7: '카피 능력', 8: '장치', 9: '적 캐릭터', 10: '공략본 정보'}
for n, s in MENU.items():
    for pre, pink in (('b', 'ff99cc'), ('bo', 'ff66cc')):
        if (pre, n) == ('b', 10):
            continue  # b10.gif 는 원본에 없음
        add('menu', f'menu/{pre}{n:02d}.gif',
            E((118, 24, 440, 68), colors=['ffffff', pink, 'ffcee7', 'ffb3da', 'ffe4f1', 'ffd6f1'], tol=40, grow=1),
            T(s, (123, 45), 30, strokes=[(3, pink)], fill='#ffffff', maxw=305))


# ---------------------------------------------------------------- */title.gif 페이지 제목
# 흰 글자 + 오른쪽 아래 반투명 그림자 (배경을 어둡게). 글자 왼쪽 x≈30, 높이 12~41
TITLE = {'about': ('「터치! 커비」란?', 412), 'sousa': ('기본 조작', 188), 'training': ('트레이닝 무비', 335),
         'maingame': ('메인 게임', 240), 'copy': ('카피 능력', 185), 'boss': ('보스 게임', 185),
         'teki': ('적 캐릭터', 155), 'rainbow': ('레인보우 트라이얼', 338), 'karakuri': ('장치', 173),
         'menu': ('웹사이트 메뉴', 390)}
for page, (s, right) in TITLE.items():
    add('title', f'{page}/title.gif',
        E((22, 6, right + 6, 50), colors=['ffffff', 'f4f4f4', 'e8e8e8'], tol=60, grow=3),
        T(s, (30, 27), 33, strokes=[], shadow=(2, 2, (10, 20, 50, 120)), fill='#ffffff', maxw=440))

# ---------------------------------------------------------------- */sub_tit*.gif 부제 (막대 위 오른쪽 정렬)
# 적갈색 글자 + 흰 외곽선 + 적갈색 외곽선. 막대(위에서부터): 테두리 2행, 채움 6행(가로 그라데이션), 테두리 2행, 그림자 1행.
# 막대 높이는 이미지마다 1행씩 달라서 x=105 열의 그림자(9daab1) 행으로 찾음.
# 원래 글자는 채움 3행째까지 걸쳐 있음 → 그 위는 배경색, 테두리는 적갈색, 채움은 각 열의 채움 맨 아랫행 색으로 복원


def subtit_bar(c):
    import numpy as np
    from PIL import Image
    a = np.asarray(c).copy()
    x0, x1 = 110, 547
    sh = next(y for y in range(30, a.shape[0]) if abs(a[y, 105].astype(int) - (0x9d, 0xaa, 0xb1)).sum() < 20)
    top = sh - 10
    a[0:top, x0:x1] = (0xe1, 0xf4, 0xfd)
    a[top:top + 2, x0:x1] = (0x80, 0x29, 0x3e)
    a[top + 2:top + 8, x0:x1] = a[top + 7:top + 8, x0:x1]
    return Image.fromarray(a)


SUB = {'about/sub_tit': ('그린 무지개가 길이 된다!', 4), 'boss/sub_tit': ('보스 게임을 이기고 다음 레벨로 나아가라!', 1),
       'karakuri/sub_tit': ('장치를 지배하는 자가 모험을 지배한다!', 1), 'maingame/sub_tit01': ('스토리', 3),
       'maingame/sub_tit02': ('모험을 달아오르게 하는 다채로운 스테이지!', 1),
       'rainbow/sub_tit': ('레인보우 트라이얼로 끝까지 파고들자!', 1), 'sousa/sub_tit': ('터치! 커비의 조작 방법', 3),
       'teki/sub_tit': ('새로운 적 캐릭터도 등장!', 3)}
for f, (s, sp) in SUB.items():
    add('subtit', f'{f}.gif',
        subtit_bar,
        T(s, (544, 42), 17, anchor='r', valign='b', strokes=[(4, '80293e'), (2, '#ffffff')], fill='80293e',
          spacing=sp, maxw=425))


# ---------------------------------------------------------------- about·sousa·boss mid 소제목 (아이콘 + 단색 알약)
# 흰 글자 + 알약보다 진한 같은 계열 외곽선 2px. 글자 왼쪽 x≈72, 가운데 y≈48
PILL = {'about/mid01': ('장르는 펜 액션!', '4699de', 'add8fd'),
        'about/mid02': ('자유자재로 조작하는 커비의 직감 펜 액션!', 'f37878', 'ffc5c5'),
        'about/mid03': ('커비도 적도 장치도 터치로 조작!', 'ffa200', 'f3e56c'),
        'about/mid04': ('익숙한 카피 능력도 11종류!', '61b15a', 'a7de89'),
        'sousa/mid02': ('터치 대시', 'fa955e', 'fdd3a6'), 'sousa/mid03': ('적을 터치!', '6793ce', 'a1c9fe'),
        'sousa/mid04': ('장치를 터치!', '3faa83', '9cdbc4'),
        'boss/mid01': ('페인트 패닉', '7e4695', 'd8c0e2'), 'boss/mid02': ('트로코 체이스', '538f2f', 'c1d8a8'),
        'boss/mid03': ('블록 어택', 'aa792a', 'ddc6a2')}
# 알약이 단색이라 "알약색과 다른 픽셀"을 지움 (획이 촘촘한 한자 안쪽의 연한 색까지 잡힘)
for f, (s, stroke, bg) in PILL.items():
    add('pill', f'{f}.gif',
        E((68, 34, 528, 62), bg=[bg], tol=24, grow=1),
        T(s, (73, 48), 22, strokes=[(2, stroke)], fill='#ffffff', maxw=445))


# ---------------------------------------------------------------- copy/mid*.gif 카피 능력 이름 (영문은 유지)
# 적갈색 글자 + 흰 외곽선 + 적갈색 외곽선. 원래 글자의 bbox (x0, y0, x1, y1) 를 기준으로 교체
COPY = {1: ('빔', (90, 29, 156, 52)), 2: ('버닝', (90, 22, 200, 46)), 3: ('휠', (90, 17, 177, 40)),
        4: ('벌룬', (90, 22, 177, 46)), 5: ('스파크', (89, 17, 177, 41)), 6: ('미사일', (90, 17, 177, 40)),
        7: ('스톤', (89, 17, 177, 40)), 8: ('크래시', (89, 17, 198, 40)), 9: ('프리즈', (90, 20, 178, 44)),
        10: ('토네이도', (90, 16, 198, 40)), 11: ('니들', (90, 16, 177, 40))}
for n, (s, (x0, y0, x1, y1)) in COPY.items():
    add('copy', f'copy/mid{n:02d}.gif',
        E((x0 - 2, y0 - 2, x1 + 3, y1 + 3), colors=['803434', 'ffffff', 'a26b6b', 'ddc9c9', 'bd9595', 'c4a0a0', '9b5860'],
          tol=50, grow=1),
        T(s, (x0 + 1, y1 + 1), 21, valign='b', strokes=[(4, '803434'), (2, '#ffffff')], fill='803434', maxw=200))


# ---------------------------------------------------------------- sousa/mid01 「虹のライン」 (배경 0~20행 + 파란 막대 21~40행에 걸친 글자)
add('misc', 'sousa/mid01.gif',
    F((38, 0, 200, 21), 'e1f4fd'), F((38, 21, 200, 41), '3366cc'),
    T('무지개의 라인', (41, 22), 23, strokes=[(2, '3366cc')], fill='#ffffff'))

# ---------------------------------------------------------------- teki/name*.gif 적 이름표 (단색 알약 + 흰 글자)
TEKI = {1: ('블레도', 'cc3333', (32, 15, 100, 31)), 2: ('덴돈', '3366cc', (26, 20, 94, 36)),
        3: ('푸쿠라', 'ff99ff', (22, 18, 73, 34)), 4: ('창 웨이들 디', '339933', (27, 21, 147, 37))}
for n, (s, bg, (x0, y0, x1, y1)) in TEKI.items():
    add('misc', f'teki/name{n:02d}.gif',
        E((x0 - 2, y0 - 2, x1 + 2, y1 + 2), bg=[bg], tol=30, grow=1),
        T(s, ((x0 + x1) / 2, (y0 + y1) / 2), 21, anchor='c', fill='#ffffff', maxw=x1 - x0 + 20))

# teki/chara05.gif 「このほかにもユニークな敵キャラが続々と登場するよ！」 노란 글자 + 주황 외곽선 + 회색 그림자
add('misc', 'teki/chara05.gif',
    E((0, 0, 501, 40), bg=['e1f4fd'], tol=20, grow=1, keep=[(140, 34, 182, 40)]),
    T('이 밖에도 개성 넘치는 적 캐릭터가 계속 등장해요!', (250, 18), 22, anchor='c',
      strokes=[(3, 'cc6600')], shadow=(2, 2, '9daab0'), fill='ffff66', maxw=470))

# ---------------------------------------------------------------- rainbow/mid*.gif (기울임 글자, 영문 Time Trial 등은 유지)
# 큰 글자: 흰 글자 + 진한 외곽선. 오른쪽 위 작은 글자: 알약색 글자 + 흰 외곽선 (알약 위 가장자리에 걸침)
RB = {1: ('타임 트라이얼', '최고 기록으로 골을 노려라!', '99cc00', '336633', 42, 25, 39, 27),
      2: ('라인 트라이얼', '무지개 잉크를 철저하게 절약!', 'ca479e', '830559', 39, 19, 34, 24)}
# 작은 글자의 채움색 = 알약색이라 인페인팅하면 알약 윗변이 번짐 → 윗변(edge) 위는 배경색, 아래는 알약색으로 칠함
# (bottom 아래는 영문 Time Trial / Line Trial)
for n, (big, small, pill, dark, big_y, edge, bottom, small_y) in RB.items():
    add('misc', f'rainbow/mid{n:02d}.gif',
        E((58, big_y - 14, 222, big_y + 14), bg=[pill], tol=30, grow=1),
        F((306, 0, 529, edge), 'e1f4fd'), F((306, edge, 529, bottom), pill),
        T(big, (63, big_y), 24, strokes=[(2, dark)], fill='#ffffff', italic=0.22),
        T(small, (524, small_y), 16, anchor='r', strokes=[(2, '#ffffff')], fill=pill, italic=0.22, maxw=215))


# ---------------------------------------------------------------- 톱 페이지 버튼 (b = 기본, bo = 마우스오버: 알약 안쪽 색만 다름)
# 장미색 글자 + 연분홍 외곽선. 알약 끝이 둥글어 테두리가 상자 안에 들어오므로 글자색으로 마스크
ROSE = ['b33955', 'c87084', 'dca3b0', 'd899a7', 'c4657a', 'e0aeb9', 'bf586f', 'b94761', 'd18798', 'f3d7db', 'e5bbc4',
        'ebcad1', 'ba4c66', 'c36278', 'd796a5', 'd08495', 'c97185', 'dca3af', 'd897a5', 'c56479', 'ebcad2', 'daa4af', 'c77083']
for pre, inner in (('b', 'ffffff'), ('bo', 'fee6e6')):
    add('btn', f'{pre}_menu.gif',
        R((12, 16, 166, 46), ['ff6666', 'f57878', 'ff9f9f', 'ffc7c7', 'ffefef', 'feeeee', 'a8dee0', 'b7cacc', 'a6d9db'], inner, tol=30),
        T('웹사이트 메뉴', (88, 31), 19, anchor='c', strokes=[(2, 'ebcad1')], fill='b33955', maxw=140))
for pre, inner in (('b', 'ffffff'), ('bo', 'e8ffe8')):
    add('btn', f'{pre}_soft.gif',
        R((10, 15, 97, 46), ['66cc66', '69cd6c', '78d27a', '78d08e', '7fd58a', '74cf8b', 'aae3aa', 'baedba', 'cceecc', 'a8dee0',
                              'b7cacc', 'a6d9db'], inner, tol=30),
        T('상품 정보', (53, 31), 19, anchor='c', strokes=[(2, 'ebcad1')], fill='b33955', maxw=74))

# ---------------------------------------------------------------- soft/ 상품 정보 팝업
add('btn', 'soft/title.gif',
    E((10, 13, 108, 43), bg=['ffffff'], tol=20, grow=1),
    T('상품 정보', (59, 28), 22, anchor='c', strokes=[(2, '70cf70')], fill='#ffffff', spacing=2, maxw=94))
# 발매 정보 4줄: 자홍 글자 + 흰 외곽선 + 분홍 외곽선
INFO_COLS = ['ee146a', 'f02e79', 'f24588', 'f36299', 'f686b1', 'f9b2cd', 'fbc9dc', 'fddbe8', 'feeff3']
add('btn', 'soft/info.gif',
    E((0, 2, 184, 86), colors=INFO_COLS, tol=30, grow=1),
    *[T(s, (4, y), 15, strokes=[(3, 'f686b1'), (1, '#ffffff')], fill='ee146a', maxw=250)
      for s, y in (('발매일: 2005년 3월 24일', 13), ('희망 소비자 가격: 4,571엔(세금 별도)', 33),
                   ('장르: 펜 액션', 53), ('플레이 인원: 1명', 73))])
add('btn', 'soft/pen.gif',
    E((10, 2, 255, 22), bg=['3399ff'], tol=30, grow=1),
    T('터치펜 [커비 핑크]가 들어 있어요!', (132, 12), 15, anchor='c', fill='#ffffff', maxw=235))

# ---------------------------------------------------------------- about/ 무비 버튼
MOV1 = ['ffff00', 'cc0000', 'da4300', 'e47600', 'db350c', 'e76f02', 'ffffff']
for pre in ('b', 'bo'):
    add('btn', f'about/{pre}_mov01.gif',
        E((18, 14, 150, 58), colors=MOV1, tol=50, grow=1),
        E((174, 18, 226, 46), colors=['ffffff'], tol=60, grow=1),
        T('무비 1편', (24, 26), 22, strokes=[(3, '#ffffff'), (2, 'cc0000')], fill='ffff00'),
        T('(약 10.6MB)', (25, 48), 14, strokes=[(3, '#ffffff'), (2, 'cc0000')], fill='ffff00'),
        T('추천', (200, 32), 15, anchor='c', fill='#ffffff', rotate=20))
    add('btn', f'about/{pre}_mov02.gif',
        E((18, 14, 146, 58), bg=['ffff99'], tol=20, grow=1),
        T('무비 2편', (22, 27), 22, strokes=[(2, '006600')], fill='99cc66'),
        T('(약 7.7MB)', (22, 48), 14, strokes=[(2, '006600')], fill='99cc66'))

# ---------------------------------------------------------------- copy/ 카피 능력 무비 버튼 (Click! 은 유지)
for pre in ('b', 'bo'):
    add('btn', f'copy/{pre}_copymov.gif',
        E((154, 6, 330, 35), colors=['ff6600', 'fe9342', 'ffab74', 'fe7414', 'ffb551', 'fd892b', 'fed4b6', 'ffffff',
                                      'fb9346', 'ffb17e'], tol=30, grow=1),
        T('카피 능력 무비', (325, 21), 22, anchor='r', strokes=[(2, 'ff6600')], fill='#ffffff', maxw=170))

# ---------------------------------------------------------------- 무비 팝업 제목 (단색 배경 전체가 글자)
for f, s, bg, stroke in (('about/movie/title01', '무비 1', 'd2eced', 'ff66cc'), ('about/movie/title02', '무비 2', 'd2eced', 'ff66cc'),
                          ('copy/movie/title', '카피 능력 무비', 'ffe6ff', '66c6ff')):
    add('btn', f'{f}.gif', F((0, 0, 200, 40), bg),
        T(s, (62 if 'about' in f else 75, 12), 18, anchor='c', strokes=[(2, stroke)], fill='#ffffff', maxw=140))


# ---------------------------------------------------------------- training/ 트레이닝 무비 버튼 (필름 무늬 배경)
# 연분홍 흰 글자 + 버튼마다 다른 색 외곽선 2px. 배경(필름)은 회색·흰색·옅은 색이라 채도 높은 픽셀(글자 외곽선)을 마스크
def tints(c, steps=(0, .15, .3, .45, .6, .7)):
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    return ['%02x%02x%02x' % tuple(round(v + (255 - v) * t) for v in (r, g, b)) for t in steps]


TRAIN = {1: ('터치 대시를 익히자! (약 4MB)', 'ff5151', 368), 2: ('터치로 앞으로 나아가자! (약 2.7MB)', '68b4ff', 317),
         3: ('커비의 방향을 바꾸자! (약 3MB)', 'ffb062', 350), 4: ('무지개의 라인에 올라타자! (약 2.4MB)', '5fd085', 317),
         5: ('카피 능력을 쓰자! (약 4.6MB)', 'd182d1', 317), 6: ('무지개의 라인으로 커비를 지키자! (약 6MB)', 'cba535', 386)}
for n, (s, stroke, right) in TRAIN.items():
    for pre in ('b', 'bo'):
        add('train', f'training/{pre}{n:02d}.gif',
            E((32, 12, right + 3, 44), sat=0.2, grow=2),
            T(s, (37, 28), 21, strokes=[(2, stroke)], fill='fff4f6', maxw=352))


# ---------------------------------------------------------------- boss/pic*.gif 스크린샷 아래 캡션 (흰 글자 + 검은 외곽선 + 색 외곽선)
BOSS = {1: (['페인트 롤러의 출제에', '이어 그림을 그리자!'], '663299', 'e9dbed'),
        2: (['윌리 그림 완성!', '1문제 클리어!'], '663399', 'e9dbed'),
        3: (['여기서도 적과 블록을', '터치할 수 있어!'], '538f2e', 'dbe6cf'),
        4: (['디디디 대왕을 따돌려라!'], '538f2e', 'dbe6cf'),
        5: (['커비는 라켓으로', '힘차게 튕겨 나가!'], '9d632c', 'ece3d5'),
        6: (['꼭대기에서 기다리는 건', '크랙코다!'], '9a642f', 'ece3d5')}
for n, (lines, outer, bg) in BOSS.items():
    ys = [253] if len(lines) == 1 else [254, 269]
    add('boss', f'boss/pic{n:02d}.gif',
        E((0, 243 if len(lines) == 2 else 243, 169, 279 if len(lines) == 2 else 264),
          colors=['ffffff', '000000', outer, '888888', 'bebcbe', '3b3c37', '474947'], tol=40, grow=1),
        *[T(s, (84, y), 16, anchor='c', strokes=[(3, outer), (1, '000000')], fill='#ffffff', maxw=164)
          for s, y in zip(lines, ys)])


# ---------------------------------------------------------------- maingame/mid*.gif 스테이지 라벨 (가타카나만 교체. LEVEL/STAGE·영문 이름은 유지)
# 분홍 글자 + 흰 외곽선, 가운데 x≈127, 30~49행 (50행부터 영문)
STAGE = {1: ('래빈 로드', 73, 182), 2: ('고스트 그라운드', 48, 207), 3: ('매그 마운트', 73, 181), 4: ('리프트 루인', 73, 181),
         5: ('콘트라스트 케이브', 48, 207), 6: ('머신 맨션', 57, 199), 7: ('콜드 코스', 65, 190), 8: ('사일런트 시베드', 39, 215)}
for n, (s, x0, x1) in STAGE.items():
    add('stage', f'maingame/mid{n:02d}.gif',
        E((x0 - 2, 28, x1 + 2, 50), colors=['ff5fb9', 'ffffff', 'f7b5db', 'fed7ed', 'fe8bcc', 'e379b9', 'd6489f', 'c40373'],
          tol=40, grow=1),
        T(s, (127, 39), 19, anchor='c', strokes=[(2, '#ffffff')], fill='ff5fb9', maxw=200))


# ---------------------------------------------------------------- maingame/story*.jpg 스토리 (남색 글자 + 흰 외곽선, 강조 단어는 분홍)
# 옅은 무늬 배경 → 어둡거나 채도 높은 픽셀을 지우고 2px 확장(흰 외곽선까지). 커비 아이콘·마녀 그림은 보호
NAVY, HI = {'fill': '000055'}, {'fill': 'ff44cc'}
SW = [(2, '#ffffff')]


def story_line(runs, x, y, maxw):
    return T([(s, HI if hi else NAVY) for s, hi in runs], (x, y), 17, strokes=SW, maxw=maxw)


add('story', 'maingame/story01.jpg',
    E((68, 2, 532, 34), sat=0.3, dark=450, grow=2),
    story_line([('여기는 평화로운 푸푸푸 랜드. 커비는 오늘도 태평하게 산책 중.', 0)], 74, 18, 450))
add('story', 'maingame/story02.jpg',
    E((26, 16, 400, 148), sat=0.3, dark=450, grow=2, keep=[(320, 42, 363, 80), (220, 88, 263, 129)]),
    E((395, 124, 440, 148), sat=0.3, dark=450, grow=2),
    story_line([('그런데 갑자기 눈앞에 ', 0), ('수상한 마녀', 1), ('가 나타나', 0)], 32, 31, 360),
    story_line([('주위를 온통 그림으로 칠해 버려요.', 0)], 32, 60, 285),
    story_line([('커비를 눈치챈 마녀는', 0)], 32, 107, 185),
    story_line([('하늘에 ', 0), ('이상한 액자', 1), ('를 그리고 그 안으로 도망쳤어요.', 0)], 32, 135, 360))
add('story', 'maingame/story03.jpg',
    E((26, 12, 532, 64), sat=0.3, dark=450, grow=2),
    story_line([('커비가 뒤쫓아 들어간 액자 속에는 그림의 세계가 펼쳐져 있었어요.', 0)], 32, 24, 490),
    story_line([('마녀는 맞서는 커비에게 ', 0), ('볼의 마법', 1), ('을 걸고 날아가 버려요.', 0)], 32, 51, 490))
add('story', 'maingame/story04.jpg',
    E((26, 8, 480, 62), sat=0.3, dark=450, grow=3, keep=[(382, 34, 424, 64)]),
    story_line([('마녀가 떨어뜨리고 간 ', 0), ('이상한 붓', 1), ('에 커비가 닿자,', 0)], 32, 23, 440),
    story_line([('붓은 무지개색 빛을 내며 당신의 손 안으로……', 0)], 32, 49, 345))


# ---------------------------------------------------------------- karakuri/ 장치 이름 (mid 아래에 chara 가 붙어 있고 글자가 두 조각에 걸침)
# 색 글자 + 흰 외곽선 + 회색 그림자. 글자 왼쪽 x=72, 가운데 y≈25.
# mid 높이 37 인 것은 chara 폭이 72뿐이라 mid 안에서만 작업
KARA = {1: ('폭탄 블록', '1aaed3'), 2: ('말뚝', '642910'), 3: ('슈퍼 대포', 'e03333'), 4: ('블레이드 바', '23a738'),
        5: ('레이저', 'ffc600'), 6: ('비눗방울', 'b949bd'), 7: ('노이즈 에리어', '21b9c6'), 8: ('팬', 'e9459a'),
        9: ('랜턴', 'ff9c00'), 10: ('범퍼 패널', '293678'), 11: ('능력 블록', '24936a'), 12: ('컬러 셔터', '585457'),
        13: ('크레인', '0188e7')}
KARA_TALL = {8, 9, 11, 12, 13}   # mid 539x37 + chara 72x35
# 배경(위 띠 + 아래 흰 패널)은 가로로 균일 → 글자 구간을 글자 없는 x=285 열로 복원 (인페인팅보다 깨끗함)
for n, (s, col) in KARA.items():
    mh = 37 if n in KARA_TALL else 31
    add('kara', None,
        H((69, 0, 240, mh if n in KARA_TALL else 72), 285),
        T(s, (73, 25), 20, strokes=[(2, '#ffffff')], shadow=(2, 2, (110, 120, 100, 170)), fill=col, maxw=210),
        files=[(f'karakuri/mid{n:02d}.gif', 0, 0), (f'karakuri/chara{n:02d}.gif', 0, mh)])


# ---------------------------------------------------------------- 로고 → 한글 로고 (Patch Tool/assets/logo/logo.png)
# 원본 로고처럼 검은 판 바깥에 흰 테두리를 두름 (한글 로고 PNG 에는 없음)
LOGO = '../Patch Tool/assets/logo/logo.png'


def korean_logo(box, border):
    def op(c):
        import os
        from PIL import Image, ImageFilter
        from render_img import ROOT
        im = Image.open(os.path.join(ROOT, LOGO)).convert('RGBA')
        x0, y0, x1, y1 = box
        r = min((x1 - x0 - 2 * border) / im.width, (y1 - y0 - 2 * border) / im.height)
        im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
        L = Image.new('RGBA', (im.width + 2 * border, im.height + 2 * border), (0, 0, 0, 0))
        L.alpha_composite(im, (border, border))
        a = L.getchannel('A').filter(ImageFilter.MaxFilter(border * 2 + 1))
        out = Image.new('RGBA', L.size, (255, 255, 255, 0)); out.putalpha(a)
        out.alpha_composite(L)
        base = c.convert('RGBA')
        base.alpha_composite(out, (x0 + (x1 - x0 - out.width) // 2, y0 + (y1 - y0 - out.height) // 2))
        return base.convert('RGB')
    return op


# 톱 페이지: 배경의 흰 호(e9f7f7 등)는 남기고 로고만 지운 뒤 붙임
add('logo', 'top03.gif',
    E((0, 10, 282, 95), bg=['a8dee0', 'e9f7f7', 'bde6e8', 'e5deed', 'dfdfdf'], tol=30, grow=1),
    korean_logo((0, 6, 282, 95), 3))
add('logo', 'common/logo.gif', F((0, 0, 117, 34), 'e1f4fd'), korean_logo((0, 0, 117, 34), 2))
