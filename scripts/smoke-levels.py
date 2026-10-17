#!/usr/bin/env python3
"""答题闯关（7 关模式）的回归冒烟测试。

遍历全部单元 × 全部关卡，自动答完每一题，断言：
  · 每关都能走到结算页
  · 全对时拿到 3 星
  · 没有题目卡死或抛异常

用法：
    python scripts/smoke-levels.py
"""
import io, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'grade7.html')

BROWSERS = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
]

AUTOPLAY = r'''
var LOG = [], totalQ = 0, levels = 0;
function answerOrder(q){
  var used = [], words = q.answer.split(' ');
  words.forEach(function(w){
    for (var i = 0; i < q.tokens.length; i++){
      if (used.indexOf(i) < 0 && q.tokens[i].toLowerCase() === w){
        used.push(i); pickToken(i); break;
      }
    }
  });
  checkOrder();
}
function answerSpell(q){
  var used = [];
  q.answer.split('').forEach(function(ch){
    for (var i = 0; i < q.letters.length; i++){
      if (used.indexOf(i) < 0 && q.letters[i].toLowerCase() === ch.toLowerCase()){
        used.push(i); pickLetter(i); break;
      }
    }
  });
  checkSpell();   // 填满后要手动提交
}
try {
  render();
  BOOK.units.forEach(function(u){
    for (var lv = 0; lv < NLV; lv++){
      G = null; startLevel(u.id, lv);
      levels++;
      var guard = 0;
      while (!G.result && guard++ < 40){
        var q = G.qs[G.i];
        if (!q){ LOG.push('NOQ ' + u.id + '/' + lv); break; }
        totalQ++;
        if (q.type === 'choice' || q.type === 'listen' || q.type === 'grammar'){
          chooseOption(q.options.indexOf(q.answer));
        } else if (q.type === 'order') answerOrder(q);
        else if (q.type === 'spell') answerSpell(q);
        else if (q.type === 'speak'){ G.answered = true; G.correct++; }
        if (!G.answered) LOG.push('NOT_ANSWERED ' + u.id + '/' + lv + ' ' + q.type);
        nextQuestion();
      }
      if (!G.result) LOG.push('NO_RESULT ' + u.id + '/' + lv);
      else if (G.result.stars !== 3){
        LOG.push('NOT_3STAR ' + u.id + '/' + lv + ' acc=' + G.result.acc.toFixed(2));
      }
    }
  });
} catch(e){
  LOG.push('EXCEPTION ' + e.message);
}
document.body.setAttribute('data-lv', JSON.stringify({
  units: BOOK.units.length, levels: levels, questions: totalQ, log: LOG.slice(0, 8)
}));
'''


def pick_browser():
    for p in BROWSERS:
        if os.path.exists(p):
            return p
    print('找不到 Edge 或 Chrome')
    sys.exit(2)


def main():
    html = io.open(SRC, encoding='utf-8').read()
    m = re.search(r'render\(\);\s*</script>', html)
    if not m:
        print('注入点未找到')
        sys.exit(2)

    tmp = tempfile.mkdtemp(prefix='lv-smoke-')
    test = os.path.join(tmp, 'l.html')
    io.open(test, 'w', encoding='utf-8').write(
        html[:m.start()] + AUTOPLAY + '\n</script>' + html[m.end():])

    out = subprocess.run([
        pick_browser(), '--headless=new', '--disable-gpu', '--no-sandbox',
        '--virtual-time-budget=60000', '--window-size=800,900',
        '--user-data-dir=' + os.path.join(tmp, 'profile'),
        '--dump-dom', 'file:///' + test.replace(os.sep, '/'),
    ], capture_output=True, text=True, timeout=300).stdout

    hit = re.search(r'data-lv="([^"]*)"', out)
    if not hit:
        print('FAIL 页面没有回报结果')
        sys.exit(1)
    raw = hit.group(1).replace('&quot;', '"').replace('&amp;', '&')
    print('结果: ' + raw)
    ok = ('"log":[]' in raw) and ('EXCEPTION' not in raw)
    if ok:
        print('PASS 全部关卡通过，每题均可作答并拿到三星')
        sys.exit(0)
    print('FAIL 见上面的日志')
    sys.exit(1)


if __name__ == '__main__':
    main()
