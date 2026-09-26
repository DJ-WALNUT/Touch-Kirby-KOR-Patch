"""JP/US 차이 파일을 올바른 포맷으로 렌더링해 비교 페이지 생성.

사용: python dump2.py JP.nds US.nds OUTDIR
  OUTDIR/index.html, OUTDIR/img/*.png, OUTDIR/assets.json
"""
import sys, os, json, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from ndslib import load_rom, write_png
import kfmt, kasset


def render(rom, name):
    """반환: (kind, [(label, Canvas)], info)"""
    key, kind = kasset.group_of(rom, name)
    if kind == 'pal':
        pal = kfmt.pal_from(kasset.dec(rom, name)[0])
        cv = kfmt.Canvas(16, (len(pal) + 15) // 16, [(0, 0, 0)] + pal)
        cv.idx = [i + 1 for i in range(len(pal))] + [-1] * (cv.w * cv.h - len(pal))
        return 'palette', [('', cv)], {'colors': len(pal)}
    if kind == 'skip':
        base = name.rsplit('/', 1)[1]
        return ('scr(chr없음)' if 'scr_' in base else base.split('_')[0]), [], {}
    g = kasset.Group(rom, key, kind)
    label = {'c05': '05cell', 'c06': '06anim', 'bg': 'bg', 'sheet': 'chr'}[kind]
    info = {'pal': g.pal_name.rsplit('/', 1)[1] if g.pal_name else None}
    return '%s %dbpp' % (label, g.bpp), [(lb, lay.render()) for lb, lay, _ in g.views], info


def main():
    JP, US, OUT = sys.argv[1:4]
    os.makedirs(OUT + '/img', exist_ok=True)
    jp, us = load_rom(JP), load_rom(US)
    diff = [n for n in sorted(set(jp) & set(us)) if jp[n] != us[n]]
    rows = []
    for i, n in enumerate(diff):
        d, base = n.rsplit('/', 1)
        bank = d.rsplit('/', 1)[1]
        rec = {'name': n, 'bank': bank, 'base': base, 'jp_size': len(jp[n]), 'us_size': len(us[n])}
        for tag, rom in (('jp', jp), ('us', us)):
            try:
                kind, cvs, info = render(rom, n)
            except Exception as ex:
                kind, cvs, info = 'error: %s' % ex, [], {}
            imgs = []
            for k, (lab, cv) in enumerate(cvs):
                if cv is None or cv.h > 2048:
                    continue
                fn = 'img/%s_%s_%d_%s.png' % (bank, base[:-4], k, tag)
                scale = 2 if cv.w <= 256 else 1
                write_png(OUT + '/' + fn, *cv.rgb(scale))
                imgs.append(fn)
            rec[tag] = {'kind': kind, 'imgs': imgs, 'info': info}
        rows.append(rec)
        if (i + 1) % 50 == 0:
            print('  %d/%d' % (i + 1, len(diff)))
    json.dump(rows, open(OUT + '/assets.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    write_html(rows, OUT)
    from collections import Counter
    print(Counter(r['jp']['kind'].split(' ')[0] for r in rows))


CSS = """
:root{color-scheme:dark}body{font:13px system-ui;background:#16181d;color:#e6e6e6;margin:0;padding:16px}
h1{font-size:18px;margin:0 0 4px}.sub{color:#9aa0aa;margin-bottom:14px}
.bar{position:sticky;top:0;background:#16181d;padding:10px 0;border-bottom:1px solid #2c303a;z-index:9;margin-bottom:12px}
button{background:#252932;color:#ddd;border:1px solid #39404d;border-radius:6px;padding:6px 12px;margin:0 6px 4px 0;cursor:pointer}
button.on{background:#3d6fd6;border-color:#3d6fd6;color:#fff}
.it{border:1px solid #2c303a;border-radius:8px;margin-bottom:10px;background:#1c1f26}
.hd{padding:7px 10px;display:flex;gap:10px;flex-wrap:wrap;border-bottom:1px solid #2c303a}
.nm{font-family:ui-monospace,monospace;color:#8fd3ff}.tag{font-size:11px;background:#2c303a;border-radius:4px;padding:2px 7px;color:#aab}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:10px}.cell{min-width:0}
.cell b{display:block;font-size:11px;color:#9aa0aa;margin-bottom:5px}
.cell img{max-width:100%;image-rendering:pixelated;display:block;margin-bottom:4px}
.none{color:#666;font-size:11px;padding:14px;text-align:center;background:#0c0d10;border-radius:4px}
"""
JS = """function F(b,k){document.querySelectorAll('.bar button').forEach(x=>x.classList.remove('on'));b.classList.add('on');
document.querySelectorAll('.it').forEach(e=>{e.style.display=(k=='all'||e.dataset.bank==k||e.dataset.kind==k)?'':'none'})}"""


def write_html(rows, OUT):
    h = ['<!doctype html><meta charset="utf-8"><title>Touch Kirby assets v2</title><style>', CSS, '</style>',
         '<h1>터치커비 JP/US 차이 파일 %d개 (v2 렌더러)</h1>' % len(rows),
         '<div class="sub">05 셀 컨테이너 / 06 애니 / chr+col+scr BG 합성 렌더링</div><div class="bar">',
         '<button class="on" onclick="F(this,\'all\')">전체</button>']
    for b in sorted(set(r['bank'] for r in rows)):
        h.append('<button onclick="F(this,\'%s\')">%s</button>' % (b, b))
    for k in sorted(set(r['jp']['kind'].split(' ')[0] for r in rows)):
        h.append('<button onclick="F(this,\'%s\')">%s</button>' % (k, k))
    h.append('</div><script>' + JS + '</script>')
    for r in rows:
        h.append('<div class="it" data-bank="%s" data-kind="%s"><div class="hd"><span class="nm">%s</span><span class="tag">%s</span><span class="tag">%s</span><span class="tag">JP %s B / US %s B</span></div><div class="pair">'
                 % (r['bank'], r['jp']['kind'].split(' ')[0], html.escape(r['base']), r['bank'],
                    html.escape(r['jp']['kind']), format(r['jp_size'], ','), format(r['us_size'], ',')))
        for t, lab in (('jp', '일본판'), ('us', '미국판')):
            h.append('<div class="cell"><b>%s</b>' % lab)
            if r[t]['imgs']:
                for f in r[t]['imgs']:
                    h.append('<img loading="lazy" src="%s">' % f)
            else:
                h.append('<div class="none">렌더 없음 (%s)</div>' % html.escape(r[t]['kind']))
            h.append('</div>')
        h.append('</div></div>')
    open(OUT + '/index.html', 'w', encoding='utf-8').write(''.join(h))


if __name__ == '__main__':
    main()
