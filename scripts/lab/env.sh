# 实验室容器（lab-host / agent）H3 链路环境
# 由 ~/.zshrc 里的一行 `source ~/workspace/remote_t2v/scripts/lab/env.sh` 引入。
# 故意不自动 activate h3：同一容器里还跑着 annotated / nano 两个别的项目环境。

export LAB_ROOT=/home/devuser/workspace
export COMFY_HOME=$LAB_ROOT/ComfyUI
export HF_ENDPOINT=https://hf-mirror.com
export HF_HOME=$LAB_ROOT/hf_cache
export HF_HUB_DISABLE_XET=1
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# 容器内 github 直连不通，clone 一律加代理前缀
alias ghp='git clone https://ghfast.top/'

alias h3env='source /home/devuser/.virtualenvs/h3/bin/activate'
# --listen 0.0.0.0 是必需的：容器有独立网络命名空间，绑 127.0.0.1 时宿主/SSH 隧道都进不来（PITFALLS #23）。
# 配套隧道（本机执行）：ssh -fN -L 8188:<容器IP>:8188 lab-host，容器 IP 用 docker inspect 现取。
alias comfy='cd $COMFY_HOME && python main.py --listen 0.0.0.0 --port 8188'
alias comfy-cpu='cd $COMFY_HOME && python main.py --cpu --listen 0.0.0.0 --port 8188'
alias h3lab='cd $LAB_ROOT/remote_t2v && h3env'
