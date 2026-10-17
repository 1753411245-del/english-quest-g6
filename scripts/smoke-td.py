#!/usr/bin/env python3
"""塔防模式的回归冒烟测试。

用法：
    python scripts/smoke-td.py                # 自动探测 Edge / Chrome
    python scripts/smoke-td.py <浏览器exe路径>

做四件事：
  1. 用无头浏览器加载 grade7.html，注入自动玩家
  2. 在全部塔位上建塔，验证「塔位数量」「拆塔返还一半」
  3. 逐题答对跑完整个战场，同时采样被瞄准敌人的位置
  4. 断言胜利、且答题期间敌人位置一直在变（战斗不冻结）

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
var lastPos = -1, frozen = 0, maxFrozen = 0, quizTicks = 0;
try {
  render();
  openTd();
  tdStart('u1-m1');
  B.loopId = -999;
  B.gold = 9999;

  LOG.push('slots=' + B.map.slots.length);

  /* 全部塔位建满，塔的种类轮着来 */
  var ks = ['word','spell','listen','grammar','word','grammar','spell','listen','word'];
  for (var i = 0; i < B.map.slots.length; i++){
    B.sel = { type:'build', slot:i };
    tdBuild(0, ks[i % ks.length]);
  }
  B.sel = null; tdPanel();
  if (Object.keys(B.towers).length !== B.map.slots.length){
    LOG.push('TOWER_BUILD_FAIL:' + Object.keys(B.towers).length);
  }

  /* 拆塔返还：词汇塔 50 金，应返 25 */
  var g0 = B.gold;
  B.sel = { type:'tower', slot:0 };
  tdSell(0);
  var back = B.gold - g0;
  if (back !== 25) LOG.push('SELL_BACK_BAD:' + back);
  if (B.towers[0]) LOG.push('SELL_NOT_REMOVED');
  B.sel = { type:'build', slot:0 }; tdBuild(0, 'word'); B.sel = null;

  var iv = setInterval(function(){
    GUARD++;
    VT += 120;
    if (B.quiz){ quizTicks++; answerQuiz(); }
    else if (B.phase === 'build') tdNextWave();
    tdFrame(VT);

    /* 冻结检测：被瞄准的敌人，位置应该每帧都在变化 */
    if (B.aim && B.aim.e && B.aim.e.hp > 0 && !B.aim.e.dead){
      if (lastPos >= 0 && Math.abs(B.aim.e.pos - lastPos) < 1e-9) frozen++;
      else frozen = 0;
      if (frozen > maxFrozen) maxFrozen = frozen;
      lastPos = B.aim.e.pos;
    } else { lastPos = -1; frozen = 0; }

    if (B.phase === 'win' || B.phase === 'lose' || GUARD > 6000){
      clearInterval(iv);
      document.body.setAttribute('data-td', JSON.stringify({
        phase: B.phase, waves: B.waveIdx + 1, q: B.stats.q, ok: B.stats.ok,
        lives: B.lives, maxFrozen: maxFrozen, quizTicks: quizTicks,
        log: LOG.slice(0, 8)
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
      tdSubmitSpell();   // 填满后要手动提交
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

    fails = []
    if '"phase":"win"' not in raw:
        fails.append('没有通关')
    if 'EXCEPTION' in raw:
        fails.append('脚本抛异常')
    if 'TOWER_BUILD_FAIL' in raw:
        fails.append('塔位没有全部建成')
    if 'SELL_BACK_BAD' in raw or 'SELL_NOT_REMOVED' in raw:
        fails.append('拆塔返还或移除失败')
    mf = re.search(r'"maxFrozen":(\d+)', raw)
    if not mf or int(mf.group(1)) > 4:
        fails.append('答题期间敌人位置停止变化（战斗被冻结）')

    if fails:
        print('FAIL ' + '；'.join(fails))
        sys.exit(1)
    print('PASS 塔防冒烟通过（拆塔返还正常、战斗未冻结）')
    sys.exit(0)


if __name__ == '__main__':
    main()
