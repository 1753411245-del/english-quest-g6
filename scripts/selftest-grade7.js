/* 题库与关卡生成自检（不依赖浏览器） */
const fs = require('fs');
const path = require('path');

const file = path.join(__dirname, '..', 'grade7.html');
const html = fs.readFileSync(file, 'utf8');
let code = html.match(/<script>([\s\S]*)<\/script>/)[1];
code = code.replace(/\nrender\(\);\s*$/, '\n');

const noop = () => {};
const el = () => ({
  innerHTML: '', style: {}, textContent: '',
  classList: { add: noop, remove: noop, toggle: noop, contains: () => false },
  appendChild: noop, removeChild: noop, offsetWidth: 0,
  setAttribute: noop, getAttribute: () => null,
});
const document = {
  getElementById: el, createElement: el,
  body: { appendChild: noop, removeChild: noop },
  addEventListener: noop, querySelector: () => null, querySelectorAll: () => [],
};
const window = {
  speechSynthesis: { getVoices: () => [], speak: noop, cancel: noop },
  scrollTo: noop, addEventListener: noop,
};
const localStorage = { getItem: () => null, setItem: noop, removeItem: noop };

const factory = new Function(
  'window', 'document', 'localStorage',
  code + '\nreturn { BOOK, LEVEL_DEFS, NLV, BOSS, MAX_STAR, buildWordLevel, buildSpellLevel,' +
  ' buildListenLevel, buildSentenceLevel, buildGrammarLevel, buildSpeakLevel, buildBoss, artSVG };'
);
const M = factory(window, document, localStorage);

let errs = 0, warns = 0;
const bad = (m) => { console.log('  ✗ ' + m); errs++; };
const warn = (m) => { console.log('  ! ' + m); warns++; };

console.log('关卡数 NLV =', M.NLV, '| Boss 下标 =', M.BOSS, '| 单元满星 =', M.MAX_STAR);
console.log('单元数 =', M.BOOK.units.length);
console.log('');

const builders = [
  ['单词关', M.buildWordLevel, 8],
  ['拼写关', M.buildSpellLevel, 8],
  ['听力关', M.buildListenLevel, 6],
  ['句型关', M.buildSentenceLevel, 6],
  ['语法关', M.buildGrammarLevel, 6],
  ['跟读关', M.buildSpeakLevel, 4],
  ['Boss 关', M.buildBoss, 12],
];

M.BOOK.units.forEach((u) => {
  console.log('【' + u.no + ' ' + u.title + '】');
  if (u.words.length < 12) warn('词汇仅 ' + u.words.length + ' 个，建议 ≥12');
  if (u.sentences.length < 8) warn('句子仅 ' + u.sentences.length + ' 句，建议 ≥8');
  if (u.grammar.length < 6) warn('语法题仅 ' + u.grammar.length + ' 道，建议 ≥6');

  // 重复词检查
  const seen = new Set();
  u.words.forEach((w) => {
    if (seen.has(w[0])) bad(u.id + ' 词汇重复：' + w[0]);
    seen.add(w[0]);
  });

  // 语法题静态校验
  u.grammar.forEach((g, i) => {
    if (g.length !== 5) bad(u.id + ' 语法题 #' + i + ' 字段数不是 5');
    const [q, ans, dis, point, exp] = g;
    if (!q || !ans || !point || !exp) bad(u.id + ' 语法题 #' + i + ' 有空字段');
    if (!/___/.test(q)) warn(u.id + ' 语法题 #' + i + ' 题干没有空格「___」');
    if (!Array.isArray(dis) || dis.length !== 3) bad(u.id + ' 语法题 #' + i + ' 干扰项不是 3 个');
    if (dis.indexOf(ans) >= 0) bad(u.id + ' 语法题 #' + i + ' 干扰项里含正确答案');
    if (new Set([ans].concat(dis)).size !== 4) bad(u.id + ' 语法题 #' + i + ' 选项有重复');
  });

  // 动态生成校验（跑 3 轮，覆盖随机性）
  builders.forEach(([name, fn, want]) => {
    for (let round = 0; round < 3; round++) {
      const qs = fn(u);
      if (qs.length !== want) bad(u.id + ' ' + name + ' 题数 ' + qs.length + '，应为 ' + want);
      qs.forEach((q) => {
        const tag = u.id + ' ' + name;
        if (q.type === 'choice' || q.type === 'listen' || q.type === 'grammar') {
          if (!q.options || q.options.length !== 4) bad(tag + ' 选项数不是 4');
          else {
            if (new Set(q.options).size !== 4) bad(tag + ' 选项重复：' + q.options.join(' / '));
            if (q.options.indexOf(q.answer) < 0) bad(tag + ' 答案不在选项中：' + q.answer);
          }
        }
        if (q.type === 'grammar') {
          if (!q.point || !q.explain) bad(tag + ' 缺语法点或解析');
        }
        if (q.type === 'spell') {
          const need = {};
          q.answer.split('').forEach((c) => { need[c.toLowerCase()] = (need[c.toLowerCase()] || 0) + 1; });
          const have = {};
          q.letters.forEach((c) => { have[c.toLowerCase()] = (have[c.toLowerCase()] || 0) + 1; });
          for (const c in need) {
            if ((have[c] || 0) < need[c]) bad(tag + ' 字母块缺少「' + c + '」，拼不出 ' + q.answer);
          }
          if (q.letters.length !== q.answer.length + 2) bad(tag + ' 字母块数异常：' + q.letters.length);
        }
        if (q.type === 'order') {
          /* answer 统一转小写，tokens 保留原大小写，比较时两边都降为小写 */
          const a = q.tokens.map((t) => t.toLowerCase()).sort().join(' ');
          const b = q.answer.split(' ').map((t) => t.toLowerCase()).sort().join(' ');
          if (a !== b) bad(tag + ' 乱序块的词集与答案不一致');
          const joined = q.tokens.join(' ').toLowerCase();
          if (joined.length !== q.answer.length) bad(tag + ' 乱序块长度与答案不一致');
        }
        if (q.type === 'choice' && q.qtype === 'fill') {
          if (q.prompt.indexOf('___') < 0) bad(tag + ' 填空题没有空格');
        }
      });
    }
  });

  // 插画校验
  const svg = M.artSVG(u.id);
  if (!svg || svg.indexOf('<svg') !== 0) bad(u.id + ' 插画不是有效 SVG');
  if (svg.indexOf('</svg>') < 0) bad(u.id + ' 插画缺少闭合标签');
  const openTags = (svg.match(/<(?!\/)[a-zA-Z]/g) || []).length;
  const closeTags = (svg.match(/<\//g) || []).length + (svg.match(/\/>/g) || []).length;
  if (openTags !== closeTags) bad(u.id + ' 插画标签不配对（开 ' + openTags + ' / 闭 ' + closeTags + '）');
  console.log('  · 词 ' + u.words.length + ' / 句 ' + u.sentences.length + ' / 语法 ' + u.grammar.length + ' / 插画 ' + svg.length + 'B');
});

// 确定 id 之外不串图
const ids = M.BOOK.units.map((u) => u.id);
const arts = ids.map((id) => M.artSVG(id));
if (new Set(arts).size !== arts.length) bad('有多张插画内容重复');
console.log('');
console.log(errs === 0 ? '✅ 全部检查通过' + (warns ? '（' + warns + ' 条提示）' : '') : '❌ ' + errs + ' 个错误，' + warns + ' 条提示');
process.exit(errs ? 1 : 0);
