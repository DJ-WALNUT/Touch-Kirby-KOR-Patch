"""nintendo.co.jp/ds/atkj/ 를 재귀적으로 미러링한다 → website/jp/
HTML·CSS·JS 안의 모든 따옴표 문자열 / url() 에서 상대경로를 뽑아 따라간다 (JS 문자열 안 링크 포함).
  python tools/crawl.py
"""
import os, re, sys, time, subprocess, urllib.parse, zlib
from collections import deque

BASE = 'https://www.nintendo.co.jp/ds/atkj/'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'jp')
TEXT_EXT = ('.html', '.htm', '.css', '.js')
EXT = r'(?:html?|gif|jpe?g|png|swf|css|js|mid|wav|mp3|ico|txt|xml|pdf|zip|flv)'
PAT = re.compile(r'''["'(=]\s*([^"'()<>\s]+?\.''' + EXT + r''')(?:[?#][^"'()\s]*)?\s*["')]''', re.I)

def fetch(url):
    # python 인증서 저장소 문제를 피하려고 curl 사용
    r = subprocess.run(['curl', '-sL', '-w', '%{http_code}', '-o', '-', url], capture_output=True)
    code = r.stdout[-3:].decode()
    return code, (r.stdout[:-3] if code == '200' else None)

def main():
    seen, q, missing = set(), deque([BASE + 'index.html']), []
    while q:
        url = q.popleft()
        if url in seen: continue
        seen.add(url)
        rel = url[len(BASE):]
        path = os.path.join(OUT, rel)
        if os.path.exists(path):
            data = open(path, 'rb').read()
        else:
            st, data = fetch(url)
            if data is None:
                missing.append((rel, st)); continue
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, 'wb').write(data)
            time.sleep(0.05)
        if rel.lower().endswith('.swf'):
            # SWF 가 loadMovie 로 부르는 외부 파일 (copy/movie/main.swf → copy1~11.swf)
            body = zlib.decompress(data[8:]) if data[:3] == b'CWS' else data[8:]
            for ref in set(re.findall(rb'[\w./-]+\.(?:swf|flv|jpg|mp3|xml|txt)', body)):
                u = urllib.parse.urljoin(url, ref.decode())
                if u.startswith(BASE) and u not in seen: q.append(u)
            continue
        if not rel.lower().endswith(TEXT_EXT): continue
        text = data.decode('shift_jis', 'replace').replace('¥', '/').replace('\\', '')
        for m in PAT.finditer(text):
            ref = m.group(1).replace('\\', '')
            if ref.startswith(('javascript:', 'mailto:')): continue
            u = urllib.parse.urljoin(url, ref).split('#')[0].split('?')[0]
            if u.startswith(BASE) and u not in seen:
                q.append(u)
    print(f'{len(seen) - len(missing)} files, {len(missing)} missing')
    for rel, st in missing: print('  missing', st, rel)

if __name__ == '__main__':
    main()
