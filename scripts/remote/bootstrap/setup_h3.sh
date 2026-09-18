#!/usr/bin/env bash
# 在 AutoDL 实例上运行（root）。幂等，可重复执行。
# 建 MiniMax H3 + ComfyUI + Blender(headless) 环境，全部落数据盘 /root/autodl-tmp。
# 前提：已跑过 autodl 套件的 bootstrap.sh（conda 目录已指向数据盘）。
# 用法：bash setup_h3.sh 2>&1 | tee /root/autodl-tmp/logs/setup_h3.log
set -euo pipefail

DATA=/root/autodl-tmp
ENV_DIR=$DATA/conda/envs/h3
COMFY=$DATA/ComfyUI
COMFY_TAG=${COMFY_TAG:-v0.34.5}          # ≥ v0.30.0 才有 H3 原生节点
BLENDER_VER=${BLENDER_VER:-4.5.13}       # 4.5 LTS
BLENDER_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/blender/release/Blender4.5
export HF_HOME=$DATA/hf_cache HF_ENDPOINT=https://hf-mirror.com HF_HUB_DISABLE_XET=1
export PIP_INDEX_URL=${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}
log() { printf "\033[36m[setup_h3]\033[0m %s\n" "$*"; }
# GitHub 直连常在 clone 中途 TLS 断掉；失败则在子 shell 里开学术加速重试（代理不外泄，pip 仍走 tuna）
gclone() {  # gclone <url> <dest> [branch]
  local url=$1 dest=$2 br=${3:-}; local args=(-q --depth=1); [ -n "$br" ] && args+=(--branch "$br")
  rm -rf "$dest"
  git clone "${args[@]}" "$url" "$dest" 2>/dev/null && return 0
  log "直连 GitHub 失败，改走学术加速重试：$url"
  rm -rf "$dest"
  ( source /etc/network_turbo >/dev/null 2>&1; git clone "${args[@]}" "$url" "$dest" )
}
mkdir -p $DATA/logs $DATA/blender $DATA/work $DATA/outputs

# ---- 0. apt：aria2 下载器、ffmpeg、Blender headless 运行库 ----
log "apt: aria2 ffmpeg + blender runtime libs"
apt-get update -qq >/dev/null 2>&1 || true
apt-get install -y -qq aria2 ffmpeg fonts-noto-cjk libxi6 libxrender1 libxkbcommon0 libsm6 libice6 libgl1 libglu1-mesa \
  libxxf86vm1 libxfixes3 libegl1 libxcursor1 libxinerama1 libxrandr2 libgomp1 >/dev/null 2>&1 || log "apt 部分失败，继续"

# ---- 1. conda env h3：从 base 克隆，保住镜像里为卡配好的 torch ----
source /root/miniconda3/etc/profile.d/conda.sh
if [ ! -x "$ENV_DIR/bin/python" ]; then
  log "conda create h3 (clone base) -> $ENV_DIR"
  conda create -y -p "$ENV_DIR" --clone base >/dev/null
fi
conda activate "$ENV_DIR"
python -c "import torch,sys;print('python',sys.version.split()[0],'torch',torch.__version__,'cuda',torch.version.cuda)"

# ---- 2. 护栏：钉死 torch 三件套，装任何东西都带 -c ----
# 注意：镜像里 torch 是按 URL 装的，pip freeze 会打成 "torch @ https://..."，用 pip list --format=freeze 才是 "torch==2.8.0+cu128"
CONS=$DATA/constraints.h3.txt
pip list --format=freeze 2>/dev/null | grep -E '^(torch|torchvision|torchaudio)==' > "$CONS" || true
grep -q '^torch==' "$CONS" || { echo "未找到 torch，终止"; exit 1; }
# 镜像未装 torchaudio（ComfyUI 需要）：钉到与 torch 相同的三段版本号，避免 pip 顺手换 torch
grep -q '^torchaudio==' "$CONS" || echo "torchaudio==$(grep '^torch==' "$CONS" | sed -E 's/^torch==([0-9]+\.[0-9]+\.[0-9]+).*/\1/')" >> "$CONS"
log "constraints: $(tr '\n' ' ' < "$CONS")"

# ---- 3. ComfyUI ----
if [ ! -d "$COMFY/.git" ]; then
  log "git clone ComfyUI $COMFY_TAG"
  # download_h3.sh 可能已先建好 $COMFY/models/…（非空目录 clone 会拒绝），故先 clone 到临时目录再合并
  tmp=$(mktemp -d "$DATA/comfy-clone.XXXX")
  gclone https://github.com/comfyanonymous/ComfyUI.git "$tmp" "$COMFY_TAG"
  mkdir -p "$COMFY" && cp -a "$tmp/." "$COMFY/" && rm -rf "$tmp"
else
  log "ComfyUI 已存在（$(git -C $COMFY describe --tags --always)），跳过 clone"
fi
log "pip install ComfyUI requirements（带护栏）"
pip install -q -c "$CONS" -r "$COMFY/requirements.txt"

# ---- 4. 自定义节点（不装 ComfyUI-MiniMaxH3-Cache：会破坏生成）----
declare -A NODES=(
  [ComfyUI-Manager]=https://github.com/Comfy-Org/ComfyUI-Manager.git
  [ComfyUI-VideoHelperSuite]=https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git
  [ComfyUI-KJNodes]=https://github.com/kijai/ComfyUI-KJNodes.git
  [rgthree-comfy]=https://github.com/rgthree/rgthree-comfy.git
  [ComfyUI-Crystools]=https://github.com/crystian/ComfyUI-Crystools.git
)
for n in "${!NODES[@]}"; do
  d="$COMFY/custom_nodes/$n"
  [ -d "$d/.git" ] || { log "clone $n"; gclone "${NODES[$n]}" "$d"; }
  [ -f "$d/requirements.txt" ] && pip install -q -c "$CONS" -r "$d/requirements.txt"
done

# ---- 5. 下载/校验工具 ----
pip install -q -c "$CONS" "huggingface_hub[cli]" modelscope

# ---- 6. Blender headless ----
BL_DIR=$DATA/blender/blender-$BLENDER_VER-linux-x64
if [ ! -x "$BL_DIR/blender" ]; then
  log "download Blender $BLENDER_VER (tuna)"
  aria2c -q -c -x 8 -s 8 -d $DATA/blender -o "blender-$BLENDER_VER-linux-x64.tar.xz" \
    "$BLENDER_MIRROR/blender-$BLENDER_VER-linux-x64.tar.xz"
  tar -xJf "$DATA/blender/blender-$BLENDER_VER-linux-x64.tar.xz" -C $DATA/blender
  rm -f "$DATA/blender/blender-$BLENDER_VER-linux-x64.tar.xz"
fi
ln -sfn "$BL_DIR" $DATA/blender/current
"$BL_DIR/blender" -b --version | head -1

# ---- 7. 项目私有 shell 配置（不动套件的 .zshrc）----
cat > /root/.zshrc.local <<'ZRC'
# text2video 远端 H3 链路
export HF_HUB_DISABLE_XET=1
export COMFY_HOME=/root/autodl-tmp/ComfyUI
export PATH=/root/autodl-tmp/blender/current:$PATH
conda activate /root/autodl-tmp/conda/envs/h3
alias comfy='cd $COMFY_HOME && python main.py --listen 127.0.0.1 --port 8188'
alias comfy-cpu='cd $COMFY_HOME && python main.py --cpu --listen 127.0.0.1 --port 8188'
ZRC

# ---- 8. 自检 + 落锁 ----
python - <<'PY'
import torch, importlib
print("torch", torch.__version__, "cuda avail", torch.cuda.is_available())
for m in ["safetensors","av","kornia","comfyui_frontend_package"]:
    try: importlib.import_module(m); print("ok", m)
    except Exception as e: print("MISSING", m, e)
PY
pip freeze > "$DATA/requirements.lock.h3.$(date +%Y%m%d).txt"
log "完成。df:"; df -h / $DATA | tail -2
