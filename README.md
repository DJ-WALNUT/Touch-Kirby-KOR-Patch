<p align="center">
  <img src="Patch%20Tool/assets/logo/logo_readme.png" alt="터치! 커비" width="720">
</p>

<h3 align="center">터치! 커비 (タッチ!カービィ) 일본판 한글패치</h3>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Nintendo%20DS-red" alt="Nintendo DS">
  <img src="https://img.shields.io/badge/patch-BPS-blue" alt="BPS">
  <img src="https://img.shields.io/badge/font-Galmuri-ff69b4" alt="Galmuri">
  <img src="https://img.shields.io/badge/python-3.9%2B-3776AB" alt="Python 3.9+">
</p>

---

닌텐도 DS 「タッチ!カービィ」(일본판)를 한국어로 즐길 수 있게 하는 비공식 한글패치입니다.

**해당 프로젝트는 Claude Opus 5.5 버전을 활용하여 진행하였으며, 에뮬레이터 및 실기 구동이 완벽히 검증되지 않았습니다.**

이 게임은 메뉴·레슨·설명 등 모든 글자가 **그림(타일)** 으로 들어 있습니다. 그래서 일본어 글자 그림을 하나하나 지우고 한글 도트 폰트로 다시 그려 넣었습니다.

- 메뉴, 파일 선택, 레슨, 일시정지 설명, 트라이얼, 메달 체인저, 골 게임, 엔딩 자막까지 그래픽 191장 한글화
- 타이틀 로고를 「터치! 커비」 한글 로고로 새로 디자인
- 용어는 [나무위키](https://namu.wiki/w/%ED%84%B0%EC%B9%98!%20%EC%BB%A4%EB%B9%84) 표기 기준
- 모든 그래픽이 원래 타일 용량 안에 들어가도록 맞춰, 실기(3DS)에서 깨지지 않게 검증

## 패치 적용

1. 일본판 ROM `Touch! Kirby (Japan).nds`를 준비합니다.
   - SHA1 `8df7de7c8bfb302865398a9d9e0cff8a79e7c50d`
2. [Releases](../../releases)에서 `TouchKirby_KR.bps`를 받습니다.
3. [Rom Patcher JS](https://www.marcrobledo.com/RomPatcher.js/)나 [Flips](https://github.com/Alcaro/Flips)로 ROM에 적용합니다.
4. 에뮬레이터나 실기(플래시 카트, 3DS의 TWiLight Menu++ 등)에서 실행합니다.

> ROM은 제공하지 않습니다. 가지고 있는 정품 게임에서 직접 추출해 주세요.

## 직접 빌드 · 번역 수정

패치 제작 도구와 번역 데이터는 [`Patch Tool/`](Patch%20Tool/)에 있습니다. 일본판 ROM만 있으면 명령 한 줄로 패치가 만들어집니다.

```sh
cd "Patch Tool"
pip install -r requirements.txt
python tools/build.py        # rom/ 에 일본판 ROM 을 넣은 뒤
```

번역 수정 방법, 타이틀 디자인 수정 방법, 그래픽 포맷 설명은 [Patch Tool/README.md](Patch%20Tool/README.md)를 보세요.

## 크레딧

- 한글화 · 타이틀 디자인: **WALNUT** (2026)
- 폰트: [갈무리(Galmuri)](https://github.com/quiple/galmuri) by Lee Minseo (quiple), SIL Open Font License 1.1
- 용어: [나무위키 「터치! 커비」](https://namu.wiki/w/%ED%84%B0%EC%B9%98!%20%EC%BB%A4%EB%B9%84)

## 면책

- 비공식 팬 번역입니다. 「タッチ!カービィ」, 「커비」와 관련 상표·저작권은 Nintendo / HAL Laboratory에 있습니다.
- 이 저장소는 ROM이나 게임 데이터를 배포하지 않습니다.
