# H3 权重手册（每个文件干什么、谁加载它）

> 常青手册。清单的**唯一真值**是 `scripts/remote/models/h3/manifest.txt`（sha256 + 字节数 + ComfyUI 内相对路径），
> 下载脚本按它校验；本文解释"为什么需要这些文件、它们在链路里的位置"。
> 体积/选型取舍的**当时判断**在 `plan/PLAN.md` §1；加速项取舍见 `research/ACCEL.md`。

MiniMax H3 是**全模态**模型：一次采样同时产出画面与 32 kHz 立体声，所以它不是单个 ckpt，
而是「扩散主干 + 文本/视觉编码器 + 两套 VAE（+ 可选加速 LoRA、可选风格 embedding）」。官方推荐组合 **17 个文件 ≈ 62.7 GB**。

## 1 `diffusion_models/` —— 主干（2 个，**二选一**）

| 文件 | 体积 | 作用 |
|---|---|---|
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | 19.53G | **FL2VA**（首帧/尾帧 → 视频+音频）：T2V、I2V、首帧/尾帧/首尾帧都走它 |
| `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | 19.53G | **REF2VA**（参考 → 视频+音频）：≤9 图 / ≤3 视频 / ≤3 音频做参考，保角色、风格、动作、声线（R2V 六段式那条路线） |

同一个 33.1B 单流 omni transformer 的**两个条件化分支**，不叠加使用。命名含义：

- `pruned` = 剪枝版 19.5G；未剪枝 int8 是 31.7G、bf16 是 61.7G（**都没下**）。
- `int8_convrot` = int8 量化 + ConvRot 旋转，压到约 1/3 体积仍保画质。

加载节点：`UNETLoader`（`workflows/h3/t2v.api.json` 里 `140:127`；R2V 图换成 ref2va）。

## 2 `text_encoders/` —— 条件编码（1 个）

| 文件 | 体积 | 作用 |
|---|---|---|
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 14.61G | **Qwen3-VL-32B**：把三段式 prompt（R2V 时还有参考图）编码成主干的条件向量 |

`nvfp4 + awq` = 4bit 浮点 + AWQ 量化；未量化 bf16 要 48G、int8 是 25.3G。官方口径"任何卡可跑"，
老卡走**软件反量化**——Ampere（A6000，sm_86）没有 fp4 硬件，这条路径是实验室链路的观察点。

加载节点：`CLIPLoader`（`140:128`）。

## 3 `vae/` —— 潜空间互转（2 个，**都必须有**）

| 文件 | 体积 | 作用 |
|---|---|---|
| `minimax_h3_video_vae_fp16.safetensors` | 4.85G | 画面 VAE：视频 latent ↔ 像素；解码出帧序列，I2V 时还要把首帧编码进去 |
| `minimax_h3_audio_vae_fp32.safetensors` | 0.56G | 声音 VAE：音频支路 latent ↔ 32 kHz 波形。**缺了它出片没有声音** |

加载节点：两个 `VAELoader`（`140:119`/`140:120`）分别喂 `VAEDecode` 与 `VAEDecodeAudio`。

## 4 `loras/` —— 少步加速（2 个，可选）

| 文件 | 体积 | 作用 |
|---|---|---|
| `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` | 1.82G | FL2VA 的 Turbo 蒸馏：20 步 → **8 步** |
| `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` | 1.82G | REF2VA 的 Turbo：20 步 → **4 步** |

来自 `lightx2v/Minimax-h3-Turbo`；加载节点 `LoraLoaderModelOnly`。两条纪律：
**带对白的镜头禁用 Turbo（音频会崩）**；加速项只在基线跑通后同 seed 逐个 A/B，正式出片关掉（见铁律 6）。

## 5 `embeddings/` —— 10 个风格词条（各 0.5–1.4 MB，可选）

官方在模板说明里写明：这是可复用的风格 token，**在 prompt 正文里用 `embedding:<文件名不含扩展名>` 引用**，例如
`embedding:minimaxh3_bullet_time`（ComfyUI 自 #15697 支持）；**不引用也完全能跑**。

| 词条 | 按命名推断的效果 |
|---|---|
| `minimaxh3_art_is_explosion` | 画面炸裂/泼溅成艺术质感 |
| `minimaxh3_blooming_flowers` | 花朵绽放 |
| `minimaxh3_bullet_time` | 子弹时间（时间凝固 + 绕拍） |
| `minimaxh3_dark_magic` | 暗黑魔法特效 |
| `minimaxh3_fire_breath` | 喷火/吐息 |
| `minimaxh3_four_seasons` | 四季在同一画面流转 |
| `minimaxh3_kiss_camera` | 贴脸/怼镜头 |
| `minimaxh3_spiral_ascent` | 螺旋上升运镜 |
| `minimaxh3_storm_magic` | 风暴魔法特效 |
| `minimaxh3_truman_show` | "楚门的世界"式布景破绽揭示 |

> 「效果」一列是**按文件名推断**，不是官方逐条说明；要用某个词条时先小样验证。

## 6 组合矩阵：一条镜头到底要哪些

| 路线 | 必需 | 可选加速 | 所在图 |
|---|---|---|---|
| T2V | fl2va + 文本编码器 + 视频 VAE + 音频 VAE | fl2v turbo 8step | `workflows/h3/t2v.api.json` |
| I2V / 首尾帧 | 同上（首帧走项目级 `first_frame`） | 同上 | 同上 |
| R2V | **ref2va** + 文本编码器 + 两个 VAE | ref2v turbo 4step | `workflows/h3/r2v.api.json` |

10 个 embedding 与 LoRA 都是"备用弹药"，缺了不影响链路跑通。

## 7 为什么是这个体积档

官方给三档：主干 19.5 / 31.7 / 61.7G，编码器 14.6 / 25.3 / 48G。选最省的一档是因为在 5090 32G / A6000 48G 上，
`int8 剪枝 + nvfp4 编码器`是**唯一能同时装下主干与编码器并给激活留出显存**的组合（换模瞬间几乎打满，见 `ops/BASELINE.md` 观察段）。

## 8 校验与重下

```bash
# AutoDL 侧（aria2）
bash scripts/remote/models/h3/download.sh --verify-only
# 实验室容器（curl 分块并发）
SRC=modelscope bash scripts/lab/models_download.sh --verify-only
```

两者都用同一份 `manifest.txt`，校验通过写 `<文件>.sha256.ok`（内容为 sha256），带这个标记的文件会被跳过。

## 9 H3 之外的权重：FLUX.2 [klein] 9B（出图，2026-09-18 起）

H3 只出视频；I2V 项目（`projects/sunset-sofa/`）的 7 张图（1 张场景底板 + 6 张首帧图）由
**FLUX.2 [klein] 9B** 在远端 ComfyUI 生成。清单与下载口径在
`scripts/remote/models/flux2/`（`manifest.txt` + `README.md`），与 H3 的 17 个文件互不依赖。

| 文件 | 体积 | 作用 |
|---|---|---|
| `diffusion_models/flux-2-klein-9b.safetensors` | 18.16G | 主干：4 步蒸馏，统一文生图 / 编辑 / **多参考图** |
| `text_encoders/qwen_3_8b_fp8mixed.safetensors` | 8.66G | 文本编码器（Qwen3-8B；4B 版配 `qwen_3_4b`） |
| `vae/flux2-vae.safetensors` | 0.34G | VAE |

- **主干在 HF 上是 gated 的**（要接受许可 + token），ModelScope 有公开镜像，所以 `SRC=modelscope` 直接下。
- 一卡一套：**不要在同一张卡上同时加载 H3 与 klein**（显存互相挤）；出图与出片分卡跑。
- 引擎入口：`python3 -m t2v flux <项目> <生图 prompt>`（`t2v/engines/flux/`），最小 API 图只用
  ComfyUI 核心节点（`ReferenceLatent` / `Flux2Scheduler` / `EmptyFlux2LatentImage` 等），
  **不需要**那份社区 355 节点画布依赖的 Easy-Use / LayerStyle / Comfyroll。
