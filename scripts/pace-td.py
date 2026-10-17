#!/usr/bin/env python3
"""塔防节奏压力测试：模拟真实答题速度，找出能守住 / 守不住的边界。

按 60fps 推进游戏时间，每道题模拟「思考 N 秒」再作答，跑完整的 4 波。
分别测 2 / 4 / 6 秒三档，看漏怪情况。

用法：
    python scripts/pace-td.py
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

RUNNER = r'''
function buildFull(){
  var ks = ['word','spell','listen','grammar','word','spell','listen','grammar','word'];
  for (var i = 0; i < B.map.slots.length; i++){
    B.sel = { type:'build', slot:i }; tdBuild(0, ks[i]);
  }
  B.sel = null;
}

function runPace(thinkMs){
  var VT = 0, qStart = -1, frames = 0;
  render(); openTd(); tdStart('u1-m1');
  B.loopId = -999; B.gold = 99999; B.last = 0;
  buildFull();
  for (frames = 0; frames < 120000; frames++){
    VT += 16;
    if (B.quiz){
      if (qStart < 0) qStart = VT;
      if (VT - qStart >= thinkMs){ tdResolve(true); qStart = -1; }
    } else {
      qStart = -1;
      if (B.phase === 'build') tdNextWave();
    }
    tdFrame(VT);
    if (B.phase === 'win' || B.phase === 'lose') break;
  }
  return { think: thinkMs / 1000, phase: B.phase, lives: B.lives,
           escaped: B.map.lives - B.lives, q: B.stats.q, ok: B.stats.ok,
           secs: +(VT / 1000).toFixed(1) };
}

/* 真实经济：初始金币一分不多给，只在下一波需要时补塔，从不拆塔 */
function ensureTower(kind){
  for (var i in B.towers){ if (B.towers[i].kind === kind) return true; }
  if (B.gold < TD_TOWERS[kind].cost) return false;
  for (var s = 0; s < B.map.slots.length; s++){
    if (!B.towers[s]){
      B.sel = { type:'build', slot:s }; tdBuild(0, kind); B.sel = null;
      return true;
    }
  }
  return false;
}
function runEcon(thinkMs){
  var VT = 0, qStart = -1, frames = 0, minGold = 1e9, shortages = [];
  render(); openTd(); tdStart('u1-m1');
  B.loopId = -999; B.last = 0;
  for (frames = 0; frames < 120000; frames++){
    if (B.phase === 'build'){
      var w = B.map.waves[B.waveIdx];
      if (w){
        var need = [];
        w.kinds.forEach(function(k){ if (need.indexOf(k) < 0) need.push(k); });
        need.forEach(function(k){
          if (!ensureTower(k)) shortages.push('第' + (B.waveIdx + 1) + '波缺' + k + '(钱' + Math.floor(B.gold) + ')');
        });
      }
      tdNextWave();
    }
    VT += 16;
    if (B.quiz){
      if (qStart < 0) qStart = VT;
      if (VT - qStart >= thinkMs){ tdResolve(true); qStart = -1; }
    } else qStart = -1;
    tdFrame(VT);
    if (B.gold < minGold) minGold = B.gold;
    if (B.phase === 'win' || B.phase === 'lose') break;
  }
  return { mode: '按需建塔', think: thinkMs / 1000, phase: B.phase, lives: B.lives,
           escaped: B.map.lives - B.lives, towers: Object.keys(B.towers).length,
           goldLeft: Math.floor(B.gold), minGold: Math.floor(minGold),
           q: B.stats.q, ok: B.stats.ok, shortages: shortages };
}

var OUT = [];
try {
  [2000, 4000, 6000].forEach(function(t){ OUT.push(runPace(t)); });
  [3000, 5000].forEach(function(t){ OUT.push(runEcon(t)); });
} catch(e){
  OUT = [{ error: e.message }];
}
document.body.setAttribute('data-pace', JSON.stringify(OUT));
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

    tmp = tempfile.mkdtemp(prefix='td-pace-')
    test = os.path.join(tmp, 'p.html')
    io.open(test, 'w', encoding='utf-8').write(
        html[:m.start()] + RUNNER + '\n</script>' + html[m.end():])

    out = subprocess.run([
        pick_browser(), '--headless=new', '--disable-gpu', '--no-sandbox',
        '--virtual-time-budget=200000', '--window-size=800,900',
        '--user-data-dir=' + os.path.join(tmp, 'profile'),
        '--dump-dom', 'file:///' + test.replace(os.sep, '/'),
    ], capture_output=True, text=True, timeout=300).stdout

    hit = re.search(r'data-pace="([^"]*)"', out)
    if not hit:
        print('FAIL 没有回报结果')
        sys.exit(1)
    raw = hit.group(1).replace('&quot;', '"').replace('&amp;', '&')
    print(raw)
    if 'error' in raw:
        sys.exit(1)


if __name__ == '__main__':
    main()
