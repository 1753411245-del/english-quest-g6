#!/usr/bin/env python3
"""375 宽窄屏溢出检查：拼写关与塔防拼写面板。

Edge/Chrome headless 有约 477px 的最小视口，直接 --window-size=375 会被
先按 477 渲染再裁切，量出来永远不溢出。所以这里把布局宽度强制成 375
再读 scrollWidth / 元素的实际右边界。

用法：
    python scripts/check-narrow.py
"""
import io, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'grade7.html')

BROWSERS = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
]

PROBE = r'''
var OUT = [];
/* headless 视口压不到 375 以下，直接把 html/body 钉成 375 当容器量 */
function pin375(){
  var st = document.createElement('style');
  st.textContent = 'html,body{width:375px!important;min-width:0!important;overflow-x:hidden}';
  document.head.appendChild(st);
}
function measure(tag){
  var w = 375;
  var over = [];
  var all = document.querySelectorAll('#app *');
  for (var i = 0; i < all.length; i++){
    var r = all[i].getBoundingClientRect();
    if (r.width > 0 && r.right > w + 0.6){
      over.push((all[i].className || all[i].tagName) + ':' + Math.round(r.right));
      if (over.length > 4) break;
    }
  }
  OUT.push({ tag: tag, sw: document.body.scrollWidth,
             cw: document.body.clientWidth, vw: window.innerWidth, over: over });
}
try {
  render();
  pin375();
  startLevel('st', 1);
  pickLetter(0); pickLetter(1);
  updateSpellUI();
  measure('spellgame');
  OUT.push({ tag: 'spellgame.height', h: document.body.scrollHeight });

  // 塔防拼写面板
  openTd(); tdStart('u1-m1');
  B.loopId = -999; B.gold = 9999;
  var u0 = BOOK.units[0];
  var q1 = makeSpell(u0, u0.words[0]);
  B.phase = 'fight';
  B.quiz = q1; B.spell = []; B.answered = false;
  B.quizE = { id:'t', pos:0.3, hp:2, tried:{}, badge: tdBadge(q1) };
  B.quizSlot = 0;
  tdPickLtr(0); tdPickLtr(1);
  tdPanel(); tdPaint(); tdHudSync();
  measure('tdspell');
  OUT.push({ tag: 'tdspell.height', h: document.body.scrollHeight,
             back: !!document.getElementById('tdBack'),
             submit: !!document.getElementById('tdSubmit'),
             opsW: (function(){
               var l = document.getElementById('tdLine');
               var e = document.querySelector('.tdedit');
               return e ? Math.round(e.getBoundingClientRect().width) : -1;
             })() });
} catch(e){
  OUT.push({ tag: 'EXCEPTION', msg: e.message });
}
document.body.setAttribute('data-narrow', JSON.stringify(OUT));
'''


def main():
    html = io.open(SRC, encoding='utf-8').read()
    m = re.search(r'render\(\);\s*</script>', html)
    if not m:
        print('注入点未找到'); sys.exit(2)
    tmp = tempfile.mkdtemp(prefix='narrow-')
    test = os.path.join(tmp, 'n.html')
    io.open(test, 'w', encoding='utf-8').write(
        html[:m.start()] + PROBE + '\n</script>' + html[m.end():])
    exe = next((p for p in BROWSERS if os.path.exists(p)), None)
    if not exe:
        print('找不到浏览器'); sys.exit(2)
    out = subprocess.run([
        exe, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-sandbox',
        '--virtual-time-budget=3000',
        # headless 最小视口约 477 物理像素，靠 2 倍缩放把 CSS 视口压到 375
        '--window-size=750,1500', '--force-device-scale-factor=2',
        '--user-data-dir=' + os.path.join(tmp, 'profile'),
        '--dump-dom', 'file:///' + test.replace(os.sep, '/'),
    ], capture_output=True, text=True, timeout=180).stdout
    hit = re.search(r'data-narrow="([^"]*)"', out)
    if not hit:
        print('FAIL 没有回报结果'); sys.exit(1)
    raw = hit.group(1).replace('&quot;', '"').replace('&amp;', '&')
    print(raw)
    if 'EXCEPTION' in raw:
        sys.exit(1)
    widths = re.findall(r'"sw":(\d+),"cw":(\d+)', raw)
    if widths and widths[0][1] != '375':
        print('WARN CSS 视口是 %s，不是 375，结论仅供参考' % widths[0][1])
    for sw, cw in widths:
        if int(sw) > int(cw):
            print('FAIL 横向溢出 sw=%s cw=%s' % (sw, cw)); sys.exit(1)
    if '"over":["' in raw:
        print('FAIL 有元素越界'); sys.exit(1)
    print('PASS 375 宽无横向溢出')


if __name__ == '__main__':
    main()
