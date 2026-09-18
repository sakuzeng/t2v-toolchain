# MiniMax H3 加速方案调研（2026-09-05）

> 目标卡：RTX 5090 32GB（sm_120，Blackwell）。环境：torch 2.8.0+cu128 / Python 3.12 / ComfyUI v0.34.5。
> 结论先行：**先跑通原生工作流拿基线，再逐个 A/B 加速项（同 prompt 同 seed 对比）**，不要一上来全开。

## 0 推荐组合（按收益/风险排序）

| 优先 | 方案 | 预期收益 | 质量代价 | 装在哪 | 备注 |
|---|---|---|---|---|---|
| 1 | 步数 20 → 14 | −19% | 肉眼无差（社区 1080p 实测） | 采样器参数 | 零成本，先做 |
| 2 | 条件/潜变量磁盘缓存（encode once, sample many seeds） | 同一镜头换 seed 时 **每次省掉文本编码器加载+编码**，24GB 卡实测 950s→96s | 无损（bit 一致） | 自定义节点 pepikir/minimax-h3-speedup | 与本仓库"一镜多跑挑 seed"节奏最匹配 |
| 3 | SageAttention 2.2 | 5090 上报告不一：0%、19%、31% | 基本无 | **GPU 机**，wheel 绑架构 | 见 §2，需自己编译 |
| 4 | Spectrum（xmarre/ComfyUI-Spectrum-MiniMax-H3） | ~1.3× | 非 bit 一致但社区评"无可见损失"；可能影响运动 | 自定义节点 | H3 专用，与 Sage 叠加 1.78× |
| 5 | TeaCache（Icyoung/ComfyUI-MiniMaxH3-TeaCache） | 作者称 3×（GA100 上） | 默认阈值"A/B 看不出" | 自定义节点，纯 Python | 用官方 wrapper API，不改核心；待更多实测 |
| 6 | ComfyUI 内置 EasyCache | 1.44× | **有隐性损失**：后段跳步引入颗粒；`end_percent` 压到 0.70 后剩 1.14× | 内置节点 | H3 上不推荐做首选 |
| 7 | Turbo LoRA（8 步 / 4 步） | 8 步约 2×+ | **4 步音频崩成白噪声；8 步音频 RMS 掉到 0.028（基线 0.100）**，对白不可用 | 已下载 | 只用于无声/纯画面冒烟，正片不用 |
| ✗ | lihaoyun6/ComfyUI-MiniMaxH3-Cache | — | README 自认"patches ComfyUI core files"，官方 wiki 点名别装 | — | 禁用 |
| ✗ | T8mars 的 BlockCache | 1.09× | 近似 | — | 收益太小 |

后期环节另有一项：超分用 NVIDIA RTX VSR 节点（Comfy-Org/Nvidia_RTX_Nodes_ComfyUI）替代 Real-ESRGAN，1080p 上 109s → 11s，仅 x86_64。

## 1 关键实测数据（社区）

- 5090 + int8 剪枝 + NVFP4 编码器，1344×768 / 56 帧：20 步 48s，4 步 Turbo 16s（HF 讨论 #26，torch 2.10+cu130）。
- 5090，720×720 / 124 帧 20 步 137s；260 帧 395s；峰值显存稳定在 ~31GB（zenn 基准）。**32GB 卡是贴着上限跑的**，Blender 等其他显存占用要清掉。
- 5090 15s 1080p 全流程：625s → 314s（14 步 + Sage 2.2.0 + RTX VSR）。
- 帧数须满足 `17n+5`（如 124、260），不合规会被自动改。
- 同图重复提交会命中 ComfyUI 缓存瞬间返回，做基准时要换 seed。

## 2 SageAttention 在 5090 + torch 2.8 上的安装问题

- PyPI 的 `sageattention` 是 1.0.6 老内核，**不能用**；要 2.2.x。
- ComfyUI 的 `--use-sage-attention` 只认包名 `sageattention`，不认 `sageattn3`。
- 预编译 Linux wheel 现状（2026-09-05 查 HF `yo9otatara/prebuilt_wheels`）：有 `cu128torch2.7.0sm120-cp312` 和 `cu128torch2.10.0sm120-cp312`，**没有 torch 2.8 的**。wheel 与 torch 小版本绑定，跨版本大概率 `undefined symbol` 或 no kernel image。
- 因此方案：在 5090 上从源码编译（thu-ml/SageAttention，`pip install -c constraints.h3.txt --no-build-isolation .`，需 nvcc 12.8，约 10–20 分钟），或者放弃 Sage 改用 Spectrum/TeaCache。
- H3 有部分层不在 Sage 支持的 FP16/BF16 dtype 内，控制台会打印 fallback 到 PyTorch 的提示，属正常。
- 编译产物 wheel 留在数据盘 `/root/autodl-tmp/wheels/`，同卡型换实例可复用。

## 3 与本仓库流程的对接

- 基线：官方模板 `video_minimax_h3_i2v` / `t2v` / `multiframe_reference`，20 步 `res_multistep + simple`，不带任何加速，先出一条 5s 384p、一条 5s 768p，记录时间与显存 → 写入 `ops/PITFALLS.md`/`status/STATUS.md`。
- 迭代：同镜头多 seed 时用磁盘缓存节点，步数 14；对白镜头禁用 Turbo LoRA。
- 出片：关闭 Spectrum/TeaCache 再跑最终版（近似加速只用于挑 seed 与构图）。

## 来源
- https://zenn.dev/toki_mwc/articles/minimax-h3-rtx5090-benchmark
- https://ai-muninn.com/en/blog/minimax-h3-rtx5090-speedup-vsr
- https://huggingface.co/Comfy-Org/MiniMax-H3/discussions/26
- https://github.com/pepikir/minimax-h3-speedup
- https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3
- https://github.com/Icyoung/ComfyUI-MiniMaxH3-TeaCache
- https://github.com/lihaoyun6/ComfyUI-MiniMaxH3-Cache
- https://comfy.icu/node/MiniMaxH3BlockCacheT8
- https://kingy.ai/ai/ai-guides/minimax-h3-comfyui-local-guide/
- https://huggingface.co/yo9otatara/prebuilt_wheels
