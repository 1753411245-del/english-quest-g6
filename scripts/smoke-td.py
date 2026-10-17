#!/usr/bin/env python3
"""塔防模式的回归冒烟测试。

用法：
    python scripts/smoke-td.py                # 自动探测 Edge / Chrome
    python scripts/smoke-td.py <浏览器exe路径>

做三件事：
  1. 用无头浏览器加载 grade7.html，注入自动玩家
  2. 让脚本自己建满六座塔、逐题答对，跑完整个战场
  3. 断言战斗结果为「胜利」，且每题都走完了结算

退出码 0 表示通过。改过塔防相关代码（TD_* / td* 函数）后建议跑一次。
"""
import io, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'grade7.html')

BROWSERS = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
]

AUTOPLAY = r'''
var VT = 0, GUARD = 0, LOG = [];
try {
  render();
  openTd();
  tdStart('u1-m1');
  B.loopId = -999;
  B.gold = 9999;
  var ks = ['word','spell','listen','grammar','word','grammar'];
  for (var i = 0; i < 6; i++){ B.sel = { type:'build', slot:i }; tdBuild(0, ks[i]); }
  B.sel = null; tdPanel();
  if (Object.keys(B.towers).length !== 6) LOG.push('TOWER_BUILD_FAIL');

  var iv = setInterval(function(){
    GUARD++;
    VT += 120;
    if (B.quiz) answerQuiz();
    else if (B.phase === 'build') tdNextWave();
    tdFrame(VT);
    if (B.phase === 'win' || B.phase === 'lose' || GUARD > 4000){
      clearInterval(iv);
      document.body.setAttribute('data-td', JSON.stringify({
        phase: B.phase, waves: B.waveIdx + 1, q: B.stats.q, ok: B.stats.ok,
        lives: B.lives, gold: B.gold, log: LOG.slice(0, 6)
      }));
    }
  }, 12);

  function answerQuiz(){
    var q = B.quiz;
    if (q.type === 'spell'){
      var used = [];
      q.answer.split('').forEach(function(ch){
        for (var i = 0; i < q.letters.length; i++){
          if (used.indexOf(i) < 0 && q.letters[i].toLowerCase() === ch.toLowerCase()){
            used.push(i); tdPickLtr(i); break;
          }
        }
      });
    } else {
      tdChoose(q.options.indexOf(q.answer));
    }
  }
} catch(e){
  document.body.setAttribute('data-td', 'EXCEPTION: ' + e.message);
}
'''


def pick_browser():
    if len(sys.argv) > 1:
        return sys.argv[1]
    for p in BROWSERS:
        if os.path.exists(p):
            return p
    print('找不到 Edge 或 Chrome，请把浏览器路径作为参数传入')
    sys.exit(2)


def main():
    html = io.open(SRC, encoding='utf-8').read()
    m = re.search(r'render\(\);\s*</script>', html)
    if not m:
        print('注入点未找到，grade7.html 结尾结构可能已变化')
        sys.exit(2)

    tmp = tempfile.mkdtemp(prefix='td-smoke-')
    test = os.path.join(tmp, 't.html')
    io.open(test, 'w', encoding='utf-8').write(
        html[:m.start()] + AUTOPLAY + '\n</script>' + html[m.end():])

    exe = pick_browser()
    out = subprocess.run([
        exe, '--headless=new', '--disable-gpu', '--no-sandbox',
        '--virtual-time-budget=150000', '--window-size=800,900',
        '--user-data-dir=' + os.path.join(tmp, 'profile'),
        '--dump-dom', 'file:///' + test.replace(os.sep, '/'),
    ], capture_output=True, text=True, timeout=300).stdout

    hit = re.search(r'data-td="([^"]*)"', out)
    if not hit:
        print('FAIL: 页面没有回报结果，可能脚本在初始化阶段就抛错了')
        sys.exit(1)

    raw = hit.group(1).replace('&quot;', '"').replace('&amp;', '&')
    print('结果: ' + raw)
    ok = ('"phase":"win"' in raw) and ('EXCEPTION' not in raw) and ('TOWER_BUILD_FAIL' not in raw)
    if ok:
        print('PASS 塔防冒烟通过')
        sys.exit(0)
    print('FAIL 未达成胜利，检查上面的结果')
    sys.exit(1)


if __name__ == '__main__':
    main()
