"""jp/ (원본 미러) → ko/ (한글판) 빌드.
  - HTML: Shift_JIS → UTF-8, translation/strings.json 으로 일본어 구간 치환, <html lang="ko">
  - 본문 글꼴: Noto Sans KR (Google Fonts). 이미지 글자는 img_ko/ 에 주아체로 다시 그린 것을 덮어씀
  - Flash: Ruffle 로 재생 (감지 스크립트는 항상 통과시킴)
  - 사이트 밖을 가리키는 상대 링크는 nintendo.co.jp 절대 URL 로
  python tools/build.py
"""
import glob, json, os, re, shutil, sys, urllib.parse
sys.path.insert(0, os.path.dirname(__file__))
from extract import segments

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JP, KO, IMG = (os.path.join(ROOT, d) for d in ('jp', 'ko', 'img_ko'))
BASE = 'https://www.nintendo.co.jp/ds/atkj/'

HEAD = '''<META CHARSET="UTF-8">
<LINK REL="preconnect" HREF="https://fonts.googleapis.com">
<LINK REL="preconnect" HREF="https://fonts.gstatic.com" CROSSORIGIN>
<LINK REL="stylesheet" HREF="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap">
<STYLE>body, td, th, div, p, span, a { font-family: 'Noto Sans KR', sans-serif; }</STYLE>
<SCRIPT>window.RufflePlayer = window.RufflePlayer || {}; window.RufflePlayer.config = { autoplay: 'on', unmuteOverlay: 'hidden', splashScreen: false };</SCRIPT>
<SCRIPT SRC="https://unpkg.com/@ruffle-rs/ruffle"></SCRIPT>'''

LINK = re.compile(r'''((?:HREF|SRC)=["']|\w+Win\(\\?')([^"'\\]+)''', re.I)


def absolutize(html, rel):
    """사이트(atkj/) 밖으로 나가는 상대 링크 → 절대 URL"""
    page = BASE + rel
    def fix(m):
        ref = m.group(2)
        if re.match(r'(?i)[a-z]+:|#', ref):
            return m.group(0)
        u = urllib.parse.urljoin(page, ref)
        return m.group(0) if u.startswith(BASE) else m.group(1) + u
    return LINK.sub(fix, html)


def build_html(src, rel, tr):
    s = open(src, 'rb').read().decode('cp932')
    out, last = [], 0
    for m, t in segments(s):
        ko = tr.get(t)
        if ko:
            a, b = m.span()
            seg = m.group()
            out.append(s[last:a] + seg.replace(t, ko))
            last = b
    s = ''.join(out) + s[last:]
    s = re.sub(r'(?i)<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=Shift_JIS">', HEAD, s)
    s = re.sub(r'(?i)<HTML>', '<HTML LANG="ko">', s, count=1)
    s = s.replace('if ( MM_FlashCanPlay ) {', 'if ( true ) { // 한글판: Ruffle 로 재생')
    s = absolutize(s, rel)
    return s


def build_js(src):
    s = open(src, 'rb').read().decode('cp932')
    # 한글판: Flash 는 Ruffle 이 재생하므로 항상 Flash 레이아웃을 쓴다
    s = s.replace('function getFlashPlayerVersion() {', 'function getFlashPlayerVersion() { return 9;')
    return s


def main():
    tr = json.load(open(os.path.join(ROOT, 'translation', 'strings.json'), encoding='utf-8'))
    if os.path.exists(KO):
        shutil.rmtree(KO)
    n_img = 0
    for src in glob.glob(os.path.join(JP, '**', '*'), recursive=True):
        if os.path.isdir(src):
            continue
        rel = os.path.relpath(src, JP).replace(os.sep, '/')
        dst = os.path.join(KO, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        low = rel.lower()
        if low.endswith(('.html', '.htm')):
            open(dst, 'w', encoding='utf-8').write(build_html(src, rel, tr))
        elif low.endswith('.js'):
            open(dst, 'w', encoding='utf-8').write(build_js(src))
        elif os.path.exists(os.path.join(IMG, rel)):
            shutil.copy2(os.path.join(IMG, rel), dst)
            n_img += 1
        else:
            shutil.copy2(src, dst)
    # 번역이 빠진 일본어 구간 검사
    left = []
    for f in glob.glob(os.path.join(KO, '**', '*.html'), recursive=True):
        s = open(f, encoding='utf-8').read()
        for _, t in segments(s):
            if re.search(r'[぀-ヿ一-鿿]', t) and 'document.write' not in t and '== -1' not in t:
                left.append((os.path.relpath(f, KO), t))
    print(f'ko/ built: {n_img} images replaced, {len(left)} Japanese segments left')
    for f, t in left:
        print('  ', f, t)


if __name__ == '__main__':
    main()
