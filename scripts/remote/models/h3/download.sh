#!/usr/bin/env bash
# 在 AutoDL 实例上运行。按同目录 manifest.txt 从 ModelScope 镜像（或 hf-mirror）用 aria2 多线程续传下载 H3 权重到 ComfyUI/models/，
# 然后 sha256 校验。幂等：已校验通过的文件（有 .sha256.ok 标记）直接跳过。
# 用法：[SRC=modelscope|hfmirror|hf] [REPO=…] [MANIFEST=…] bash scripts/remote/models/h3/download.sh [--verify-only] 2>&1 | tee /root/autodl-tmp/logs/download_h3.log
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST=${MANIFEST:-$HERE/manifest.txt}
COMFY=${COMFY_HOME:-/root/autodl-tmp/ComfyUI}
REPO=${REPO:-Comfy-Org/MiniMax-H3}   # 可覆盖：REPO=<仓库> MANIFEST=<清单路径>
# 下载源：modelscope（实测 17MB/s+，sha256 与 HF 一致，默认）| hfmirror（1-3MB/s 不稳）| hf（需 source /etc/network_turbo）
SRC=${SRC:-modelscope}
case "$SRC" in
  modelscope) URL_BASE="https://www.modelscope.cn/models/$REPO/resolve/master" ;;
  hfmirror)   URL_BASE="https://hf-mirror.com/$REPO/resolve/main" ;;
  hf)         URL_BASE="https://huggingface.co/$REPO/resolve/main" ;;
  *) echo "unknown SRC=$SRC"; exit 2 ;;
esac
VERIFY_ONLY=0; [ "${1:-}" = "--verify-only" ] && VERIFY_ONLY=1
log() { printf "\033[35m[download_h3]\033[0m %s\n" "$*"; }

fail=0
while read -r sha size path; do
  [[ -z "$sha" || "$sha" == \#* ]] && continue
  dst="$COMFY/models/$path"; mkdir -p "$(dirname "$dst")"
  if [ -f "$dst.sha256.ok" ] && [ "$(cat "$dst.sha256.ok")" = "$sha" ]; then log "skip (verified) $path"; continue; fi
  if [ $VERIFY_ONLY -eq 0 ]; then
    log "download $path ($((size/1024/1024)) MB)"
    until aria2c -c -x 8 -s 8 -k 1M --file-allocation=none --max-tries=0 --retry-wait=5 \
          --connect-timeout=30 --timeout=60 --lowest-speed-limit=50K --auto-file-renaming=false \
          --console-log-level=warn --summary-interval=30 \
          -d "$(dirname "$dst")" -o "$(basename "$dst")" "$URL_BASE/$path"; do
      log "aria2 exited non-zero, retry in 10s: $path"; sleep 10
    done
  fi
  if [ ! -f "$dst" ]; then log "MISSING $path"; fail=1; continue; fi
  actual=$(stat -c %s "$dst")
  if [ "$actual" != "$size" ]; then log "SIZE MISMATCH $path: $actual != $size"; fail=1; continue; fi
  log "sha256 $path ..."
  got=$(sha256sum "$dst" | cut -d' ' -f1)
  if [ "$got" = "$sha" ]; then echo "$sha" > "$dst.sha256.ok"; log "OK $path"
  else log "SHA MISMATCH $path (got $got); 删除后重跑本脚本可续传"; rm -f "$dst.sha256.ok"; fail=1; fi
done < "$MANIFEST"

log "models 目录占用："; du -sh "$COMFY/models"/{diffusion_models,text_encoders,vae,loras,embeddings} 2>/dev/null
[ $fail -eq 0 ] && log "全部通过" || { log "有失败项，见上文"; exit 1; }
