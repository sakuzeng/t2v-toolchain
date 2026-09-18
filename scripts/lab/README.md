# 实验室容器链路（lab-host / agent）

第三类执行地点：实验室服务器上的 `agent` Docker 容器。与 `../remote/`（AutoDL 租用实例）
并行，跑同一套 MiniMax H3 + ComfyUI 链路，但环境与路径不同；本目录只放实验室特有的脚本。

## 机器与路径

| 项 | 值 |
|---|---|
| SSH | `ssh lab-host`（`<宿主IP>:22`，别名在 `~/.ssh/config`） |
| 容器 | `docker exec -it -u devuser agent zsh`，宿主别名 `dockeragent` |
| 硬件 | 2× RTX A6000 48 GB（sm_86）；宿主驱动 535.54 / CUDA 12.2，**无 nvcc** |
| 持久卷 | `workspace/`（=`/Data/<user>/agent/workspace`）、`.virtualenvs/`、`.cache/`、几个 dotfile；**其余路径容器重建即丢** |
| 代码 | `~/workspace/remote_t2v`（本仓库用 `tar`/`rsync` 从本机推上去） |
| ComfyUI | `~/workspace/ComfyUI`（`$COMFY_HOME`） |
| venv | `~/workspace` 之外的 `~/.virtualenvs/h3`，用 `h3env` 激活 |
| 日志 | `~/workspace/logs/`（宿主侧 `/Data/<user>/logs/` 亦可） |

## 三个与 AutoDL 不同的默认

1. **torch 钉 `2.7.1`（cu126）** —— 下限由框架定，不是由驱动定：ComfyUI v0.34.5 的 `comfy-kitchen`
   import 期就要 `torch.library.infer_schema` 支持 PEP 585 的 `list[int]`，那是 **torch ≥ 2.7** 才有的
   （最初按"驱动老"装了 2.6.0+cu124，GPU 自检全过但 ComfyUI 直接起不来，见 PITFALLS #22）。
   宿主驱动 535/CUDA 12.2 靠 CUDA 12.x minor version compatibility 跑 cu126，实测 `cuda 12.6 avail True`。
   换版本改 `TORCH_VER` / `TORCHVISION_VER` / `TORCHAUDIO_VER`。
2. **GitHub 走代理**：容器内 `curl https://github.com` 返回 000。所有 clone 用
   `https://ghfast.top/https://github.com/…`（备选 `gh-proxy.com`、`ghproxy.net`、`gitclone.com`），
   脚本里由 `gclone` 统一加前缀。
3. **无 conda、无 Blender**：venv 用 `python3 -m venv`；Blender 随 previz 于 2026-09-16 取消。

## 用法

```bash
# 容器内跑长任务：tmux 开在容器里（宿主 tmux 的 Ctrl-C 杀不掉容器内子进程，见 PITFALLS #16）
docker exec -u devuser agent tmux new-session -d -s h3 -n setup   # 之后 dockeragent 进去 tmux a -t h3
docker exec -u devuser agent tmux send-keys -t h3:setup \
  'bash ~/workspace/remote_t2v/scripts/lab/bootstrap/setup_h3.sh 2>&1 | tee ~/workspace/logs/setup_h3_lab.log' Enter

# 首次或每次改配置后重跑都幂等（torch / ComfyUI / 插件都带存在性判断）
bash ~/workspace/remote_t2v/scripts/lab/bootstrap/setup_h3.sh

# 权重（读 remote/models/h3/manifest.txt，curl 分块并发 + sha256 校验 + 断点续传）
SRC=modelscope WORKERS=24 bash ~/workspace/remote_t2v/scripts/lab/models_download.sh
ENGINE=aria2 bash ~/workspace/remote_t2v/scripts/lab/models_download.sh --verify-only   # 只校验

# 起 ComfyUI（容器内 tmux；--listen 0.0.0.0 才能被宿主/隧道访问，见 PITFALLS #23）
comfy
```

> `tee` 到一个新目录前先 `mkdir -p`：目标目录不存在时 `tee` 直接失败且不重试，整轮日志静默丢失（PITFALLS #20）。

## 从本机驱动（run capsule 落本仓库）

```bash
# 1) 取容器 IP（docker 动态分配，重建容器后会变，别写死）
IP=$(ssh lab-host 'docker inspect -f "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" agent')
# 2) 隧道打到【容器 IP】，不是 127.0.0.1（容器有独立网络命名空间，PITFALLS #23）
ssh -fN -L 8188:$IP:8188 lab-host
# 3) 之后和 AutoDL 链路一样，本机跑 t2v
python3 -m t2v validate <项目> [镜头]
python3 -m t2v run <项目> <镜头> --execute --generation-confirmed
```

验证隧道：`curl -s http://127.0.0.1:8188/system_stats`（应返回 comfyui 0.34.5 与两块 A6000）。

**浏览器首次打开会转一会儿**：ComfyUI 前端是 868 个文件、约 83 MB（`comfyui_frontend_package/static/assets`），
经隧道首次加载慢；加载完浏览器会缓存。嫌慢就把隧道加压缩重建（JS/JSON 压得动）：
`ssh -fNC -L 8188:$IP:8188 lab-host`（重建前先按 PID 停掉旧隧道，别用 `pkill -f`，见 PITFALLS #17）。

`env.sh` 由 `~/.zshrc` source，给出 `COMFY_HOME` / `HF_*` / `PIP_INDEX_URL` 与
`h3env`、`comfy`、`comfy-cpu`、`h3lab` 别名；**不自动 activate h3**，以免干扰同容器里的
`annotated` / `nano` 两个环境。

## 下载路径与实测速度

权重落到 `~/workspace/ComfyUI/models/`（= 宿主 `/Data/<user>/agent/workspace/ComfyUI/models/`），
按 `manifest.txt` 的 `diffusion_models/` `text_encoders/` `vae/` `loras/` `embeddings/` 铺开，`--verify-only` 与
aria2 版脚本用同一套 `.sha256.ok` 标记。

同一个 20 GB 文件、同一台机、按 `du` 计实际落盘（2026-09-18）：**modelscope 24 并发 ≈12 MB/s**、
modelscope 8 并发 ≈10 MB/s、aria2c `-x8 -s8` ≈6 MB/s、hf-mirror 16 并发 ≈5.6 MB/s、python urllib ≈0.5 MB/s。
瓶颈在 CDN/校园网出口（约 12 MB/s 饱和），换工具收益有限；63 GB 约 1.5 小时。
测速时的硬注意事项：modelscope 会 302 跳 CDN，curl **必须带 `-L`**，否则只拿到 375 字节跳转页，
按耗时算速度会得出完全错误的结论（PITFALLS #18）。

## 坑

见 `docs/ops/PITFALLS.md` 的「实验室容器（lab-host / agent）」12–21 条：宿主机是 CentOS 7 且只有 Python 2.7
（脚本必须在容器内跑）、git 仓库在上级目录（推代码不等于推 `.git`）、macOS 自带 rsync 是
openrsync 2.6.9（不认 `--info=`，用 `tar | ssh` 更稳）、GitHub 要挂代理、驱动 535 只能配 cu124、
`pgrep -f` 会匹配到自己的命令行。
