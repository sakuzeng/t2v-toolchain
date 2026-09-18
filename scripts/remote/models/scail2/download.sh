#!/usr/bin/env bash
# 在 AutoDL 实例上运行。按同目录 manifest.txt（多仓库，五列）从 ModelScope 镜像用 aria2 续传下载 SCAIL-2 角色替换所需权重到 ComfyUI/models/，
# 然后 sha256 校验。幂等：已校验通过的文件（有 .sha256.ok 标记）直接跳过。与 H3 下载脚本同一套逻辑，只是每行自带仓库与落地路径。
# 用法：[SRC=modelscope|hfmirror|hf] [MANIFEST=…] bash scripts/remote/models/scail2/download.sh [--verify-only] 2>&1 | tee -a /root/autodl-tmp/logs/download_scail2.log
# 建议在 tmux 窗口里跑（tmux new-window -t h3 -n dl），不要用 pkill -f 结束（PITFALLS #2）。
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST=${MANIFEST:-$HERE/manifest.txt}
COMFY=${COMFY_HOME:-/root/autodl-tmp/ComfyUI}
SRC=${SRC:-modelscope}
VERIFY_ONLY=0; [ "${1:-}" = "--verify-only" ] && VERIFY_ONLY=1
log() { printf "\033[36m[download_scail2]\033[0m %s %s\n" "$(date +%H:%M:%S)" "$*"; }
url_for() {  # $1=repo $2=remote_path
  case "$SRC" in
    modelscope) echo "https://www.modelscope.cn/models/$1/resolve/master/$2" ;;
    hfmirror)   echo "https://hf-mirror.com/$1/resolve/main/$2" ;;
    hf)         echo "https://huggingface.co/$1/resolve/main/$2" ;;
    *) echo "unknown SRC=$SRC" >&2; exit 2 ;;
  esac
}
command -v aria2c >/dev/null || { log "需要 aria2c：apt-get install -y aria2"; exit 2; }

need=0
while read -r sha size repo rpath lpath; do
  [[ -z "$sha" || "$sha" == \#* ]] && continue
  dst="$COMFY/models/$lpath"
  if ! { [ -f "$dst.sha256.ok" ] && [ "$(cat "$dst.sha256.ok")" = "$sha" ]; }; then
    have=0; [ -f "$dst" ] && have=$(stat -c %s "$dst"); need=$((need + size - have))
  fi
done < "$MANIFEST"
avail=$(df -B1 --output=avail "$COMFY" | tail -1)
log "还需下载约 $((need/1024/1024/1024)) GB；数据盘可用 $((avail/1024/1024/1024)) GB"
if [ $VERIFY_ONLY -eq 0 ] && [ "$avail" -lt $((need + 8*1024*1024*1024)) ]; then
  log "可用空间不足（要求余量 ≥ 需求 + 8 GB），停止"; exit 3
fi

fail=0
while read -r sha size repo rpath lpath; do
  [[ -z "$sha" || "$sha" == \#* ]] && continue
  dst="$COMFY/models/$lpath"; mkdir -p "$(dirname "$dst")"
  if [ -f "$dst.sha256.ok" ] && [ "$(cat "$dst.sha256.ok")" = "$sha" ]; then log "skip (verified) $lpath"; continue; fi
  if [ $VERIFY_ONLY -eq 0 ]; then
    log "download $lpath ($((size/1024/1024)) MB) from $repo"
    until aria2c -c -x 8 -s 8 -k 1M --file-allocation=none --max-tries=0 --retry-wait=5 \
          --connect-timeout=30 --timeout=60 --lowest-speed-limit=50K --auto-file-renaming=false \
          --console-log-level=warn --summary-interval=60 \
          -d "$(dirname "$dst")" -o "$(basename "$dst")" "$(url_for "$repo" "$rpath")"; do
      log "aria2 exited non-zero, retry in 10s: $lpath"; sleep 10
    done
  fi
  if [ ! -f "$dst" ]; then log "MISSING $lpath"; fail=1; continue; fi
  actual=$(stat -c %s "$dst")
  if [ "$actual" != "$size" ]; then log "SIZE MISMATCH $lpath: $actual != $size"; fail=1; continue; fi
  log "sha256 $lpath ..."
  got=$(sha256sum "$dst" | cut -d' ' -f1)
  if [ "$got" = "$sha" ]; then echo "$sha" > "$dst.sha256.ok"; log "OK $lpath"
  else log "SHA MISMATCH $lpath (got $got); 删除后重跑本脚本可续传"; rm -f "$dst.sha256.ok"; fail=1; fi
done < "$MANIFEST"

log "models 目录占用："; du -sh "$COMFY/models"/{diffusion_models,text_encoders,vae,loras,clip_vision,checkpoints} 2>/dev/null
df -h "$COMFY" | tail -1
[ $fail -eq 0 ] && log "全部通过" || { log "有失败项，见上文"; exit 1; }
