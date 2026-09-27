# 「터치! 커비」 공식 홈페이지 한글화

원본: https://www.nintendo.co.jp/ds/atkj/index.html (2005, Shift_JIS 정적 HTML)

## 폴더
| 경로 | 내용 |
|---|---|
| `jp/` | 원본 미러 (HTML 21, 이미지 364, SWF 20). `tools/crawl.py` 로 재귀 수집 |
| `ko/` | 한글판 결과물. `tools/build.py` 가 생성 (직접 고치지 말 것) |
| `img_ko/` | 한글로 다시 그린 이미지 140개. `tools/render_img.py` 가 생성 |
| `translation/strings.json` | HTML 본문·ALT 번역 {원문: 번역}. 값이 "" 이면 원문 유지 (JS 조각) |
| `tools/img_spec.py` | 이미지별 사양 (지울 영역, 번역문, 색, 외곽선) |
| `fonts/Jua-Regular.ttf` | 배민 주아체 (OFL, Google Fonts). 주아체에 없는 「」 등은 히라기노 마루고딕으로 대체 |
| `_sheets/cmp_*.png` | 원본/한글판 비교 이미지, `_shots/` 페이지 스크린샷 |

## 빌드
```
python3 -m venv .venv && .venv/bin/pip install pillow numpy opencv-python-headless fonttools playwright
.venv/bin/python tools/crawl.py        # 원본 미러 (이미 받은 파일은 건너뜀)
.venv/bin/python tools/extract.py      # 새 일본어 구간을 strings.json 에 추가
.venv/bin/python tools/render_img.py   # 이미지 한글화 (그룹 이름을 주면 그것만)
.venv/bin/python tools/build.py        # ko/ 생성. "0 Japanese segments left" 확인
.venv/bin/python tools/shot.py         # 스크린샷 (python -m playwright install chromium 필요)
```
로컬 확인: `cd ko && python3 -m http.server` → http://localhost:8000

## 배포 (Cloudflare Pages)
`ko/` 가 완성된 정적 사이트라 빌드 없이 그대로 올림.
- Git 연동: Build command 비움, Build output directory `website/ko`
- 또는 직접 업로드: `npx wrangler pages deploy website/ko --project-name <이름>`

`tools/` 를 고쳤으면 `build.py` 로 `ko/` 를 다시 만든 뒤 커밋할 것 (Pages 는 `ko/` 만 봄).
파일 419개, 가장 큰 파일 10.6MB (movie1.swf) → Pages 한도(2만 개, 파일당 25MiB) 안.

## 한글판에서 바뀌는 것
- 인코딩 UTF-8, `<html lang="ko">`, 본문 글꼴 Noto Sans KR (Google Fonts)
- 이미지 글자 → 주아체. 영문(Touch!, BEAM, Ravine Road, Click! 등)과 게임 스크린샷 속 글자는 원본 유지
- 로고 → `Patch Tool/assets/logo/logo.png` (흰 테두리를 둘러서 사용)
- Flash → Ruffle 로 재생. Flash 감지 스크립트는 항상 통과시킴 (`kirby.js`, 팝업의 `MM_FlashCanPlay`)
- 사이트 밖 링크(닌텐도 홈, DS 톱, 이웃 게임 페이지)는 nintendo.co.jp 절대 URL

## 남은 것 / 확인 필요
- **SWF 안의 글자는 일본어 그대로** (트레이닝 무비 6, 무비 2, 카피 능력 무비 11+메인). SWF 편집이 필요
- `package.jpg` 는 일본판 실물 패키지 사진이라 그대로 둠
- `nofla.gif` (Flash 없을 때 안내)는 Ruffle 을 쓰면 안 보이므로 번역하지 않음
- 용어집(`../legacy/translation/glossary.md`)에 없는 용어 — 확정 필요:

| 원문 | 번역 | 비고 |
|---|---|---|
| カラクリ | 장치 | 페이지 제목·메뉴·본문 전체 |
| ブレドー / デンドン / プクラ | 블레도 / 덴돈 / 푸쿠라 | 음역 |
| ヤリワドルディ | 창 웨이들 디 | 용어집 「웨이들 디」 기준 |
| 攻略本情報 (menu/bo10) | 공략본 정보 | 링크 없는 메뉴 |
| スーパー大砲 / ブレードバー / ノイズエリア 등 | 슈퍼 대포 / 블레이드 바 / 노이즈 에리어 | 음역·직역 |
| ステージ 이름 (ラビン ロード 등) | 래빈 로드 등 | 용어집: 스테이지명은 영문 유지 → 큰 글씨만 음역, 영문은 그대로 |
