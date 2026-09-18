#!/usr/bin/env bash
# 在实验室服务器 lab-host（实验室，2×RTX A6000）的 agent Docker 容器内运行，用户 devuser（sudo NOPASSWD）。
# 幂等，可重复执行。用法：bash scripts/lab/bootstrap/setup_h3.sh 2>&1 | tee ~/workspace/logs/setup_h3_lab.log
#
# 与 AutoDL 版 scripts/remote/bootstrap/setup_h3.sh 的差异（原因见 docs/ops/PITFALLS.md）：
#   1. 无 conda，改用 python3 venv（落 .virtualenvs，随 bind mount 持久化）；不 clone base 镜像 torch。
#   2. 宿主驱动 535.54 / CUDA 12.2 → 用 cu126 系 torch（PyPI 上 torch 2.7.x 的 linux 默认 wheel 即 cu126），
#      靠 CUDA 12.x minor version compatibility 跑；**不能用更老的 2.6**：ComfyUI v0.34.5 的 comfy-kitchen
#      在 import 期调用 torch.library.infer_schema，参数用了 PEP 585 的 list[int]，2.6 只认 typing.List[int]。
#   3. 容器内 GitHub 直连不通（curl 000），全部走 GH_PROXY 前缀；无 /etc/network_turbo。
#   4. 不用 Blender（2026-09-16 已从项目取消 previz）。
#   5. 代码与 ComfyUI 都放 ~/workspace（= /Data/<user>/agent/workspace，唯一持久化的项目卷）。
set -euo pipefail

LAB=${LAB:-/home/devuser/workspace}
VENV=${VENV:-/home/devuser/.virtualenvs/h3}
COMFY=${COMFY:-$LAB/ComfyUI}
COMFY_TAG=${COMFY_TAG:-v0.34.5}                 # ≥ v0.30.0 才有 H3 原生节点
GH_PROXY=${GH_PROXY:-https://ghfast.top}        # 备用：https://gh-proxy.com / https://ghproxy.net
TORCH_VER=${TORCH_VER:-2.7.1}                   # ≥ 2.7 是 comfy-kitchen 的硬要求
TORCHVISION_VER=${TORCHVISION_VER:-0.22.1}
TORCHAUDIO_VER=${TORCHAUDIO_VER:-2.7.1}
CONS=$LAB/constraints.h3.txt
export HF_ENDPOINT=${HF_ENDPOINT:-https://hf-mirror.com}
export HF_HOME=${HF_HOME:-$LAB/hf_cache}
export HF_HUB_DISABLE_XET=1
export PIP_INDEX_URL=${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}

log() { printf "\033[36m[setup_h3_lab]\033[0m %s\n" "$*"; }
gurl() { printf '%s/%s\n' "$GH_PROXY" "$1"; }   # https://github.com/… → 代理前缀形式
gclone() {  # gclone <github-url> <dest> [tag]
  local url=$1 dest=$2 tag=${3:-}
  [ -d "$dest/.git" ] && { log "已存在，跳过 clone：$dest"; return 0; }
  local args=(-q --depth=1); [ -n "$tag" ] && args+=(--branch "$tag")
  rm -rf "$dest"
  log "clone $(basename "$dest") ${tag:-default}（走 $GH_PROXY）"
  git clone "${args[@]}" "$(gurl "$url")" "$dest"
}

mkdir -p "$LAB/logs" "$LAB/work" "$LAB/outputs" "$HF_HOME"
log "LAB=$LAB VENV=$VENV COMFY=$COMFY TORCH=$TORCH_VER"

# ---- 0. apt：aria2 下载器（base 镜像已带 git/ffmpeg/zsh/tmux/gcc/libgl1） ----
if ! command -v aria2c >/dev/null; then
  log "apt install aria2"
  sudo apt-get update -qq >/dev/null 2>&1 || true
  sudo apt-get install -y -qq aria2 >/dev/null 2>&1 || log "apt aria2 失败，稍后用 curl 兜底"
fi
command -v aria2c >/dev/null && log "aria2c $(aria2c --version | head -1)"

# ---- 1. venv h3 ----
if [ ! -x "$VENV/bin/python" ]; then
  log "创建 venv：$VENV"
  python3 -m venv "$VENV"
else
  log "venv 已存在：$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -V

# ---- 2. torch 三件套（cu124，带驱动 535 的 A6000；sm_86） ----
if python -c "import torch" 2>/dev/null; then
  log "torch 已装：$(python -c 'import torch;print(torch.__version__)')，跳过"
else
  log "pip install torch==$TORCH_VER(+cu124) torchvision==$TORCHVISION_VER torchaudio==$TORCHAUDIO_VER"
  pip install -q --upgrade pip
  pip install torch=="$TORCH_VER" torchvision=="$TORCHVISION_VER" torchaudio=="$TORCHAUDIO_VER"
fi

# ---- 3. 护栏：钉死 torch 三件套，装任何东西都带 -c ----
pip list --format=freeze 2>/dev/null | grep -E '^(torch|torchvision|torchaudio)==' > "$CONS"
grep -q '^torch==' "$CONS" || { echo "未找到 torch，终止"; exit 1; }
log "constraints: $(tr '\n' ' ' < "$CONS")"

# ---- 4. ComfyUI ----
if [ ! -d "$COMFY/.git" ]; then
  # 权重下载脚本可能已先建好 $COMFY/models/…（非空目录 clone 会拒绝），先 clone 到临时目录再合并
  tmp=$(mktemp -d "$LAB/comfy-clone.XXXX")
  gclone https://github.com/comfyanonymous/ComfyUI.git "$tmp" "$COMFY_TAG"
  mkdir -p "$COMFY" && cp -a "$tmp/." "$COMFY/" && rm -rf "$tmp"
else
  log "ComfyUI 已存在（$(git -C "$COMFY" describe --tags --always)），跳过 clone"
fi
log "pip install ComfyUI requirements（带护栏）"
pip install -q -c "$CONS" -r "$COMFY/requirements.txt"

# ---- 5. 自定义节点（禁装 ComfyUI-MiniMaxH3-Cache：会破坏生成） ----
declare -A NODES=(
  [ComfyUI-Manager]=https://github.com/Comfy-Org/ComfyUI-Manager.git
  [ComfyUI-VideoHelperSuite]=https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git
  [ComfyUI-KJNodes]=https://github.com/kijai/ComfyUI-KJNodes.git
  [rgthree-comfy]=https://github.com/rgthree/rgthree-comfy.git
  [ComfyUI-Crystools]=https://github.com/crystian/ComfyUI-Crystools.git
)
for n in "${!NODES[@]}"; do
  d="$COMFY/custom_nodes/$n"
  gclone "${NODES[$n]}" "$d"
  [ -f "$d/requirements.txt" ] && pip install -q -c "$CONS" -r "$d/requirements.txt"
done
if [ -d "$COMFY/custom_nodes/ComfyUI-MiniMaxH3-Cache" ]; then
  log "⚠ 检测到禁用插件 ComfyUI-MiniMaxH3-Cache，已改名隔离"
  mv "$COMFY/custom_nodes/ComfyUI-MiniMaxH3-Cache" "$COMFY/custom_nodes/.DISABLED_ComfyUI-MiniMaxH3-Cache"
fi

# ---- 6. 下载工具 ----
pip install -q -c "$CONS" "huggingface_hub[cli]" modelscope

# ---- 7. 自检 ----
log "自检"
python - <<'PY'
import importlib, torch
maj, minor = (int(x) for x in torch.__version__.split("+")[0].split(".")[:2])
assert (maj, minor) >= (2, 7), f"ComfyUI v0.34.5 需要 torch>=2.7（comfy-kitchen 用 list[int]），当前 {torch.__version__}"
print("python ok / torch", torch.__version__, "cuda", torch.version.cuda,
      "avail", torch.cuda.is_available(), "n_gpu", torch.cuda.device_count())
if torch.cuda.is_available():
    print("gpu0", torch.cuda.get_device_name(0), "cap", torch.cuda.get_device_capability(0))
    a = torch.randn(512, 512, device="cuda"); b = a @ a
    print("matmul ok", tuple(b.shape), float(b.sum()))
for m in ["safetensors", "av", "kornia", "comfyui_frontend_package", "transformers"]:
    try:
        importlib.import_module(m); print("ok", m)
    except Exception as e:
        print("MISSING", m, e)
PY
pip list --format=freeze > "$LAB/requirements.lock.h3.$(date +%Y%m%d).txt"
log "完成。df:"; df -h "$LAB" | tail -1
