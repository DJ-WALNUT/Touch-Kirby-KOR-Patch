"""ko/ 페이지 전체 스크린샷 → _shots/ (로컬 http 서버로 띄워서)
  python tools/shot.py [페이지…]   예: index.html menu/index.html"""
import os, sys, threading, http.server, functools
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = sys.argv[1:] or ['index.html', 'menu/index.html', 'about/index.html', 'sousa/index.html', 'training/index.html',
                          'maingame/index.html', 'boss/index.html', 'rainbow/index.html', 'copy/index.html',
                          'karakuri/index.html', 'teki/index.html', 'soft/index.html', 'about/movie/movie1.html',
                          'training/t1/index.html', 'copy/movie/index.html']
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=os.path.join(ROOT, 'ko'))
H.log_message = lambda *a: None
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8765), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.makedirs(os.path.join(ROOT, '_shots'), exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 700, 'height': 800})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    for page in PAGES:
        errs.clear()
        pg.goto(f'http://127.0.0.1:8765/{page}', wait_until='networkidle')
        pg.wait_for_timeout(1500)
        out = os.path.join(ROOT, '_shots', page.replace('/', '_').replace('.html', '.png'))
        pg.screenshot(path=out, full_page=True)
        print(page, 'errors:', errs[:3])
    b.close()
srv.shutdown()
