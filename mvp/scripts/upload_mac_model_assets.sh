#!/usr/bin/env bash
# upload_mac_model_assets.sh — 把 mac CI 需要的三份模型资产挂到 rolling tag `model-assets`
#
# 为什么走 release 而不是 git：这三份里 ISC 外部权重 209MB，超 GitHub 单文件 100MB 硬限；
# 而"CI 现场导出"锁不住 sha256（export_patch_onnx.py 重导出的图文件只差元数据但字节不同，
# accept_packaged_bundle.py 与 Windows 包用同一份 asset.json 做硬比对 ⇒ 一改 sha 锁 Windows 验收就红）。
# 泄露面为零：这三份字节本就随 r9/r11 的 win 包与 mac-alpha 的 mac 包对外分发。
#
# 用法（在仓库根）:  bash mvp/scripts/upload_mac_model_assets.sh
# 依赖: curl；令牌从 git credential helper 取（不落盘、不打印）
set -euo pipefail

API="https://api.github.com"
UPLOADS="https://uploads.github.com"
OWNER_REPO="bsaizne/source-video-locator"
TAG="model-assets"
M="mvp/ui/resources/models"

FILES=(
  "$M/dinov2_cls_patch/dinov2_cls_patch.onnx.data"
  "$M/isc_ft_v107/isc_ft_v107.onnx"
  "$M/isc_ft_v107/isc_ft_v107.onnx.data"
)

# 令牌来源（按序尝试）：$SVL_GH_TOKEN → 缓存文件 $SVL_GH_TOKEN_FILE → git credential helper
# （helper 今天实测会偶发挂住 ⇒ 一律加 timeout，且优先用缓存）
TOK="${SVL_GH_TOKEN:-}"
if [ -z "$TOK" ] && [ -n "${SVL_GH_TOKEN_FILE:-}" ] && [ -f "$SVL_GH_TOKEN_FILE" ]; then
  TOK="$(sed -n 's/^password=//p' "$SVL_GH_TOKEN_FILE" | tr -d '\r')"
fi
if [ -z "$TOK" ]; then
  TOK="$(timeout 30 bash -c 'printf "protocol=https\nhost=github.com\n\n" | GIT_TERMINAL_PROMPT=0 git credential-manager get' | sed -n 's/^password=//p' | tr -d '\r')"
fi
if [ -z "$TOK" ]; then echo "拿不到 GitHub API 令牌（helper 可能挂住；设 SVL_GH_TOKEN 或 SVL_GH_TOKEN_FILE 再跑）"; exit 1; fi
AUTH="Authorization: Bearer $TOK"
ACC="Accept: application/vnd.github+json"

REL_ID="$(curl -s --max-time 60 -H "$AUTH" -H "$ACC" "$API/repos/$OWNER_REPO/releases/tags/$TAG" | node -e "
let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>{
  try{const j=JSON.parse(s);if(j.id)process.stdout.write(String(j.id));}catch(e){}});")"
if [ -z "$REL_ID" ]; then
  echo "release $TAG 不存在，创建中"
  printf '{"tag_name":"%s","prerelease":true,"name":"Model assets (CI download source)","body":"Internal: model assets downloaded and sha256-verified by CI mac packaging.","target_commitish":"master"}' "$TAG" > /tmp/svl_rel_body.json
  REL_ID="$(curl -s --max-time 60 -X POST -H "$AUTH" -H "$ACC" --data-binary @/tmp/svl_rel_body.json \
    "$API/repos/$OWNER_REPO/releases" | node -e "
let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>{
  try{const j=JSON.parse(s);if(j.id)process.stdout.write(String(j.id));else console.error('create failed:',j.message);}catch(e){console.error('bad json');}});")"
fi
[ -n "$REL_ID" ] || { echo "创建/查询 release 失败"; exit 1; }
echo "release id=$REL_ID"

for f in "${FILES[@]}"; do
  name="$(basename "$f")"
  [ -f "$f" ] || { echo "缺文件 $f"; exit 1; }
  size="$(wc -c < "$f" | tr -d ' ')"
  # 同名资产先删，避免重复（等价 gh release upload --clobber）
  AID="$(curl -s --max-time 60 -H "$AUTH" -H "$ACC" "$API/repos/$OWNER_REPO/releases/$REL_ID/assets" | node -e "
let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>{
  let arr=[];try{arr=JSON.parse(s);}catch(e){}
  const a=(Array.isArray(arr)?arr:[]).find(x=>x.name===process.argv[1]);
  if(a)process.stdout.write(String(a.id));});" "$name")"
  if [ -n "$AID" ]; then
    echo "  已存在 $name (id=$AID) → 先删"
    curl -s --max-time 60 -X DELETE -H "$AUTH" -H "$ACC" "$API/repos/$OWNER_REPO/releases/assets/$AID" -o /dev/null
  fi
  echo "  上传 $name ($size B)"
  code="$(curl -s --max-time 1800 -o /tmp/up.json -w "%{http_code}" -X POST -H "$AUTH" -H "$ACC" \
    -H "Content-Type: application/octet-stream" \
    --data-binary "@$f" \
    "$UPLOADS/repos/$OWNER_REPO/releases/$REL_ID/assets?name=$name")"
  echo "  HTTP=$code"
  case "$code" in 2*) ;; *) head -c 300 /tmp/up.json; echo; exit 1;; esac
done

echo "DONE. 校验清单:"
curl -s -H "$AUTH" -H "$ACC" "$API/repos/$OWNER_REPO/releases/tags/$TAG" | node -e "
let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>{
  const j=JSON.parse(s);
  for(const a of j.assets||[])console.log(' -',a.name,a.size,'B  dl=',a.browser_download_url);});"
