#!/usr/bin/env bash
# =============================================================
# 发布前自动安全检查（preflight）
#
# 用法：  bash scripts/preflight.sh
# 退出码：0 = 全部通过，可以发布；1 = 有阻断项，禁止发布
#
# CI 会在 .github/workflows/pages.yml 的 preflight job 中自动运行，
# 检查不通过时不会部署到 GitHub Pages。
# =============================================================
set -u

FAIL=0
WARN=0
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$1"; FAIL=$((FAIL+1)); }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; WARN=$((WARN+1)); }
sec()  { printf '\n\033[1m%s\033[0m\n' "$1"; }

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)" || exit 1

# 只检查被 git 追踪的文件（.gitignore 里排除的本地文件不会发布）
mapfile -t FILES < <(git ls-files)
if [ ${#FILES[@]} -eq 0 ]; then
  echo "没有任何被追踪的文件，先在仓库根目录执行本脚本"; exit 1
fi

scan() { # $1=正则 $2=说明 -> 输出命中行
  local pat="$1"
  grep -nIE -- "$pat" "${FILES[@]}" 2>/dev/null
}

# -------------------------------------------------------------
sec "1. 凭证与密钥"
SECRET_RE='(ghp_[A-Za-z0-9]{20,}|gh[ousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|eyJhbGciOi[A-Za-z0-9_-]{10,})'
out=$(scan "$SECRET_RE")
if [ -n "$out" ]; then bad "发现疑似密钥/令牌："; echo "$out" | sed 's/^/      /'
else ok "无硬编码密钥、令牌、私钥"; fi

out=$(scan '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
if [ -n "$out" ]; then
  real=$(echo "$out" | grep -v 'users\.noreply\.github\.com' | grep -v 'example\.com')
  if [ -n "$real" ]; then warn "发现邮箱地址（确认不是个人邮箱）："; echo "$real" | sed 's/^/      /'
  else ok "仅有 GitHub noreply 邮箱"; fi
else ok "无邮箱地址"; fi

out=$(scan '(^|[^0-9])1[3-9][0-9]{9}([^0-9]|$)')
if [ -n "$out" ]; then warn "发现疑似手机号（确认非真实号码）："; echo "$out" | sed 's/^/      /'
else ok "无手机号"; fi

# -------------------------------------------------------------
sec "2. 本机路径与隐私信息"
PATH_RE='([A-Za-z]:\\\\Users\\\\|[A-Za-z]:/Users/|/Users/[A-Za-z]|/home/[a-z]|E:/workbuddy|E:\\\\workbuddy|\.workbuddy/)'
out=$(scan "$PATH_RE")
if [ -n "$out" ]; then
  # 这几个文件里出现路径/ .workbuddy 字样属于规则说明与自检逻辑，不是真实本机路径
  real=$(echo "$out" | grep -vE '^(docs/DESIGN\.md|docs/PRE-RELEASE-CHECKLIST\.md|\.gitignore|scripts/preflight\.sh):')
  if [ -n "$real" ]; then bad "发现本机绝对路径（会暴露目录结构/用户名）："; echo "$real" | sed 's/^/      /'
  else ok "仅在忽略规则/自检脚本/文档说明中出现 .workbuddy，不涉及真实本机路径"; fi
else ok "无本机绝对路径"; fi

out=$(git ls-files | grep -E '(^|/)(\.env|\.env\..*|\.workbuddy|node_modules|\.git-credentials|id_rsa|.*\.pem|.*\.key|.*\.log)$')
if [ -n "$out" ]; then bad "这些文件不该进仓库："; echo "$out" | sed 's/^/      /'
else ok "无敏感文件被纳入版本库"; fi

# -------------------------------------------------------------
sec "3. 页面运行时安全（index.html）"
if [ -f index.html ]; then
  if grep -q 'http-equiv="Content-Security-Policy"' index.html; then
    ok "已声明 Content-Security-Policy"
  else bad "缺少 CSP，建议在 <head> 加 default-src 'none' 基线"; fi

  if grep -q 'name="referrer"' index.html; then ok "已设置 referrer 策略"
  else warn "建议加 <meta name=\"referrer\" content=\"no-referrer\">"; fi

  out=$(grep -nIE '(<script[^>]+src=|<link[^>]+href=[^>]*https?:|<iframe|src="https?:|@import)' index.html)
  if [ -n "$out" ]; then bad "index.html 引入外部资源（离线与隐私都会失效）："; echo "$out" | sed 's/^/      /'
  else ok "无外部脚本 / 样式 / iframe 引用"; fi

  out=$(grep -nIE '(fetch\(|XMLHttpRequest|new WebSocket|sendBeacon|navigator\.geolocation|document\.cookie)' index.html)
  if [ -n "$out" ]; then bad "index.html 存在网络请求或追踪类调用："; echo "$out" | sed 's/^/      /'
  else ok "无网络请求、无地理定位、无 cookie 写入"; fi

  out=$(grep -nIE 'eval\(|new Function\(|document\.write\(' index.html)
  if [ -n "$out" ]; then warn "存在动态执行（确认输入来源可信）："; echo "$out" | sed 's/^/      /'
  else ok "无 eval / new Function / document.write"; fi

  if grep -q 'getUserMedia\|SpeechRecognition' index.html; then
    if grep -q '关于麦克风' index.html; then ok "使用麦克风，且已有授权前说明文案"
    else bad "调用麦克风但缺少使用前的隐私说明"; fi
  fi

  out=$(grep -nIE 'https?://' index.html)
  if [ -n "$out" ]; then warn "index.html 出现网址（确认只是文案而非请求）："; echo "$out" | sed 's/^/      /'
  else ok "index.html 内无任何网址"; fi
else
  bad "缺少 index.html"
fi

# -------------------------------------------------------------
sec "4. 仓库卫生"
BIG=$(git ls-files -z | xargs -0 -I{} sh -c 'test -f "{}" && s=$(wc -c <"{}") && [ "$s" -gt 1048576 ] && echo "{} ($((s/1024)) KB)"')
if [ -n "$BIG" ]; then warn "存在大于 1MB 的文件："; echo "$BIG" | sed 's/^/      /'
else ok "无超大文件"; fi

for f in README.md LICENSE .gitignore .gitattributes docs/DESIGN.md; do
  if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then ok "已包含 $f"
  else warn "缺少 $f"; fi
done

AUTHOR=$(git log -1 --format='%ae' 2>/dev/null || true)
if [ -n "$AUTHOR" ]; then
  case "$AUTHOR" in
    *users.noreply.github.com) ok "提交邮箱为 GitHub noreply（不暴露真实邮箱）" ;;
    *) warn "提交邮箱为 $AUTHOR，公开仓库前建议改成 noreply 邮箱" ;;
  esac
fi

# -------------------------------------------------------------
echo
echo "-----------------------------------------------------------"
if [ "$FAIL" -gt 0 ]; then
  printf '\033[31m阻断项 %d 个，警告 %d 个 —— 不要发布\033[0m\n' "$FAIL" "$WARN"
  exit 1
fi
printf '\033[32m通过（警告 %d 个）—— 可以发布\033[0m\n' "$WARN"
