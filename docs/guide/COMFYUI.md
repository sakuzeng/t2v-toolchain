# ComfyUI 使用手册

> 常青手册。正文来自 `research/WORKFLOW.md` §1/§3/§4/§6/§7（2026-09-05 调研）——
> 该文 2026-09-16 按章节拆进 `guide/` 后退场。
> 工作流文件本身在仓库根 `workflows/`（角色划分见那里的 README），prompt 规范见 `guide/H3_PROMPT.md`。

| 模板 | 节点核心 | 输入 | 用途 |
|---|---|---|---|
| `video_minimax_h3_t2v` | `MiniMaxH3ImageToVideo`（不接图） | prompt | 纯文生视频 |
| `video_minimax_h3_i2v` | 同上，接 `first_frame` / `last_frame` | 首帧、尾帧任选 | 首帧 / 首尾帧 / 尾帧模式（I2VA / FL2VA / L2VA） |
| `video_minimax_h3_i2v_continuation` | 同上 | 一张图 + 空 prompt 起步 | 从图续写运动/镜头/声音 |
| `video_minimax_h3_multiframe_reference` | `MiniMaxH3AddGuide` 串联 | 最多 4 张关键帧锚在时间轴任意点 | 多关键帧控制运动与构图；**`t2v` 不再接这条**，关键帧锚点已于 2026-09-16 随深度控制一起退役 |
| `video_minimax_h3_r2v` | `MiniMaxH3ReferenceToVideo` + `ref2va` 权重 | ≤9 图、≤3 视频（可带音轨）、≤3 音频 | 角色/风格/动作/镜头/声线参考 |

共同骨架：`UNETLoader` → `CLIPLoader`(Qwen3-VL) → `VAELoader`×2 → `EmptyMiniMaxH3LatentAV` → 采样（`res_multistep + simple`，20 步）→ `SaveVideo`（MP4 内嵌立体声）。分辨率经 `ResolutionSelector` 按 megapixels 选（0.4=864×480，0.98=1344×768 官方 768p，必须 32 的倍数）；时长由 Math 节点换算成 `17k+5` 帧。另有 9 个 `api_*` 模板走 Comfy 云 API，**付费，禁用**。

社区简化包 `nkxx188/ComfyUI-MiniMaxH3-Easy`：一个节点覆盖 T2V/I2V/首尾帧/R2V，`@Image1` 自动转 `<Picture 1>`，`#` 生成 `<d>` 对白块，不改核心文件。适合人在 UI 里手调；程序化提交仍用原生节点（API JSON 稳定）。

## 2 程序化驱动 ComfyUI


- 接口：`POST /prompt`（API 格式 JSON，非 UI 格式）、`GET /history/<id>`、`GET /view?filename=`、`POST /upload/image`、`/object_info` 校验节点、`/system_stats` 看显存、`/interrupt`。
- 做法：在 UI 里把官方模板跑通 → `Save (API Format)` 导出 → `project.json` 与 prompt frontmatter 解析 prompt / 参考图 / seed / 分辨率 / 时长 → 填值提交、轮询并下载到独立 run capsule。现由 `python3 -m t2v` 实现（`t2v/comfy/client.py` 管通信，`t2v/engines/h3/` 管建图与执行）；工作流文件的角色划分见 `workflows/README.md`。
- 参考实现（都可借鉴，不直接装）：
  - `SlavaSexton/ComfyUI-Agent-Kit`（Apache-2.0）：Claude Code 插件，约 90 个 MCP 工具，含 **H3 专用 skill**（三段式 prompt、量化梯度、加速项），按显存推荐模型；重，且假定本地 ComfyUI。
  - `MCKRUZ/ComfyUI-Expert`（MIT）：13 个 skill，`state/inventory.json` 缓存模型/节点/显存并在提交前校验；REST 5 秒轮询而非 WebSocket，适合 Claude Code。
  - `Comfy-Org/ComfyUI` 讨论 #13283：从节点源码抽取 360+ 节点定义的 workflow-builder skill。
- 远端访问：`ssh -L 8188:127.0.0.1:8188 autodl`，本机浏览器与脚本都打 `127.0.0.1:8188`。
  实验室链路**不能照抄这条**：容器有独立网络命名空间，得先让 ComfyUI `--listen 0.0.0.0`，再把隧道打到容器 IP ——
  `IP=$(ssh lab-host 'docker inspect -f "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" agent'); ssh -fN -L 8188:$IP:8188 lab-host`（见 `docs/ops/PITFALLS.md` 23 条）。
- **让脚本提交的任务实时显示在浏览器画布上**：ComfyUI 只把 `progress / executing / executed` 事件发给提交该任务的
  `client_id`，而前端是从 `window.name` 取 clientId 去连 websocket 的（不是 URL 参数）。做法：在浏览器那个标签页的控制台执行
  `window.name = 'lab-smoke'; location.reload()`，再用 `--client-id lab-smoke` 提交 —— 画布实时显示进度，跑完视频落进对应节点。
  不传 client_id 时这些事件**根本不发**（队列与历史里能看到状态，但画布不动）。提交时导出的
  `<name>__<stamp>__<prompt_id>.ui.json`（`--export-ui` 可指定路径）与提交的图节点 id 一致，拖进浏览器即可对上。
  标签页关闭后 `window.name` 会换，需要重新设。
- 两处部署（2026-09-18 起）：AutoDL 实例与实验室 `lab-host` 的 `agent` 容器跑同一套 ComfyUI v0.34.5 + 同一批插件，
  差异只有路径、torch 版本（AutoDL `2.8.0+cu128` / 实验室 `2.7.1+cu126`，因宿主驱动只到 CUDA 12.2）与 clone 代理
  （AutoDL 走 `/etc/network_turbo`，实验室走 `ghfast.top`）。约束文件分别是 `/root/autodl-tmp/constraints.h3.txt`
  与 `~/workspace/constraints.h3.txt`。**ComfyUI v0.34.5 要求 torch ≥ 2.7**：`comfy-kitchen` 的
  `torch.library.infer_schema` 用了 PEP 585 的 `list[int]`，torch 2.6 只认 `typing.List[int]`，实验室最初装 2.6.0 时
  卡在 `ValueError: Parameter kernel_size has unsupported type list[int]`（见 `docs/ops/PITFALLS.md` 22 条）。

## 3 自定义节点（插件）取舍


原则：**少装**。每个插件都有自己的 pip 依赖，会拱 torch/transformers；装任何插件都带约束文件
（AutoDL `-c /root/autodl-tmp/constraints.h3.txt`，实验室 `-c ~/workspace/constraints.h3.txt`），装完重启 ComfyUI 看日志里 `IMPORT FAILED`。

| 层 | 插件 | 作用 | 状态 |
|---|---|---|---|
| 基础 | ComfyUI-Manager | 装/更/删插件，缺失节点一键补 | 已装 |
| 基础 | ComfyUI-VideoHelperSuite | 视频/音频加载、合成、预览，H3 出片必备 | 已装 |
| 基础 | ComfyUI-KJNodes | 工具节点集；`Patch Sage Attention KJ` 在这里 | 已装 |
| 顺手 | rgthree-comfy | Seed 节点、Fast Muter（一键屏蔽分支）、Context、断线修复 | 建议阶段 B 装 |
| 顺手 | ComfyUI-Crystools | 显存/CPU/进度监视条，看 5090 是否贴 32GB 上限 | 建议阶段 B 装 |
| 顺手 | pythongosssss/ComfyUI-Custom-Scripts | 自动补全、工作流图片预览、显示节点 ID | 可选 |
| H3 专用 | nkxx188/ComfyUI-MiniMaxH3-Easy | 一个节点覆盖各模式，`@Image1` / `#` 对白语法 | UI 手调时装 |
| H3 加速 | pepikir/minimax-h3-speedup、xmarre Spectrum、Icyoung TeaCache | 见 `research/ACCEL.md` | 基线后 A/B |
| 后期 | ComfyUI-Frame-Interpolation（RIFE/FILM） | 24→48fps 或慢动作 | 按需 |
| 后期 | ComfyUI-SeedVR2 / Comfy-Org Nvidia_RTX_Nodes（RTX VSR） | 768p→1080p/2K 视频超分，时序一致 | 按需；SeedVR2 需另下权重 |
| 后期 | ComfyUI-Impact-Pack | 人脸/局部细化、分段超分 | 按需，依赖重 |
| 禁 | lihaoyun6/ComfyUI-MiniMaxH3-Cache | 改核心文件 | 禁 |
| 禁 | 任何 `api_*` 模板 / Partner 节点 | 走云 API 付费 | 禁 |

## 4 本机浏览器访问远端 ComfyUI


`~/.ssh/config` 的 `autodl` 别名已加 `LocalForward 8188 127.0.0.1:8188`：任何一条 `ssh autodl` 连着时，本机打开 `http://127.0.0.1:8188` 就是远端 UI（脚本的 API 调用同样打这个地址）。多开 ssh 会有 `bind: Address already in use` 提示，无害。ComfyUI 保持 `--listen 127.0.0.1`，不暴露公网。备选：AutoDL 控制台"自定义服务"（需 `--listen 0.0.0.0 --port 6006`），不必要。

## 5 配套 skill 分工（实体在 `.claude/skills/`，`.agents/skills/` 建同名软链接供 Codex 发现）


| skill | 职责 | 复用 |
|---|---|---|
| `reference-video-director` | 视频探针与哈希 → 候选切点 → 粗／密抽帧 → 主体动作、构图、镜头与剪辑分层 → 匹配时间码差异报告 | 已建；FFmpeg 零额外 Python 依赖；内置中文导演知识库，不把 optical flow 或 scene score 自动当成导演结论 |
| `h3-prompt` | 把批准后的导演分析改写成 H3 三段式（含 R2V 六段式）；校验时间戳递增、17k+5、(Sx) 一致、`<d>` 语言标签 | 规范来自 MiniMax 官方 prompt 指南（本仓提炼见 `docs/guide/H3_PROMPT.md`）；只消费分析结论，不自行臆测参考片 |
| `comfy-run` | 把 `t2v/` 的纪律写成 skill：dry-run → 报价 → 确认 → 提交 → 写 PROGRESS | 命令表已备在 `t2v/README.md`；可借鉴 ComfyUI-Expert 的 inventory 校验 |
| `blender-previz` | 从分镜表生成 bpy 脚本：灰盒场景 + 相机关键帧 → headless 渲染参考视频/首尾帧 | 见 §5 |
| （上级技能不复用） | — | H3 原生出声，`overall_soundscape` / `non_diegetic_music` 字段由 `h3-prompt` 一并产出 |


建设状态：`reference-video-director` 与 `character-design-director` 已建，
`h3-prompt` / `comfy-run` / `blender-previz` 待建。目录规则：`.claude/skills/` 是唯一实体目录，
`.agents/skills/` 只放指向它的相对软链接（见 README 的「跨客户端单一来源」）。

## 来源

- https://docs.comfy.org/tutorials/video/minimax/minimax-h3
- https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md
- https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md
- https://github.com/nkxx188/ComfyUI-MiniMaxH3-Easy
- https://github.com/SlavaSexton/ComfyUI-Agent-Kit
- https://github.com/MCKRUZ/ComfyUI-Expert
- https://github.com/Comfy-Org/ComfyUI/discussions/13283
- https://github.com/ahujasid/blender-mcp
- https://toonkit.io/en/models/seedance-blender
- https://tesseract.academy/from-blender-to-ai-video-a-faster-creative-workflow/
