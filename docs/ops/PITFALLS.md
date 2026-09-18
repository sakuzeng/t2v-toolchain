# 远端 H3 链路踩坑记录（AutoDL + 实验室容器 + ComfyUI）

> 与 `plan/PLAN.md` 配套。每次尝试遇到的坑按日期追加，格式：现象 → 原因 → 解法。
> 跨项目通用的 AutoDL 坑（tmux 不继承 .zshrc、HF Xet 401、SSH 掉线等）已在
> `~/improve/coding/autodl/docs/autodl-usage-notes.md`，这里只记本链路特有的。
> 本文坑 1–6 中通用的部分（换实例域名变区域、pkill -f 自杀、ModelScope+aria2 下载、pip freeze 护栏、git clone 走加速、clone 非空目录）已于 2026-09-05 回写到该套件笔记。

## 索引

| # | 日期 | 阶段 | 一句话 |
|---|---|---|---|
| 1 | 2026-09-05 | 下载机 | SSH 握手即断：实例换了区域域名 westd→westb，Clash TUN 的 fake-IP 掩盖了真相 |
| 2 | 2026-09-05 | 下载机 | `pkill -f aria2c` 把承载命令的 ssh shell 自己杀了（exit 255） |
| 3 | 2026-09-05 | 下载机 | hf-mirror 只有 1–3 MB/s；ModelScope 有 Comfy-Org/MiniMax-H3 同名镜像，sha256 一致，16+ MB/s |
| 4 | 2026-09-05 | 下载机 | 镜像里 torch 按 URL 装，`pip freeze` 打成 `torch @ https://…`，`grep '^torch=='` 空 → pipefail 静默退出 |
| 5 | 2026-09-05 | 下载机 | 下载脚本先建了 `ComfyUI/models/…`，`git clone` 拒绝非空目录 |
| 6 | 2026-09-05 | 下载机 | GitHub 直连 clone 中途 `GnuTLS recv error (-110)`；直连失败自动切学术加速重试 |
| 7 | 2026-09-06 | ComfyUI | 启动日志一大段 Manager `TimeoutError` 与 `DEPRECATION WARNING`，噪音不影响生成；Manager 已设 offline 消掉 |
| 8 | 2026-09-06 | GPU 机 | R2V `ref_image_size=max` + 四张参考图 + ControlNet 在 1080p 级（2.07 MP）采样第 2 步 OOM：max 把每张图放大到 2048 短边，四图合计约 26 MP 参考 token；1080p 改 `match` |
| 9 | 2026-09-06 | ComfyUI | R2V 参考视频 `<Video 1>` 会被整段重绘（模型先验是视频编辑/续写），不能用来「只借运镜」；曾改走 H3 Fun ControlNet 深度控制视频，该路线已于 2026-09-16 否决（见 `docs/research/CAMERA_REPLICATION.md` 文首），现按光流量化写进 prompt |
| 10 | 2026-09-07 | 控制片制作 | 抹鹤脚本只留中央 30% 带，把裙腿削成细条，depth 里成了远处小人；控制片接入前必须与参考片同时间码并排核对 |
| 11 | 2026-09-08 | GPU 机 / ComfyUI | `conda activate h3` 实际激活 miniconda base，ComfyUI 报缺 sqlalchemy；启动一律写 `/root/autodl-tmp/conda/envs/h3/bin/python` 绝对路径 |
| 12 | 2026-09-18 | 实验室容器 | 宿主 lab-host 是 CentOS 7 + Python 2.7：一切命令必须在 `agent` 容器内跑 |
| 13 | 2026-09-18 | 本机 → 实验室 | macOS 自带 rsync 是 openrsync 2.6.9，不认 `--info=stats2`，打 usage 而退出码被管道里的 tail 吞成 0；推代码用 `tar \| ssh` |
| 14 | 2026-09-18 | 实验室容器 | 容器内 GitHub 直连 000，clone 一律加 `https://ghfast.top/` 前缀（容器里没有 `/etc/network_turbo`） |
| 15 | 2026-09-18 | 实验室容器 | 宿主驱动 535.54 / CUDA 12.2 → torch 钉 cu124（2.6.0）；A6000 是 sm_86 |
| 16 | 2026-09-18 | 实验室容器 | 宿主 `tmux send-keys C-c` 杀不掉 `docker exec` 起的容器内子进程 → 容器里留下占 apt 锁的僵尸；改在容器内跑 tmux |
| 17 | 2026-09-18 | 实验室容器 | `pgrep -f fetch_manifest.py` 匹配到自己那条 `bash -lc` 命令行并自杀（同坑 2）；用 `awk "/[f]etch…/"` |
| 18 | 2026-09-18 | 实验室容器 | **测量陷阱**：modelscope 回 302 跳 CDN，curl 不带 `-L` 只拿到 375 字节跳转页；照此计时得出过"121 MB/s""aria2 慢 20 倍"两个假结论 |
| 19 | 2026-09-18 | 实验室容器 | 权重源实测（同一 20 GB 文件）：modelscope 24 并发 ≈12 MB/s ＞ aria2c 8 连接 ≈6 MB/s ≈ hf-mirror 16 并发 5.6 MB/s ≫ urllib 0.5 MB/s |
| 20 | 2026-09-18 | 实验室容器 | `tee` 的目标目录不存在时直接失败且不重试，整轮日志静默丢失；重定向前先 `mkdir -p` |
| 21 | 2026-09-18 | 实验室容器 | 宿主时钟比本机慢约 18 s，`tar` 会警告"时间戳在未来"，无害 |
| 22 | 2026-09-18 | 实验室容器 / ComfyUI | **ComfyUI v0.34.5 要求 torch ≥ 2.7**：2.6 起不来（`comfy-kitchen` 用了 PEP 585 `list[int]`）；升 2.7.1+cu126 后 535 驱动照样跑 |
| 23 | 2026-09-18 | 实验室容器 | 容器有独立网络命名空间：`ssh -L 8188:127.0.0.1:8188 lab-host` 转到的是**宿主**的 8188（空的）；要 ComfyUI `--listen 0.0.0.0` + 转发**容器 IP**（`docker inspect` 取） |

## 记录

### 1. SSH 握手即断，其实是域名错了（2026-09-05，下载机）
- 现象：`ssh autodl` 报 `kex_exchange_identification: Connection closed by remote host`；TCP 能连、任何端口都"能连"。
- 原因：新实例在 `connect.<区域>.seetacloud.com`，`~/.ssh/config` 里还是旧的 `westd`。本机 Clash Verge 开 TUN + fake-IP（198.18.x.x），任何域名/IP 的 TCP 都由 Clash 本地应答，`nc -z` 永远"succeeded"，无法从本机分辨是网关拒绝还是实例没开。
- 解法：每次换实例先对照控制台 SSH 指令的 **域名 + 端口** 两项，不只看端口。诊断时用控制台给的完整命令直接试。
- 已回写脚本：否（属 ssh config 维护）。

### 2. `pkill -f aria2c` 自杀（2026-09-05，下载机）
- 现象：一条 `ssh autodl '… pkill -f aria2c …'` 直接 exit 255，后半段命令没执行。
- 原因：`-f` 按完整命令行匹配，承载这串命令的远端 shell 命令行里含 "aria2c"，被一起杀掉。
- 解法：用 `pkill -x aria2c`（精确进程名），或 `tmux kill-window` 让 tmux 收尾。同一天又踩一次（`pkill -f "main.py --cpu"`）——**通则：通过 `ssh host '…'` 发出的任何 `pkill -f <模式>`，模式必然出现在承载它的远端 shell 命令行里，必自杀**。要杀自己起的进程，记 PID（`setsid cmd & echo $! > x.pid`）按 PID 杀，或走 tmux 窗口。
- 已回写脚本：否（操作习惯）。

### 3. hf-mirror 慢，ModelScope 镜像快且 sha 一致（2026-09-05，下载机）
- 现象：aria2 -x8 走 hf-mirror 只有 1–2.6 MB/s，62GB 要 7 小时；学术加速直连 HF 也只有 2 MB/s。
- 原因：hf-mirror 对大文件限速/不稳（autodl 通用笔记已有记录）。
- 解法：ModelScope 上有 `Comfy-Org/MiniMax-H3` 同名镜像，API 给出的 sha256/size 与 HF 17 个文件全部一致，单连接 17 MB/s。`download_h3.sh` 默认 `SRC=modelscope`，URL 形如 `https://www.modelscope.cn/models/<repo>/resolve/master/<path>`。校验 API：`https://www.modelscope.cn/api/v1/models/<repo>/repo/files?Recursive=true`。
- 已回写脚本：是。

### 4. `pip freeze` 打不出 `torch==`，护栏为空导致脚本静默退出（2026-09-05，下载机）
- 现象：setup 日志停在打印 torch 版本那行，tmux 里回到提示符，无报错。
- 原因：AutoDL 镜像的 torch 用 wheel URL 安装，`pip freeze` 输出 `torch @ https://download.pytorch.org/...`；`grep -E '^torch=='` 匹配为空，`set -euo pipefail` 下管道失败即退出。另外镜像不带 torchaudio。
- 解法：用 `pip list --format=freeze`（输出 `torch==2.8.0+cu128`）生成护栏；找不到 torch 就明确报错退出；torchaudio 钉到与 torch 相同的三段版本。
- 已回写脚本：是。

### 5. `git clone` 拒绝非空目录（2026-09-05，下载机）
- 现象：`fatal: destination path '/root/autodl-tmp/ComfyUI' already exists and is not an empty directory.`
- 原因：setup 和 download 并行跑，download 先 `mkdir -p ComfyUI/models/diffusion_models`。
- 解法：clone 到临时目录再 `cp -a tmp/. ComfyUI/` 合并。
- 已回写脚本：是。

<!-- 模板
### N. 一句话标题（YYYY-MM-DD，阶段：下载机/克隆/GPU机/ComfyUI/Blender）
- 现象：
- 原因：
- 解法：
- 是否已回写到 setup/download 脚本：是/否
-->

### 6. GitHub 直连 clone 中途断（2026-09-05，下载机）
- 现象：`fatal: unable to access 'https://github.com/…': GnuTLS recv error (-110): The TLS connection was non-properly terminated.`，curl 探测 github.com 是 200 也照样会断。
- 原因：AutoDL 出口到 GitHub 不稳，大仓库 clone 撑不到结束。
- 解法：`setup_h3.sh` 的 `gclone()` 先直连，失败则在子 shell 里 `source /etc/network_turbo` 重试（子 shell 结束代理即消失，后续 pip 仍走 tuna 镜像，避免 autodl 笔记里"开加速后 pip 变慢"的坑）。
- 已回写脚本：是。

### 7. 启动日志里 Manager 报错与弃用警告是噪音（2026-09-06，ComfyUI）
- 现象：GPU 模式起 ComfyUI 后日志出现两段 `[ERROR] [ComfyUI-Manager] Failed to perform initial fetching 'custom-node-list.json' / 'extension-node-map.json'`，堆栈落在 aiohttp `TimeoutError`；前面还有多条 `[WARNING] [DEPRECATION WARNING] Detected import of deprecated legacy API: /scripts/ui.js、/extensions/core/groupNode.js、/extensions/core/widgetInputs.js、/scripts/ui/components/button.js`。
- 原因：Manager 启动时去 GitHub raw 拉节点列表缓存，AutoDL 出口到 GitHub 不稳（同坑 6）超时；弃用警告是 VHS / KJNodes / rgthree 等插件用了前端 1.49 已弃用的旧 API。两者都与生成流程无关，`got prompt` 之后照常跑完（480p 与 768p 冒烟都是在这些报错之后通过的）。
- 解法（2026-09-06 已做）：`ComfyUI/user/__manager/config.ini` 里 `network_mode = offline`，重启 ComfyUI 后启动日志只剩一行 `network_mode: offline`，两段 TimeoutError 消失（Manager 装节点功能随之不可用，本链路禁装插件所以无所谓）。弃用警告仍在，忽略。看日志时用 `grep -vE "DEPRECATION|ComfyUI-Manager|aiohttp|asyncio|\^\^\^|File \"|await |raise |    "` 过滤，或只看 `got prompt` 之后的行。若嫌烦：Manager 设置里把 `network_mode` 改为 `offline`（`custom_nodes/ComfyUI-Manager/config.ini`），弃用警告等插件升级。不要为消除警告去升级/换插件——护栏 `constraints.h3.txt` 之外的改动都可能带来新的 `IMPORT FAILED`。
- 已回写脚本：否（无需）。

### 8. 1080p + max 参考图 + ControlNet 采样 OOM（2026-09-06，GPU 机）
- 现象：`SamplerCustomAdvanced` 第 2/20 步 `torch.OutOfMemoryError: Allocation on device`，栈在 `comfy_kitchen …/int8_linear`；ComfyUI 历史里状态 error，`comfy_run.py` 轮询到 error 退出、无产物。480p 同配置正常。
- 原因：`ref_image_size=max` 按节点说明「用参考管线的 2048 短边」，是**放大**不是只缩：面部裁图 840×810、全身 768×1344、裙靴裁图 840×1480、剑 1952×1120 四张放大后合计约 26 MP 的参考 token，每步采样都带着；再加 ControlNet 控制 token 与 2.07 MP 的生成 token，激活内存超过 32 GB。
- 解法：1080p 级用 `--ref-image-size match`（只缩不放，四图合计约 5 MP）；参考图本身 ≥0.7 MP 时 1080p 下身份保真够用。480p/768p 挑 seed 可继续用 max。仍 OOM 再试重启 ComfyUI 加 `--lowvram`（权重外卸、给激活腾空间，慢）。
- 已回写脚本：run.sh 默认仍是 max，1080p 命令加 `--ref-image-size match` 覆盖（argparse 后者优先）。

### 9. `<Video 1>` 参考视频被整段重绘（2026-09-06，ComfyUI）
- 现象：C01 喂参考片段作 `<Video 1>` 并声明 weak_reference 只借运镜，结果三镜里两镜是参考片原表演者（白袍、赤足），只有正面特写保住我们的角色。
- 原因：R2V 把参考视频逐帧（94 帧）作为视觉条件与 1 张人物图并列；官方定位 `<Video N>` 是剪辑源/续写起点/整段结构，模型先验是重绘该视频；文字的 retention 标记压不过稠密画面条件。
- 解法：不喂参考视频；运镜与节拍用分镜表 + 光流量化写进文字，逐帧控制走 H3 Fun ControlNet（深度）。参考视频只在真要做「视频编辑/角色替换」时用。
- 已回写脚本：`--ref-video` 接线保留（现为 `python3 -m t2v h3 --ref-video`），`run.sh` 不再自动挂参考片段。

### 10. 控制片清场把主体也抹掉，模型忠实复现了错误（2026-09-07，ComfyUI / 控制片制作）

> 2026-09-16：深度/姿态控制路线已整体否决（`docs/research/CAMERA_REPLICATION.md` 文首），本条的脚本与控制片都已删除。留作记录：**任何逐帧约束输入在接入前都必须与参考片同时间码并排核对**——这条规则对将来任何控制类输入仍然成立。
- 现象：C001A v004/v007 前 1.4 s 都生成为"远处小人全身站定"，且 0.3 s 就落地；prompt 写的是水面低机位腿部近景、0.7 s 触水。验收表 A10/A11 两版都挂。
- 原因：`scripts/clean_depth_sides.py --center 0.30` 为抹掉两侧白鹤只保留中央 30% 带，而参考片 0.4–1.4 s 的裙摆和腿占宽 40–55%，被削成一根细条；深度里"细条 + 大片近景水面"就是一个远处小人。depth 强度 1.0 时模型完全照做。此前没人逐帧看过控制片。
- 解法：`clean_depth_sides.py` 加 `--schedule "0.30:0.0,0.90:0.40,1.57:0.55"` 分时段带宽（人未入画的 0.30 s 前整帧清空，连中间那只小鹤一起去掉）；新控制片 `references/controls/c001a/depth_clean_v2_73.mp4`。
- 规则：**任何控制片在接入前必须与参考片同时间码抽帧并排核对**（`prepare_evidence.py --compare 控制片`），清场带宽按主体实际宽度定；产物与 prompt 不符时先怀疑控制片再怀疑 prompt。
- 已回写脚本：是（`--schedule`）。

### 11. `conda activate h3` 激活到了 miniconda base，ComfyUI 报 `No module named 'sqlalchemy'`（2026-09-08，GPU 机 / ComfyUI）
- 现象：重新开机后在 tmux 里 `source ~/.bashrc; conda activate h3; python main.py …`，提示符显示 `(h3)`，却在 `app/assets/database/queries/asset.py` 抛 `ModuleNotFoundError: No module named 'sqlalchemy'`；同一台机 11:15 还正常跑过。
- 原因：`which python` 是 `/root/miniconda3/bin/python`（base，3.12，没装 ComfyUI 依赖），不是 `/root/autodl-tmp/conda/envs/h3/bin/python`（sqlalchemy 2.0.52、torch 2.8 都在）。远端登录壳是 zsh，`~/.bashrc` 里的 conda 初始化指向 miniconda，`conda activate h3` 只改了提示符没有把数据盘那套 conda 的 env 放到 PATH 前面。历史记录里之前几次都是写绝对路径启动的。
- 解法：启动一律写绝对路径 `cd /root/autodl-tmp/ComfyUI && /root/autodl-tmp/conda/envs/h3/bin/python main.py --listen 127.0.0.1 --port 8188 --lowvram 2>&1 | tee -a /root/autodl-tmp/logs/comfy_YYYYMMDD.log`；或先 `source /root/autodl-tmp/conda/etc/profile.d/conda.sh && conda activate h3`。装包同理用该 python 的 `-m pip`。别看到缺包就 pip install，先 `which python`。
- 顺带：本机已 `ssh -fN autodl` 占住 8188 后，其他 ssh 命令会刷 `bind [127.0.0.1]:8188: Address already in use`，加 `-o ClearAllForwardings=yes` 即可。
- 已回写脚本：否（启动命令写进 RUNBOOK 与本条）。

## 实验室容器（lab-host / agent，2026-09-18 首次搭建）

### 12. 宿主只有 Python 2.7，什么都不能在宿主跑（2026-09-18，实验室容器）
- 现象：`ssh lab-host` 上去 `python3 -V` → `未找到命令`，`python -V` → `Python 2.7.5`（CentOS 7），`which conda` 也没有；但 `nvidia-smi` 显示 2× RTX A6000。
- 原因：这台是实验室公共机器，宿主是老的 CentOS 7；所有开发环境都在 `agent` 容器里（Ubuntu 22.04 + Python 3.10 + sudo NOPASSWD）。
- 解法：一切命令写成 `docker exec -u devuser agent bash -lc "…"`，或直接 `dockeragent` 进去（宿主 `~/.bashrc` 里的别名）。长任务用**容器内**的 tmux（见坑 16）。
- 已回写脚本：是（`scripts/lab/bootstrap/setup_h3.sh` 开头就写明"在容器内运行"）。

### 13. macOS 自带 rsync 把推代码这一步静默做废（2026-09-18，本机 → 实验室）
- 现象：`rsync -az --info=stats2 …` 输出一大段 rsync 用法说明，远端目录建了但是空的；因为命令末尾接了 `| tail -20`，退出码变成 tail 的 0，看起来"成功"。
- 原因：macOS 自带的是 **openrsync 2.6.9**（`protocol version 29`），不认 rsync 3.1+ 的 `--info=`；报错退出 1 被管道吞掉。
- 解法：跨公网推目录用 `tar czf - --exclude='._*' . | ssh host 'tar xzf - -C 目标'`（顺带绕开 macOS 的 `._*` 资源叉文件）；要用 rsync 就只用 2.6.9 认识的参数，并且别把退出码交给管道。
- 已回写脚本：否（本文档 + `scripts/lab/README.md` 记录）。

### 14. 容器内 GitHub 直连 000（2026-09-18，实验室容器）
- 现象：`curl -sI https://github.com` 返回 `000`，`git clone` 直接失败；而 pypi（清华/阿里）、hf-mirror、modelscope、gitee 都是 200。
- 原因：实验室网络对 GitHub 不通，容器里也没有 AutoDL 那套 `/etc/network_turbo`。实测可用的镜像前缀：`ghfast.top`、`gh-proxy.com`、`ghproxy.net`、`gitclone.com`（`ghproxy.cc`、`hub.fastgit.xyz`、`mirror.ghproxy.com` 都不通）。
- 解法：`gclone()` 统一加前缀 —— `git clone https://ghfast.top/https://github.com/<owner>/<repo>.git`；ComfyUI 与 5 个插件都是这么装上的。
- 已回写脚本：是（`setup_h3.sh` 的 `gclone`/`gurl`）。

### 15. 驱动 535 只到 CUDA 12.2，torch 不能用 AutoDL 那套 cu128（2026-09-18，实验室容器）
- 现象：宿主 `NVIDIA-SMI 535.54.03 / CUDA Version 12.2`，卡是 RTX A6000（`cap (8, 6)` = sm_86），且没有 `nvcc`。AutoDL 镜像里那套 `torch 2.8.0+cu128` 照着搬过来有版本兼容风险。
- 原因：cu128 wheel 面向更新的驱动/Blackwell；A6000 是 Ampere（int8 OK，但**没有 nvfp4 硬件**，H3 的 nvfp4 文本编码器只能靠软件反量化跑）。
- 解法：钉 **cu124 三件套**（PyPI 上 `torch==2.6.0` 的 linux 默认 wheel 就是 cu124）：`torch 2.6.0 / torchvision 0.21.0 / torchaudio 2.6.0`，装完写进 `constraints.h3.txt` 护栏再装 ComfyUI。自检结果：`cuda 12.4 avail True n_gpu 2`、GPU matmul 通过。
- 已回写脚本：是（`setup_h3.sh` 的 `TORCH_VER`/`TORCHVISION_VER`/`TORCHAUDIO_VER`）。

### 16. 宿主 tmux 里 Ctrl-C 杀不掉容器内的子进程（2026-09-18，实验室容器）
- 现象：第一轮 `docker exec -u devuser agent bash -lc "setup_h3.sh"` 起在**宿主** tmux 窗口里，Ctrl-C 之后容器内 `apt-get update` 还在跑，第二轮 apt 报 `Could not get lock /var/lib/apt/lists/lock (held by process 9126)`、`Unable to locate package aria2`；两轮 `setup_h3.sh` 同时往同一个日志写，日志互相污染。
- 原因：`send-keys C-c` 的 SIGINT 只打到宿主的 `docker exec` 客户端，容器内进程组的祖先没了但进程继续；而且 `tee` 的目标目录当时还不存在，那轮日志一个字都没留下（见坑 20）。
- 解法：**长任务一律在容器内跑 tmux**（`docker exec -u devuser agent tmux new-session -d -s h3`，窗口 setup / dl / comfy），Ctrl-C 就能真正打到容器内的前台进程组；已经残留的按 PID 杀，别指望信号。
- 已回写脚本：否（记进 `scripts/lab/README.md` 的用法与本文）。

### 17. `pgrep -f` 又自杀了一次（2026-09-18，实验室容器）
- 现象：一条 `docker exec … bash -lc "…; P=$(pgrep -f fetch_manifest.py); kill $P; tmux send-keys …"` 整条命令没有任何输出就结束了，下载器也确实死了 —— 但**新任务没起来**。
- 原因：`pgrep -f` 匹配整条命令行，而这条 `bash -lc` 的命令行里就含 `fetch_manifest.py`，于是它匹配到自己并把自己 kill 了（与坑 2 的 `pkill -f aria2c` 同一类）。
- 解法：用 `ps -eo pid,cmd | awk "/[f]etch_manifest.py/ {print \$1}"` 这种 `[f]` 技巧（命令行里是 `[f]etch…`，正则匹配不到自己）；或者在容器内 tmux 里直接 Ctrl-C。
- 已回写脚本：否（本文档）。

### 18. 【测量陷阱】curl 不带 `-L` 时，"下载速度"全是假的（2026-09-18，实验室容器）
- 现象：同一个 20 GB 权重，`curl -r 0-49999999 -o /dev/null <modelscope URL>` 报"50 MB / 1.9 s ≈ 26 MB/s"，8 并发"240 MB / 2.0 s ≈ 121 MB/s"；据此得出"aria2c 只有 6 MB/s，比 curl 慢 20 倍"，还把 aria2 换掉重写了一遍下载器。
- 原因：modelscope 对 LFS 请求回 **HTTP 302**，`Location` 指向 `cdn-lfs-cn-1.modelscope.cn/...&auth_key=…`；curl 不带 `-L` 不跟随，只拿到 375 字节的跳转页就"完成"了。`-o /dev/null` + `-w %{time_total}` 让这件事完全看不出来。python 的 `urllib` 默认跟随重定向，所以旧版脚本反而能下（但慢）。
- 解法：**测带宽必须同时核对 `%{http_code}` 与 `%{size_download}`**（期望 206 + 预期字节数），否则不要把时间当速度。`fetch_manifest.py` 里 curl 一律带 `-L`，并在每个分块后校验写入字节数 == 请求区间（302 的 375 字节会立刻被判成"短读"）。
- 已回写脚本：是（`-L` + 短读校验 + worker 失败即 `abort`，不再空扫剩余分块）。

### 19. 权重下载源实测：modelscope 24 并发最快，但仍只有 ~12 MB/s（2026-09-18，实验室容器）
- 现象：同一台机、同一个 20 GB 文件、`du` 计实际落盘：
  - modelscope（`resolve/master` → 302 → CDN）**24 并发 ≈ 12 MB/s**（8 并发约 10–11 MB/s）
  - aria2c `-x8 -s8` ≈ 6 MB/s
  - hf-mirror `resolve/main` 16 并发 ≈ 5.6 MB/s（单连接测试反而是 modelscope 的 2.4 倍，但**并发被限**，不能只看单连接）
  - python urllib 8 并发 ≈ 0.5–1.4 MB/s（且被 302 后的 CDN 拖慢）
- 原因：瓶颈在 CDN/校园网出口一侧，加并发只能到 ~12 MB/s 就饱和；`aria2` 与 `curl` 的差距远没有最初以为的大（那个结论是坑 18 的假数据）。
- 解法：默认用 `scripts/lab/models_download.sh`（= `fetch_manifest.py`，curl 分块并发 + `.progress.json` 断点续传 + sha256 落 `.sha256.ok`），`SRC=modelscope WORKERS=24`；要回退 aria2 用 `ENGINE=aria2`。63 GB 预计 1.5 小时左右，别再为"提速"反复换工具——先把 302/`-L` 这类硬错误排除掉。
- 已回写脚本：是（`scripts/lab/models_download.sh` + `scripts/lab/fetch_manifest.py`）。

### 20. `tee` 到不存在的目录＝整轮日志静默丢失（2026-09-18，实验室容器）
- 现象：第一次起 `setup_h3.sh` 时 `| tee ~/workspace/logs/setup_h3_lab.log` 报 `No such file or directory`，而容器里 `~/workspace/logs` 当时还不存在（脚本里的 `mkdir -p` 在 tee 之后才执行）；那一轮全部输出只留在 tmux 回滚里，80×23 的窗口一屏就冲掉了。
- 解法：重定向到新目录前先 `mkdir -p`（宿主侧建一次即可，bind mount 立刻可见）；日志目录统一 `~/workspace/logs/`。
- 已回写脚本：是（本文档流程；脚本自身的 `mkdir -p "$LAB/logs"` 保留）。

### 21. 宿主时钟慢 18 秒（2026-09-18，实验室容器）
- 现象：`tar xzf` 刷一串 `时间戳 2026-09-18 21:31:10 是未来的 18.089216529 秒之后`。
- 原因：lab-host 宿主未同步 NTP，比本机慢约 18 s；容器共用宿主时钟。
- 解法：无害，忽略。但跨机比对日志时间/`mtime` 时记得有这个偏移（排查"进程启动早于脚本落盘"时曾差点被它误导）。
- 已回写脚本：否。

### 22. ComfyUI v0.34.5 起不来：`comfy-kitchen` 要 torch ≥ 2.7（2026-09-18，实验室容器 / ComfyUI）
- 现象：按"驱动老 → 用 cu124"的思路装了 `torch 2.6.0+cu124`，GPU 自检全过（`cuda avail True`、matmul OK），但 `python main.py --quick-test-for-ci` 直接 traceback：
  `File "…/comfy_kitchen/backends/eager/na.py", line 164, in <module> … ValueError: infer_schema(func): Parameter kernel_size has unsupported type list[int]`。
  `comfy_kitchen` 的 METADATA 里**没有声明 torch 依赖**（`Requires:` 为空），所以 pip 不拦、护栏也拦不住。
- 原因：`comfy_kitchen` 0.2.31 用 PEP 585 的 `list[int]` 声明自定义算子参数，而 `torch.library.infer_schema` 直到 torch 2.7 才支持 `list[...]`（此前只认 `typing.List[int]`）；comfy-kitchen 官方也把最低版本写成 **PyTorch ≥ 2.7.0**。
- 解法：升到 **`torch 2.7.1 + torchvision 0.22.1 + torchaudio 2.7.1`**（PyPI linux 默认 wheel = cu126）。宿主驱动 535/CUDA 12.2 靠 **CUDA 12.x minor version compatibility** 照样跑通：自检 `torch 2.7.1+cu126 cuda 12.6 avail True n_gpu 2` + GPU matmul 通过。随后重跑 `setup_h3.sh` 让 `constraints.h3.txt` 跟着变成 `torch==2.7.1`（否则后面装插件会把 torch 拽回旧版）。升完 `--quick-test-for-ci` 零 `IMPORT FAILED`，1271 个节点注册，H3 原生节点齐全。
- 教训：**先看框架侧的硬要求，再按驱动选 CUDA 版本**——"驱动老就降 torch"会撞上框架的地板；`pip show <包>` 的 `Requires:` 为空 ≠ 没有版本要求。
- 已回写脚本：是（`setup_h3.sh` 默认改 2.7.1，并在自检里加 `torch>=2.7` 断言）。

### 23. 宿主 `ssh -L` 转发不到容器里的 ComfyUI（2026-09-18，实验室容器）
- 现象：按 AutoDL 的习惯 `ssh -fN -L 8188:127.0.0.1:8188 lab-host` 建隧道，端口监听了（`lsof` 有），但 `curl http://127.0.0.1:8188/system_stats` 返回**空**；容器内 `curl 127.0.0.1:8188` 却是 200。
- 原因：容器有**独立的网络命名空间**（compose 桥接网 `10.254.252.0/24`，agent = `<容器IP>`）。SSH 服务跑在**宿主**上，`-L …:127.0.0.1:8188` 的“127.0.0.1”是宿主自己的回环，那里根本没人监听；而 ComfyUI 默认 `--listen 127.0.0.1` 只绑容器的回环，宿主也连不到容器 IP。
- 解法：两头一起改 —— ① 容器内用 `--listen 0.0.0.0 --port 8188` 起 ComfyUI（`scripts/lab/env.sh` 的 `comfy` 别名已改）；② 隧道指向**容器 IP**：`ssh -fN -L 8188:$(ssh lab-host 'docker inspect -f "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" agent'):8188 lab-host`。验证：宿主 `curl http://<容器IP>:8188/system_stats` → 200，本机经隧道 `/object_info` → 1271 个节点。容器 IP 是 docker 动态分配的，**重建容器后会变**，用 `docker inspect` 现取，别写死。
- 注意：`--listen 0.0.0.0` 会让同一 docker 桥上的兄弟容器也能访问 8188（宿主机外仍不可达，agent 容器没有发布 8188 端口）；这台是共享机，改回 `comfy-cpu`/仅本机时记得用 `--listen 127.0.0.1`。
- 已回写脚本：是（`scripts/lab/env.sh` 的 `comfy` 别名 + `scripts/lab/README.md` 的隧道命令）。
