"""jp/ HTML 에서 일본어가 든 텍스트 구간을 뽑아 translation/strings.json 에 추가한다 (기존 번역 유지).
구간 = 태그·따옴표·줄바꿈으로 끊긴 연속 문자열 중 일본어(가나·한자·전각)를 포함한 것.
strings.json = {원문: 번역}. 번역이 "" 이면 원문 유지 (JS 주석 등)."""
import glob, json, os, re
JA = re.compile(r'[　-ヿ一-鿿＀-￯]')
SEG = re.compile(r'''[^<>"'\n]+''')

def segments(s):
    for m in SEG.finditer(s):
        t = m.group().strip()
        if JA.search(t): yield m, t

if __name__ == '__main__':
    path = 'translation/strings.json'
    old = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
    out = {}
    for f in sorted(glob.glob('jp/**/*.html', recursive=True)):
        for _, t in segments(open(f, 'rb').read().decode('cp932')):
            out.setdefault(t, old.get(t, ''))
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    todo = [k for k, v in out.items() if not v]
    print(len(out), 'segments,', len(todo), 'untranslated')
    for k in todo: print('  ', k)
