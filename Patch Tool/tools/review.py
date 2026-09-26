"""일본판 원본과 한글 결과를 나란히 보는 검토 페이지 생성 -> review.html

  python tools/review.py
"""
import sys, os, json, glob, re, html
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
ROOT = config.ROOT

# 큰 글자 / 확인 필요 목록 (작업 보고 기준)
FLAGS = {
    'chr_title': '타이틀 로고: 사용자 디자인 (assets/title/title_design.png → tools/import_art.py)',
    'trialmainmessage': '큰 글자: 폰트를 2배 확대해 찍음',
    'z_chr_lesson11_7': '큰 글자: 「그럼 / 해 볼까요!」', 'z_chr_lesson21_3': '큰 글자', 'z_chr_lesson31_4': '큰 글자',
    'z_chr_lesson41_4': '큰 글자', 'z_chr_lesson51_5': '큰 글자', 'z_chr_lesson61_5': '큰 글자',
    'chgmedalprizelist': '큰 글자: 원본보다 작음', 'sellvlname0': '큰 글자: 물결 배치 레벨명',
    'chr_pipepanicmedal': '큰 글자', 'chr_truckmedal': '큰 글자', 'chr_pipepanicnewranking': '큰 글자',
    'pipebutton': '큰 글자 / 그림자 1px 잘림', 'sgrank': '큰 글자: 칭호',
    'truckupinfo': '큰 글자: 칭호', 'z_chr_ed0': '엔딩 자막: 원본 13px → 11px',
    'selboss_s_': '보스게임 설명: 제목 칸·부제·효과음', 'selsubgame_s_': '서브게임 설명: 제목 칸·부제·효과음',
    'z_chr_op0': '오프닝 자막 (용량 맞춤: g11b 로 변경, 줄을 8px 격자에 정렬)', 'chr_pause': '일시정지 설명: 원본보다 획이 가늘 수 있음',
    'sgranking': '「랭크」 7px 가독성 / 그림자 1px 잘림', 'truckranking': '「랭크」 7px 가독성 / 그림자 1px 잘림',
    'pipeinfo': '그림자 1px 잘림', 'bossinfo': '「도로시아 마법사」 어순 (L303)',
    'noticeobj': '용량 맞춤: 글자 칸을 일본어 칸 위치에 맞춤', 'chgmedalhelpmsg': '용량 맞춤: 「새 코스」 문구 사이 빈칸',
    'chgmedalprizelist': '용량 맞춤: 숫자 위치 고정·자간 조정', 'menucommontext': '실기에서 깨졌던 파일 (용량 맞춤으로 수정)',
    'sellvlname0': '용량 부족으로 원본 영문 유지', 'sellvlname1': '가독성 때문에 원본 영문 유지',

    'z_chr_lesson11_3': '새로 번역한 레슨 그림 페이지', 'z_chr_lesson11_5': '새로 번역', 'z_chr_lesson31_2': '새로 번역',
    'z_chr_lesson31_3': '새로 번역', 'z_chr_lesson41_3': '새로 번역', 'z_chr_lesson51_4': '새로 번역 (그림 속 「빔」 버튼도 한글화)',
    'z_chr_lesson61_2': '새로 번역', 'z_chr_lesson61_4': '새로 번역', 'chr_pausebossbg': '새로 번역', 'chr_pausepicto': '새로 번역',
    'chr_pausetrainingbg': '새로 번역', 'z_chr_trialline': '새로 번역', 'z_chr_trialtime': '새로 번역',
    'z_chr_lesson': '레슨: 문장 조각 줄 이음 실기 확인',
}


def main():
    man = json.load(open(os.path.join(config.WORK, 'manifest.json'), encoding='utf-8'))
    lt = {}
    for f in glob.glob(os.path.join(config.TRANSLATION, 'length_table*.md')):
        for line in open(f, encoding='utf-8'):
            c = [x.strip() for x in line.strip().strip('|').split('|')]
            if len(c) >= 5 and re.match(r'L\d+$', c[0]):
                lt.setdefault(c[1], []).append(c[0])
    rows = []
    for key, m in sorted(man.items()):
        for rel in m['png']:
            base = rel.split('/')[-1][:-4]
            flags = [v for k, v in FLAGS.items() if k in base]
            rows.append((rel, m['note'], flags, lt.get(rel, [])))
    h = ['<!doctype html><meta charset="utf-8"><title>한글패치 검토</title><style>',
         'body{font:13px system-ui;background:#1d1f25;color:#ddd;margin:0;padding:16px}',
         'h1{font-size:18px}.it{border:1px solid #333;border-radius:8px;margin:0 0 12px;background:#24272e}',
         '.hd{padding:6px 10px;border-bottom:1px solid #333;display:flex;gap:8px;flex-wrap:wrap;align-items:center}',
         '.nm{font-family:ui-monospace,monospace;color:#8fd3ff}.fl{background:#6b3b12;color:#ffd9a8;border-radius:4px;padding:1px 6px;font-size:11px}',
         '.lt{background:#244a2b;color:#bfe8c6;border-radius:4px;padding:1px 6px;font-size:11px}.nt{color:#99a;font-size:11px}',
         '.pr{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:8px}.pr div{min-width:0}',
         '.pr b{display:block;font-size:11px;color:#99a;margin-bottom:4px}',
         'img{max-width:100%;image-rendering:pixelated;background:#3c3f48;zoom:2}',
         '.bar{position:sticky;top:0;background:#1d1f25;padding:8px 0;margin-bottom:8px;z-index:2}',
         'label{margin-right:12px}</style>',
         '<h1>터치! 커비 한글패치 검토 (%d장)</h1>' % len(rows),
         '<div class="bar"><label><input type="checkbox" id="f" onchange="F()"> 검토 표시가 있는 것만</label>',
         '<span class="fl">주황 = 검토 필요</span> <span class="lt">초록 = 칸 부족 표 ID</span></div>',
         '<script>function F(){var on=document.getElementById("f").checked;',
         'document.querySelectorAll(".it").forEach(function(e){e.style.display=(!on||e.dataset.f=="1")?"":"none"})}</script>']
    for rel, note, flags, ids in rows:
        h.append('<div class="it" data-f="%d"><div class="hd"><span class="nm">%s</span>' % (1 if flags or ids else 0, html.escape(rel)))
        for f in flags:
            h.append('<span class="fl">%s</span>' % html.escape(f))
        for i in ids:
            h.append('<span class="lt">%s</span>' % i)
        h.append('<span class="nt">%s</span></div><div class="pr">' % html.escape(note[:120]))
        h.append('<div><b>일본판</b><img loading="lazy" src="work/_jp/%s"></div>' % rel)
        h.append('<div><b>한글</b><img loading="lazy" src="work/%s"></div></div></div>' % rel)
    open(os.path.join(config.WORK, 'review.html'), 'w', encoding='utf-8').write(''.join(h))
    print('review.html: %d장' % len(rows))


if __name__ == '__main__':
    main()
