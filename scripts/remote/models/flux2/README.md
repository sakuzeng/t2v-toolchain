# FLUX.2 [klein] 9B —— 生图权重（I2V 首帧图的来源）

MiniMax H3 只出视频，**出图是另一条链路**：本项目（`projects/sunset-sofa/`）的 7 张图
（1 张场景底板 + 6 张首帧图）由远端 ComfyUI + FLUX.2 [klein] 生成。这里只放权重清单与下载口径；
节点接线与 `flux` 引擎见 `t2v/engines/flux/` 与 `docs/guide/COMFYUI.md`。

## 三个文件、各自干什么

| 文件 | 体积 | 作用 |
|---|---|---|
| `diffusion_models/flux-2-klein-9b.safetensors` | 18.16G | **主干**：FLUX.2 [klein] 9B，4 步蒸馏，统一「文生图 + 图像编辑 + 多参考图」 |
| `text_encoders/qwen_3_8b_fp8mixed.safetensors` | 8.66G | **文本编码器**：Qwen3-8B（klein 系列的配对编码器；4B 版用 `qwen_3_4b`） |
| `vae/flux2-vae.safetensors` | 0.34G | **VAE**：FLUX.2 的潜在空间编解码，生成与编辑共用 |

合计约 **27.2 GB**。

### 为什么是这个档

- **9B 蒸馏版**：4 步出图，A6000 上没有 fp8/fp4 张量核（sm_86），算力提升拿不到，
  但**步数少**是实打实的——这是本地抽卡最划算的一档。要更高上限可换同仓库的 **base 9B**（50 步，慢一个量级）。
- **主干默认下 bf16 而不是 fp8mixed**：48G 显存不缺，量化只省显存不提速，白丢一点画质。
  想省一半下载量就把清单第一行换成 fp8 那份（见 `manifest.txt` 顶部注释）。
- **文本编码器下 fp8mixed**：文本编码对量化不敏感，省 7.7 GB。
- **许可**：9B 系列是 FLUX 非商用许可（NCL）；**4B 才是 Apache 2.0**。个人创作项目不受影响，
  要商用就换 4B（`Comfy-Org/flux2-klein` 那个仓库，另需 `qwen_3_4b` 编码器）。

## 下载（读 `manifest.txt`，sha256 校验、断点续传）

```bash
# 实验室容器：curl 分块并发（比 aria2 快一个量级，见 docs/ops/PITFALLS.md #19）
SRC=modelscope WORKERS=16 \
MANIFEST=~/workspace/remote_t2v/scripts/remote/models/flux2/manifest.txt \
  bash ~/workspace/remote_t2v/scripts/lab/models_download.sh

# 只校验（不下载）
SRC=modelscope \
MANIFEST=~/workspace/remote_t2v/scripts/remote/models/flux2/manifest.txt \
  bash ~/workspace/remote_t2v/scripts/lab/models_download.sh --verify-only
```

- 清单里每行都带**仓库列**，所以一份清单一趟能把 BFL 主干与 Comfy-Org 的编码器/VAE 一起下完，
  不用分两次跑（这是 2026-09-18 给 `fetch_manifest.py` 加的：`sha 字节 落盘路径 [仓库内路径] [仓库]`）。
- **主干在 HF 上是 gated 的**（网页上接受许可 + token 才能下），所以走 ModelScope 公开镜像。
- AutoDL 侧目前只有 H3 的 aria2 脚本；要在 AutoDL 出图，先按同样清单跑
  `python3 scripts/lab/fetch_manifest.py --manifest … --repo …`（该脚本只依赖 python3 + curl）。

## 与 H3 权重的关系

两套权重互不依赖、可共存：H3 占 `diffusion_models/minimax_h3_*`、`text_encoders/qwen3vl_32b_*`、
`vae/minimax_h3_*`；klein 占上表三个文件。**同一张卡不要同时加载两套**（合计显存会互相挤），
出图与出片建议分卡跑（同一张卡同时加载两套权重会互相挤显存）。
