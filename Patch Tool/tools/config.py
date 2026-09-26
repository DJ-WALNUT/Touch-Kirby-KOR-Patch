"""경로 설정. 모든 도구가 이 파일을 통해 위치를 찾는다.

ROM 위치는 기본값(rom/ 폴더) 대신 환경변수로 바꿀 수 있다:
  KIRBY_JP_ROM=/경로/Touch! Kirby (Japan).nds
  KIRBY_US_ROM=/경로/Kirby - Canvas Curse (USA).nds   (선택: 비교용 참고 이미지에만 씀)
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ROM_JP = os.environ.get('KIRBY_JP_ROM') or os.path.join(ROOT, 'rom', 'Touch! Kirby (Japan).nds')
ROM_US = os.environ.get('KIRBY_US_ROM') or os.path.join(ROOT, 'rom', 'Kirby - Canvas Curse (USA).nds')
ROM_JP_SHA1 = '8df7de7c8bfb302865398a9d9e0cff8a79e7c50d'

WORK = os.path.join(ROOT, 'work')            # 추출·합성 중간 결과 (git 에 올리지 않음)
OUT = os.path.join(ROOT, 'out')              # 빌드 결과 ROM / BPS (git 에 올리지 않음)
PREVIEW = os.path.join(ROOT, 'work', '_preview')
DATA = os.path.join(ROOT, 'data')
TARGETS = os.path.join(DATA, 'targets.json')
TRANSLATION = os.path.join(ROOT, 'translation')
SPECS = os.path.join(TRANSLATION, 'render')
FONTS = os.path.join(ROOT, 'fonts')
TITLE_DESIGN = os.path.join(ROOT, 'assets', 'title', 'title_design.png')

OUT_ROM = os.path.join(OUT, 'Touch Kirby (KR).nds')
OUT_BPS = os.path.join(OUT, 'TouchKirby_KR.bps')


def check_rom():
    """일본판 ROM 이 있는지, 원본과 같은지 확인"""
    import hashlib
    if not os.path.exists(ROM_JP):
        raise SystemExit('일본판 ROM 이 없습니다: %s\n  rom/ 폴더에 넣거나 KIRBY_JP_ROM 환경변수로 경로를 지정하세요.' % ROM_JP)
    h = hashlib.sha1(open(ROM_JP, 'rb').read()).hexdigest()
    if h != ROM_JP_SHA1:
        raise SystemExit('ROM 이 다릅니다 (SHA1 %s). 필요한 원본: %s' % (h, ROM_JP_SHA1))
