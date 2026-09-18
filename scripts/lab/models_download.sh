#!/usr/bin/env bash
# 实验室容器内下载 H3 权重（读 ../remote/models/h3/manifest.txt，sha256 校验、断点续传）。
#
# 默认引擎是 fetch_manifest.py（curl 分块并发 + pwrite），不是 aria2c：
# 同一个 modelscope URL 实测 aria2c 只有 5.3–6.0 MB/s、python-urllib 0.4–0.6 MB/s，
# 而 curl 单连接 22–39 MB/s、8 并发聚合 121 MB/s，20 GB 文件从 ETA 53 分钟降到约 2 分钟。
# ENGINE=aria2 可回退旧路径（AutoDL 侧就是它）。
#
# 用法：[SRC=modelscope|hfmirror|hf] [WORKERS=8] [ENGINE=python|aria2] bash models_download.sh [--verify-only]
set -euo pipefail
LAB=${LAB:-/home/devuser/workspace}
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export COMFY_HOME=${COMFY_HOME:-$LAB/ComfyUI}
export HF_ENDPOINT=${HF_ENDPOINT:-https://hf-mirror.com}
ENGINE=${ENGINE:-python}
SRC=${SRC:-modelscope}
WORKERS=${WORKERS:-8}
REPO=${REPO:-Comfy-Org/MiniMax-H3}
MANIFEST=${MANIFEST:-$HERE/../remote/models/h3/manifest.txt}
PY=${PY:-python3}
mkdir -p "$COMFY_HOME/models"

if [ "$ENGINE" = aria2 ]; then
  exec bash "$HERE/../remote/models/h3/download.sh" "$@"
fi

exec "$PY" "$HERE/fetch_manifest.py" --manifest "$MANIFEST" --dest-root "$COMFY_HOME/models" \
  --src "$SRC" --workers "$WORKERS" --repo "$REPO" "$@"
