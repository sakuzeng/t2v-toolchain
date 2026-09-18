# 5090 32G 上 H3 显存的真相（2026-09-06）

> 起因：R2V 480p 旁路记到峰值 28.2G，担心 768p OOM。实测 768p 峰值 24.7G、无 OOM。结论与依据如下。

## 结论
1. ComfyUI 在 torch ≥ 2.8 + NVIDIA（非 WSL）上默认启用 **DynamicVRAM**：权重分块按需进显存，放不下的留在系统内存，`nvidia-smi` 看到的是「有多少用多少」，不是任务的最小需求。本机 92G 内存足够兜底。
2. 官方 Ref2VA pruned int8 在 12G 卡上也能出 1344×768（社区实测 11.6G 显存 + 43G 内存），代价只是慢。
3. 因此 5090 上 T2V / I2V / R2V 的 768p 都直接跑；**1080p 级（1952×1120）已实测通过，峰值 25.3G，耗时 25 分钟**（`ops/BASELINE.md` #7）。2K 未测。
4. 真遇到 OOM 的处理顺序：`--disable-pinned-memory`（社区反馈可降内存约 30G、修复 0.30.x 加载慢）→ `--reserve-vram 2` → `--lowvram`；参考图用默认 `ref_image_size=match`（按生成像素面积缩小），`max`（短边 2048）会让参考 token 数倍增加、每步都更慢。
5. 本机实测（`ops/BASELINE.md`）：T2V 768p 瞬时 32.1G（换模瞬间）、R2V 480p 28.2G、R2V 768p 24.7G —— 三个数互相矛盾恰恰说明它们是缓存占用，不是需求。

## 来源
- ComfyUI 显存参数与 DynamicVRAM 说明：https://www.instasd.com/post/comfyui-vram-offloading-guide
- H3 显存/内存实测（含 Ref2VA 12G 卡出 768p）：https://www.minimaxh3tutorial.com/vram 、https://github.com/iSk2y/awesome-minimax-h3
- `--disable-pinned-memory` 降内存约 29.5G 的实测：https://note.com/sepiablue/n/n9bc6fad6eae9
- Blackwell 上 pinned memory / VAE 解码问题：https://github.com/Comfy-Org/ComfyUI/issues/15337 、https://github.com/Comfy-Org/ComfyUI/issues/15488
- 官方教程：https://docs.comfy.org/tutorials/video/minimax/minimax-h3 、https://comfyui-wiki.com/en/tutorial/advanced/video/minimax/minimax-h3
