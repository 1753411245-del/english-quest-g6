#!/usr/bin/env python3
"""拼写题的「删改」回归测试。

孩子点错第一个字母时必须能改回来。这个脚本盯死三条路径：

  闯关模式
    · 再点一次已用字母块 → 撤销
    · 点填字框里的字母   → 删掉那一个
    · 「⌫ 删一个」按钮   → 删最后一个
    · 填满不自动判题     → 必须手动点「检查」

  塔防模式
    · 点已填格子 / 已用字母块 / 删一个按钮，都能撤
    · 填满不自动判题，要手动「提交」

用法：
    python scripts/test-spell-edit.py
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
var LOG = [];
function ck(name, cond, extra){
  if (!cond) LOG.push(name + (extra ? ' <' + extra + '>' : ''));
}
function wrongIdx(q){
  for (var i = 0; i < q.letters.length; i++){
    if (q.letters[i].toLowerCase() !== q.answer.charAt(0).toLowerCase()) return i;
  }
  return -1;
}
function spellRight(q){
  var used = [];
  q.answer.split('').forEach(function(ch){
    for (var i = 0; i < q.letters.length; i++){
      if (used.indexOf(i) < 0 && q.letters[i].toLowerCase() === ch.toLowerCase()){
        used.push(i); pickLetter(i); break;
      }
    }
  });
}

/* ---------- 闯关 ---------- */
function testGame(){
  G = null;
  startLevel('st', 1);                       // 第 1 关＝拼写关
  var q = G.qs[G.i];
  ck('game.type', q.type === 'spell', q.type);
  var wi = wrongIdx(q);
  ck('game.hasWrong', wi >= 0);
  if (wi < 0) return;

  // 点错第一个字母
  pickLetter(wi);
  ck('game.picked1', G.spellPicked.length === 1, 'len=' + G.spellPicked.length);

  // 再点同一个字母块＝撤销
  pickLetter(wi);
  ck('game.undoByBlock', G.spellPicked.length === 0, 'len=' + G.spellPicked.length);

  // 点错的，再点填字框里的那个字母
  pickLetter(wi);
  ck('game.picked2', G.spellPicked.length === 1);
  var box = document.querySelector('#spellline .sltr');
  ck('game.boxExists', !!box);
  if (box) unpickLetter(0);
  ck('game.undoByBox', G.spellPicked.length === 0, 'len=' + G.spellPicked.length);

  // 点错的，用按钮删
  pickLetter(wi);
  var back = document.getElementById('spBack');
  ck('game.backBtn', !!back);
  if (back) spellBack();
  ck('game.undoByBtn', G.spellPicked.length === 0, 'len=' + G.spellPicked.length);

  // 空的时候按钮应该是禁用的
  ck('game.backDisabledEmpty', back && back.disabled === true);

  // 拼满：不自动判题，检查按钮启用
  spellRight(q);
  ck('game.fullNotAuto', G.answered === false, 'answered=' + G.answered);
  var chk = document.getElementById('spCheck');
  ck('game.checkEnabled', chk && chk.disabled === false);
  ck('game.fullLen', G.spellPicked.length === q.answer.length);

  // 填满后不再往下塞（题库里有干扰字母块时才测得到）
  var spare = -1;
  for (var i2 = 0; i2 < q.letters.length; i2++){
    if (G.spellPicked.indexOf(i2) < 0){ spare = i2; break; }
  }
  if (spare >= 0){
    pickLetter(spare);
    ck('game.noOverflow', G.spellPicked.length === q.answer.length, 'len=' + G.spellPicked.length);
  }

  // 满了还能改：删一个再补回去
  spellBack();
  ck('game.stillEditable', G.answered === false && G.spellPicked.length === q.answer.length - 1,
     'len=' + G.spellPicked.length);

  // 补回最后一个字母后手动检查
  var last = q.answer.charAt(q.answer.length - 1);
  for (var i = 0; i < q.letters.length; i++){
    if (G.spellPicked.indexOf(i) < 0 && q.letters[i].toLowerCase() === last.toLowerCase()){
      pickLetter(i); break;
    }
  }
  ck('game.reFilled', G.spellPicked.length === q.answer.length, 'len=' + G.spellPicked.length);
  checkSpell();
  ck('game.correct', G.answered === true && G.correct === 1,
     'answered=' + G.answered + ' correct=' + G.correct);
}

/* ---------- 塔防 ---------- */
function testTd(){
  render(); openTd(); tdStart('u1-m1');
  B.loopId = -999;
  var u = BOOK.units[0];
  var q = makeSpell(u, u.words[0]);
  B.phase = 'fight';
  B.quiz = q; B.spell = []; B.answered = false;
  B.quizE = { id: 'test', pos: 0.4, hp: 2, tried: {}, badge: tdBadge(q) };
  B.quizSlot = 0;
  tdPanel();

  var wi = wrongIdx(q);
  ck('td.panelRendered', !!document.getElementById('tdLine'));

  tdPickLtr(wi);
  ck('td.picked1', B.spell.length === 1, 'len=' + B.spell.length);

  // 再点已用字母块＝撤销
  tdPickLtr(wi);
  ck('td.undoByBlock', B.spell.length === 0, 'len=' + B.spell.length);

  // 点错的，再点已填格子
  tdPickLtr(wi);
  var cell = document.querySelector('#tdLine .sl.full');
  ck('td.cellClickable', !!cell && !!cell.getAttribute('onclick'));
  if (cell) tdUnpickLtr(0);
  ck('td.undoByCell', B.spell.length === 0, 'len=' + B.spell.length);

  // 点错的，用按钮删
  tdPickLtr(wi);
  var back = document.getElementById('tdBack');
  ck('td.backBtn', !!back && back.disabled === false);
  if (back) tdBackLtr();
  ck('td.undoByBtn', B.spell.length === 0, 'len=' + B.spell.length);

  // 拼满：不自动判题，提交按钮启用
  var used = [];
  q.answer.split('').forEach(function(ch){
    for (var i = 0; i < q.letters.length; i++){
      if (used.indexOf(i) < 0 && q.letters[i].toLowerCase() === ch.toLowerCase()){
        used.push(i); tdPickLtr(i); break;
      }
    }
  });
  ck('td.fullNotAuto', B.answered === false, 'answered=' + B.answered);
  var sub = document.getElementById('tdSubmit');
  ck('td.submitEnabled', sub && sub.disabled === false);
  ck('td.fullLen', B.spell.length === q.answer.length);

  // 满了还能删
  tdBackLtr();
  ck('td.stillEditable', B.answered === false && B.spell.length === q.answer.length - 1,
     'len=' + B.spell.length);

  // 补回最后一个字母再提交
  var last = q.answer.charAt(q.answer.length - 1);
  for (var j = 0; j < q.letters.length; j++){
    if (B.spell.indexOf(j) < 0 && q.letters[j].toLowerCase() === last.toLowerCase()){
      tdPickLtr(j); break;
    }
  }
  ck('td.reFilled', B.spell.length === q.answer.length, 'len=' + B.spell.length);
  try { tdSubmitSpell(); } catch(e){ LOG.push('td.submitThrow ' + e.message); }
  ck('td.submitted', B.answered === true, 'answered=' + B.answered);
}

try {
  testGame();
  testTd();
} catch(e){
  LOG.push('EXCEPTION ' + e.message);
}
document.body.setAttribute('data-spell', JSON.stringify({ fail: LOG }));
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

    tmp = tempfile.mkdtemp(prefix='spell-edit-')
    test = os.path.join(tmp, 's.html')
    io.open(test, 'w', encoding='utf-8').write(
        html[:m.start()] + RUNNER + '\n</script>' + html[m.end():])

    out = subprocess.run([
        pick_browser(), '--headless=new', '--disable-gpu', '--no-sandbox',
        '--virtual-time-budget=40000', '--window-size=800,900',
        '--user-data-dir=' + os.path.join(tmp, 'profile'),
        '--dump-dom', 'file:///' + test.replace(os.sep, '/'),
    ], capture_output=True, text=True, timeout=180).stdout

    hit = re.search(r'data-spell="([^"]*)"', out)
    if not hit:
        print('FAIL 没有回报结果')
        sys.exit(1)
    raw = hit.group(1).replace('&quot;', '"').replace('&amp;', '&')
    print('结果:', raw)
    fails = re.search(r'"fail":\[(.*?)\]', raw)
    if fails and fails.group(1).strip():
        print('FAIL 以下断言没过：')
        for f in fails.group(1).split(','):
            print('  ·', f.strip().strip('"'))
        sys.exit(1)
    print('PASS 拼写题点错后都能删改（闯关 + 塔防）')


if __name__ == '__main__':
    main()
