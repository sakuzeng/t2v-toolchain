# 动作迁移路线取舍：C001A 之后该用什么复刻参考片（2026-09-08）

> 2026-09-16 代码整理说明：下文提出的 `scripts/comfy_run.py`、`tools/t2v.py` 等路径是当时方案；现有 H3/SCAIL-2 命令统一经 `python3 -m t2v` 调用。赤翎深度控制路线已停用，SCAIL-2 已有独立实验入口。

## 一、结论先行

目标一旦定义为“动作、时序、运镜尽量贴近参考片”，H3 的“文字 + 深度控制片 → 重新生成”就不是主路线：`chiling-ink-sword` C001A 从 v004 到 v017 十余轮、约 ¥3 的实验证明，深度轮廓只能约束占位与先后，表达不了膝—胫—踝的关节时序，H3 会把缺失的证据补成最常见的“弯腿放下、双脚并排站定”。

候选替代路线四条，按本镜头的适配度排序：

| 路线 | 驱动信号 | 背景 / 机位 | 本镜头的致命点 | 结论 |
|---|---|---|---|---|
| **SCAIL-2 角色替换**（智谱，2026-06，MIT；ComfyUI 核心节点 `WanSCAILToVideo` + `SAM3_VideoTrack`，模板 `video_wan21_scail2_character_replacement_int8`） | 参考片原始帧 + SAM3 人物彩色 mask，**不抽骨架** | 替换模式保留参考片背景与机位，逐帧时序天然一致 | 单张主参考图 + 可附加近景/背面视图；服装剪影可能被原表演者牵制 | **主路线** |
| Wan Animate 2（Comfy-Org 打包，`WanAnimate2ToVideo`） | 参考片原始帧，不抽骨架 | 官方说明：背景与相机由 prompt 生成，**与驱动视频解耦** | 会丢掉“低机位空湖 → 快速上摇”的机位与湖景真值 | 只作动画模式备选 |
| Wan 2.2 Animate v1 角色替换（另一软件提议的路线，`WanAnimateToVideo`） | DWPose 骨架 + 人物 mask + 面部裁切 | 保留背景与机位 | 本机探针证明 0–1.4 s 自动骨架不可用（见下），需人工标注约 35 帧腿部关键点 | 被 SCAIL-2 取代；仅当 SCAIL-2 失败且愿意手标骨架时再回头 |
| H3 R2V `<Video 1>` + FunControl pose/HED | 源片语义参考 + 源派生结构片 | 保留节奏但不保证逐关节 | PITFALLS #9：`<Video 1>` 会把原表演者的白袍赤足带回来；pose 同样受骨架失效影响 | 不再为此付费试错 |

H3 保留的职责：水墨风统一、局部重绘、短镜补帧，以及不依赖参考片的原创镜头。

## 二、为什么“先抽骨架”在本镜头行不通（实测）

探针：`projects/chiling-ink-sword/references/analysis/c001a/20260908-dwpose-partial-body-probe/`（rtmlib Wholebody，正常检测与强制整帧两种跑法）。

- 空湖无人帧（0–0.38 s）膝踝置信度 0.25–0.38，检测器仍报“1 人”；腿部入画帧（0.42–0.75 s）0.23–0.39，与空场无法区分，f16 只画出一条腿。
- 0.79–1.40 s 腿在正确位置，但同时把画外的肩、臂、头幻觉进画面；上摇模糊段与近景段骨架散乱。
- 结论：任何以 OpenPose 骨架为硬输入的路线，在这条镜头上都必须先解决“无骨架可用”的问题；SCAIL-2 / Wan Animate 2 的端到端驱动直接绕开它。

## 三、SCAIL-2 需要什么（已核对模板与节点源码）

**节点**：`WanSCAILToVideo`、`SCAIL2ColoredMask`、`SAM3_VideoTrack` 全部在 ComfyUI 核心（本机 `third/ComfyUI` v0.34.0 已含 `comfy_extras/nodes_scail.py`、`nodes_sam3.py`；远端 v0.34.5 应已具备，开机后第一件事是核对）。无需第三方插件，避开护栏与 `IMPORT FAILED` 风险。

**关键输入**（`WanSCAILToVideo`）：`pose_video`（驱动视频，内部降到一半分辨率）、`pose_video_mask`（SAM3 彩色身份 mask；替换模式白底）、`reference_image` + `reference_image_mask`（首张为主参考，**后续批次图作为附加视图：背面、近景、被遮挡背景**，各配同色 mask）、`replacement_mode`、`pose_strength/pose_start/pose_end`、`length`（4n+1）、宽高需 32 的倍数。

**权重（int8 模板默认，ModelScope 有同名镜像）**：

| 文件 | 目录 | 大小 |
|---|---|---|
| `wan2.1_14B_SCAIL_2_int8_convrot.safetensors` | diffusion_models | 15.5 GB |
| `wan2.1_SCAIL_2_DPO_lora_bf16.safetensors` | loras | 1.1 GB |
| `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors` | loras | 0.7 GB |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | text_encoders | 6.3 GB |
| `clip_vision_h.safetensors` | clip_vision | 1.2 GB |
| `Wan2_1_VAE_bf16.safetensors` | vae | 0.25 GB |
| `sam3.1_multiplex_fp16.safetensors` | checkpoints | 1.6 GB |
| 合计 | | **≈ 26.7 GB**（可选 relight LoRA 再 +1.1 GB） |

来源：`Comfy-Org/SCAIL-2`、`Comfy-Org/sam3.1`、`Comfy-Org/Wan_2.1_ComfyUI_repackaged`（HF 与 ModelScope 均已确认存在、大小一致）。

**磁盘**：远端数据盘 120 G 已用 78 G，余约 42 G；装完剩约 15 G，够 480p 产物与临时文件，但不要再装第二套 14B（Wan Animate 2 int8 另需 15.5 GB，与 SCAIL-2 二选一）。

**显存**：14B int8 权重约 15.5 G + umt5 fp8 分时加载，480p 级 69 帧在 32 G 5090 上应可跑（`--lowvram` 已启用）；模板默认 turbo 预设（lightx2v 蒸馏 LoRA 0.8、6 步、CFG 1、shift 5），非 turbo 为 40 步 / CFG 5。

**参数对齐 C001A**：驱动片 `references/clips/c001a/reference.mp4` 恰为 69 帧（4×17+1 ✓）、864×480（均为 32 的倍数 ✓）、24 fps；单段即可，无需 extend 子图。

## 四、分阶段执行（每段都有止损门）

| 阶段 | 内容 | 费用 | 门槛 |
|---|---|---|---|
| 0 本地准备（零费用） | 参考图与视图选择（主参考全身 v8 + 近景正脸 v1 + 裙靴 v1 作附加视图）、SCAIL 风格 prompt 草稿、SAM3 词、参数表；写入 `projects/chiling-ink-sword/experiments/scail2-c001a/` | 0 | 用户确认路线与三项创作决定（见五） |
| 1 远端就绪（开机即计费） | 核对 v0.34.5 含 SCAIL/SAM3 节点 → 下载 26.7 GB（ModelScope 镜像，sha256 校验）→ 浏览器载入模板、导出 API 版到 `workflows/` → 只跑 SAM3 追踪预览核对 mask | 约 15–30 分钟机时 ≈ ¥0.7–1.4 | mask 覆盖人物与裙摆、不吃鹤与倒影 |
| 2 首次小样（付费） | 864×480 × 69 帧、turbo 预设、替换模式，一次 | 预计 3–6 分钟 ≈ ¥0.15–0.30（待实测校准） | 用 `reference-video-director` 匹配时间码对比 + `check_acceptance.py`；重点看左先右后、右腿摆入交叠、脚尖触水、身份/服装 |
| 3 迭代 | 调 `pose_strength`、参考视图组合、prompt；必要时非 turbo 40 步复跑一次 | 每次 ¥0.15–2 | 通过则 promote，再用同链路做 C001B |

## 五、需要用户先拍板的三件事

1. **背景照搬**：替换模式会原样保留参考片的湖、日、鹤与原机位。v017 的创作覆盖“删除参考片中的鹤”在此路线下需要额外一遍局部修复，或直接接受鹤。
2. **剑**：画面里的剑刃来自参考片（人物 mask 之外），只有近景右上的剑柄可能露出差异；羽翎剑格与红穗在 C001A 基本不可见。若坚持羽翎剑外观，要在后期局部重绘。
3. **服装剪影**：SCAIL-2 会在原表演者的 mask 区域内画赤翎，飘逸白袍与赤足可能牵制黑红开衩裙与长靴的剪影；这是首次小样的主要观察项，接受度由用户定。

## 六、工具链改动（阶段 1 之后）

- `scripts/comfy_run.py` 现只认 H3 R2V/FunControl 图。SCAIL 需新增通用模式：`--workflow <api.json>` + 按节点 id 注入驱动视频、参考图批次、prompt、length、seed；run capsule、费用 sidecar、`runs/index.jsonl` 复用。
- `tools/t2v.py` 的 `engine.mode` 增加 `scail2`；跳过 H3 六字段校验，改校验 4n+1、32 倍数、mask 词、参考视图数。
- `reference-video-director` 的验收脚本不变：对比对象仍是参考片与产物的匹配时间码。

## 来源

- ComfyUI 模板 `video_wan21_scail2_character_replacement_int8.json` 与 `video_wan_animate2.json`（随 `comfyui_workflow_templates` 包）
- ComfyUI 核心 `comfy_extras/nodes_scail.py`、`nodes_sam3.py`、`nodes_wan.py`（`WanAnimateToVideo` / `WanAnimate2ToVideo`）
- SCAIL-2 模型卡：https://huggingface.co/zai-org/SCAIL-2 （端到端驱动、无需骨架、替换/动画双模式、512p/704p、MIT）
- 权重清单：https://huggingface.co/Comfy-Org/SCAIL-2 、https://huggingface.co/Comfy-Org/sam3.1 、https://huggingface.co/Comfy-Org/Wan-Animate-2
- 本仓库：`CAMERA_REPLICATION.md`（2026-09-06 已把 Wan 系动作迁移列为 A 路线失败后的备胎）、`ops/PITFALLS.md` #9/#10
