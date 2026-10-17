#!/usr/bin/env python3
"""塔防界面截图：战斗态、塔面板、布防态。输出到 .shots/"""
import io, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'grade7.html')
SHOTS = os.path.join(ROOT, '.shots')

BROWSERS = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
]

SETUP = r'''
  render(); openTd(); tdStart('u1-m1');
  B.loopId = -999; B.gold = 9999;
  [[0,'word'],[2,'spell'],[5,'listen'],[6,'grammar']].forEach(function(c){
    B.sel = { type:'build', slot:c[0] }; tdBuild(0, c[1]);
  });
  B.sel = null;
'''

CASES = {
    # 战斗中：四座塔、三只怪在射程内、一道题正等着答
    'v_tdfight': SETUP + r'''
  B.phase = 'fight';
  tdSpawn({ kind:'word', hp:1 });    B.enemies[0].pos = 0.055;
  tdSpawn({ kind:'spell', hp:1 });   B.enemies[1].pos = 0.30;
  tdSpawn({ kind:'listen', hp:1 });  B.enemies[2].pos = 0.46;
  B.last = 0;
  tdAsk(B.enemies[0], 0);
  tdPaint(); tdHudSync();
''',
    # 点开一座塔：射程圈 + 升级 / 拆掉
    'v_tdtower': SETUP + r'''
  B.phase = 'fight';
  tdSpawn({ kind:'word', hp:1 }); B.enemies[0].pos = 0.16;
  B.last = 0;
  B.towers[2].lv = 2;
  B.sel = { type:'tower', slot:2 };
  tdPanel(); tdPaint(); tdHudSync();
''',
    # 布防：9 个空位
    'v_tdbuild': r'''
  render(); openTd(); tdStart('u1-m1');
  B.loopId = -999;
  tdPanel(); tdPaint(); tdHudSync();
''',
}


def pick_browser():
    for p in BROWSERS:
        if os.path.exists(p):
            return p
    sys.exit(2)


def main():
    html = io.open(SRC, encoding='utf-8').read()
    m = re.search(r'render\(\);\s*</script>', html)
    if not m:
        print('注入点未找到'); sys.exit(2)
    os.makedirs(SHOTS, exist_ok=True)

    tmp = tempfile.mkdtemp(prefix='td-shot-')
    for name, js in CASES.items():
        path = os.path.join(SHOTS, name + '.html')
        io.open(path, 'w', encoding='utf-8').write(
            html[:m.start()] + js + '\n</script>' + html[m.end():])
        png = os.path.join(SHOTS, name + '.png')
        subprocess.run([
            pick_browser(), '--headless=new', '--disable-gpu', '--hide-scrollbars',
            '--no-sandbox', '--virtual-time-budget=150',
            '--window-size=800,1250', '--screenshot=' + png,
            '--user-data-dir=' + os.path.join(tmp, 'profile'),
            'file:///' + path.replace(os.sep, '/'),
        ], capture_output=True, timeout=120)
        print('ok ' + png)


if __name__ == '__main__':
    main()
