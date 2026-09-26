"""한글패치 한 번에 빌드.

  python tools/build.py [--no-title] [--clean]

  1. 일본판 ROM 확인 (SHA1)
  2. kpatch export    대상 그래픽을 work/ 에 추출 (--clean 이면 work/ 를 지우고 새로)
  3. ktext render     translation/render/*.json 사양대로 한국어 글자를 그림
  4. import_art       assets/title/title_design.png → 타이틀 화면 (--no-title 이면 건너뜀)
  5. title_credit     타이틀 크레딧 문구
  6. ktext check      모든 그래픽이 원래 타일 용량 안에 들어가는지 검사 (초과가 있으면 중단)
  7. kpatch build     out/Touch Kirby (KR).nds, out/TouchKirby_KR.bps 생성
  8. verify           빌드된 ROM 을 다시 읽어 work/ PNG 와 픽셀 비교
"""
import os, sys, shutil, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
import config

TOOLS = os.path.dirname(os.path.abspath(__file__))
TITLE_PNG = 'bank04bin/chr_title__scr_title.png'


def run(title, script, *args, capture=False):
    print('\n== %s' % title, flush=True)
    cmd = [sys.executable, os.path.join(TOOLS, script)] + list(args)
    if not capture:
        subprocess.run(cmd, check=True, cwd=config.ROOT)
        return ''
    r = subprocess.run(cmd, check=True, cwd=config.ROOT, capture_output=True, text=True, encoding='utf-8')
    return r.stdout


def main():
    argv = sys.argv[1:]
    config.check_rom()
    print('일본판 ROM 확인:', config.ROM_JP)
    if '--clean' in argv and os.path.isdir(config.WORK):
        shutil.rmtree(config.WORK)
    # export 는 이미 있는 work PNG 를 덮어쓰지 않으므로 --force 로 항상 원본에서 다시 시작
    run('1/7 원본 그래픽 추출', 'kpatch.py', 'export', '--force')
    run('2/7 번역 글자 렌더', 'ktext.py', 'render')
    if '--no-title' not in argv:
        run('3/7 타이틀 디자인 적용', 'import_art.py', config.TITLE_DESIGN, TITLE_PNG, '--screen-h', '192', '--keep-bank')
        run('4/7 타이틀 크레딧', 'title_credit.py')
    out = run('5/7 타일 용량 검사', 'ktext.py', 'check', capture=True)
    lines = out.splitlines()
    over = [l for l in lines if ' 초과 ' in l]
    notes = [l for l in lines if l.startswith('    ') and '오브젝트 테두리' not in l]
    print('용량 OK %d개, 초과 %d개' % (sum(1 for l in lines if ' OK ' in l), len(over)))
    for l in over + notes:  # notes: 타일 밖 픽셀 무시 등 참고 메시지
        print(l)
    if over:
        raise SystemExit('타일 용량 초과가 있어 빌드를 중단합니다. (실기에서 그래픽이 깨짐)')
    run('6/7 ROM 빌드', 'kpatch.py', 'build')
    run('7/7 검증', 'verify.py')
    print('\n완료. 배포용 패치: %s' % config.OUT_BPS)


if __name__ == '__main__':
    main()
