# 复刻参考片运镜与节奏：路线调研（2026-09-06）

> 问题：`projects/chiling-ink-sword/` 用「分镜表 + 纯文字六段式」复刻水墨舞剑参考片，切点能对上、脸与剑能保住，但**运镜的手感与停顿节奏仍与参考片有差距**；把参考片直接当 `<Video 1>` 喂 R2V 则被整段重绘（三镜里两镜是原表演者）。本文调研「借参考片的运镜/动作，不借外观」有哪些可行路线，给出取舍。

## 〇、2026-09-16 结论更新：路线 A 已否决

> 下文写于 2026-09-06，当时把 **A. H3 Fun ControlNet（深度/姿态控制视频）判为首选**。**这个判断已被实测推翻，本文保留作为当时的取舍记录。**

- **证据**：`chiling-ink-sword` C001A 从 v004 到 v017 十余轮、约 ¥3 的实验（见 `projects/chiling-ink-sword/PROGRESS.md`）。深度轮廓只能约束占位与先后，表达不了膝—胫—踝的关节时序；H3 会把缺失的证据补成最常见的"弯腿放下、双脚并排站定"。
- **更关键的副作用**：在 clean depth 1.0/0.8 下，v007、v008、v009 三版差异很大的 prompt 用同一个 seed 出的产物几乎逐帧一致——**成片的时机与动作阶段由控制片和 seed 决定，文字几乎不参与**。深度控制不只是没帮上忙，它还压掉了 prompt 的作用。
- **当前路线**：无控制 R2V（参考图 + prompt）+ 多 seed 抽卡挑片。效果靠打磨 prompt 的过程描写（动作动力链、先后连词、幅度速度词），不靠逐帧约束。2026-09-16 已从 `t2v/` 删除全部控制片与关键帧锚点代码，`workflows/h3_r2v_funcontrol*.api.json` 也不在仓库里。
- **仍然有效的部分**：路线 C（光流量化 → 写进 prompt）现在是主力，入口为 `python3 -m t2v motion`；路线 B（视频编辑/角色替换）的后继调研见 `MOTION_TRANSFER.md`（SCAIL-2）；路线 D（Blender 预演）已放弃：远端虽装了 Blender headless，但 previz 链路从未建起，2026-09-16 连同方案文档与待办一起删除。

---

## 一、结论先行

| 路线 | 原理 | 借到什么 | 代价 | 判断 |
|---|---|---|---|---|
| **A. H3 Fun ControlNet Union（深度/姿态控制视频）** | Alibaba PAI 发布的 H3 视频 ControlNet（6.8 GB，五合一：depth/canny/pose/HED/MLSD）。从参考片抽深度或姿态序列作控制视频，逐帧约束构图、机位与人物动作；身份仍来自参考图，风格来自文字 | 运镜、构图、人物动作、停顿节拍，**逐帧对齐** | 装社区节点 `ComfyUI-H3-FunControl` + Kijai 剪枝版权重 + 预处理器（Depth Anything / DWPose）；显存增加未知（5090 需实测）；控制强度要调 | **首选**。这是「借结构不借外观」的正解，且与现有 ref2va 双图/三图链路直接叠加 |
| **B. 视频编辑模式（角色替换）** | 官方 `[video editing]` 任务：`The target video is an edited version of <Video 1>`，只换表演者。社区有 SAM3 抠人 + Ref2VA 的成熟工作流 | 参考片的一切：运镜、停顿、墨效、光 | 产物几乎就是参考片换皮：场景/白鹤/墨效全是别人的；鹤要靠 prompt 删，未必删得掉；**版权与原创性问题** | 技术上最省事、效果最像，但成片等于重绘他人作品，只适合做研究对照或私用 |
| **C. 纯文字 + 量化分析** | 用光流工具把参考片每镜的运镜类型/速度/停顿量化成数据，写进 prompt（幅度、速度、「静止 0.4 s」等） | 切点、景别、运镜类型、大致节拍 | 零新依赖；但模型对「停顿多久、摇多快」执行是概率性的，需抽卡 | 已在做（SHOTLIST）。作为 A 的 prompt 底稿继续用，单独不够 |
| **D. Blender 灰盒预演** | 在 Blender 里摆人偶与相机关键帧，渲染 → 当 A 的**深度控制视频**（渲染深度通道最干净），或当 `<Video 1>` | 精确相机轨迹与人物位置 | 要手动做舞剑动作的关键帧，工作量大；直接当 `<Video 1>` 未在 H3 上验证（可能出灰盒画面） | 只在「想要参考片里没有的机位」时用；深度输出走 A |
| **E. 换模型（Wan Animate 2 / Uni3C / MoCha）** | Wan 2.1/2.2 系动作迁移与相机迁移专用模型 | 动作与相机迁移成熟 | 另下 30–60 GB、另建工作流、无原生音频、画风与 H3 不一致 | 备胎，A 失败再考虑 |

**推荐顺序**：A（ControlNet 深度/姿态）为主，C 的分镜表与量化数据作 prompt 底稿；B 只做一条对照看上限；D/E 不做。

## 二、各路线细节

### A. MiniMax-H3-Fun-Controlnet-Union
- 权重：`alibaba-pai/MiniMax-H3-Fun-Controlnet-Union`（6.8 GB，只含控制分支 `control_proj_in` + 5 个 `control_blocks`，叠在 H3 transformer 上）。ComfyUI 节点要求 **Kijai 的 curve 剪枝版** `minimax_h3_fun_controlnet_union_pruned_bf16.safetensors`（放 `models/controlnet`），原版会被 loader 拒绝。
- 节点：`wyzborrero/ComfyUI-H3-FunControl`，两个节点 `H3 Fun ControlNet Loader` / `H3 Fun ControlNet Apply`（strength、start/end 百分比），无额外 Python 依赖。它 patch 的是 model 不是 conditioning，所以 **fl2va 与 ref2va 都能接**，作者主要在 ref2va 上测过——即可与 `MiniMaxH3ReferenceToVideo` 的三图（脸/全身/剑）同用。
- 控制视频：IMAGE 批（尺寸需匹配），来源可以是估计器跑参考片、3D 渲染、手绘。作者只验证过 depth 与 pose；**pose 比 depth 更能维持人物尺度**，链式叠加时强度相加（depth 0.3 + pose 0.7 可用，1.0+1.0 饱和），**end 设到约 0.6** 给后段留纹理，CFG 4.0 附着更好，strength > 1.0 无益。
- 分辩率约束：控制权取决于 token 分辩率，「约 100 px 高的人物只占 22 个竖向 token 中的 3 个」——大远景里的小人控制力弱，中近景强；480p 试验要注意这点。
- 已知坑：Sol-Attn 的 `morton: true` 会**静默破坏**控制，用 `morton: false`。
- 预处理器：Depth Anything（V2）与 DWPose 的 ComfyUI 节点（`comfyui_controlnet_aux` 一类），装法照 `docs/guide/COMFYUI.md` 的插件纪律：带 constraints 护栏，装完看启动日志有没有 `IMPORT FAILED`。
- 未知项（需 5090 实测）：显存增量、480p→1080p 的控制力、水墨风格下 depth 与 pose 哪个更合适（墨效不是刚体，depth 会把墨浪也约束住，pose 只约束人）。

### B. 视频编辑 / 角色替换
- 官方参考模式指南支持 `[video editing + reference generation]`，summary 首句写 `The target video is an edited version of <Video 1>.`，`<Video 1>` 用 `fully_preserved`（保留剪辑/镜头/时序），`<Subject 1>` 换人。
- 社区工作流（RunComfy「MiniMax H3 Character Replacement」）：SAM3 按文字「person」逐帧抠出表演者 → `ImageCompositeMasked` 做「以表演者为中心的参考」→ Ref2VA；prompt 只描述新身份与服装，并要求保留原动作与场景。给出的经验：mask 干净则光晕少、场景光照要稳。
- 对本项目的含义：我们的「泄漏」其实就是这条路线的正常行为；若接受「成片=参考片换皮」，它是效果上限。但白鹤、赤足、背剑这些要改的点在编辑模式里更难改（模型倾向保留原片），且原创性存疑。

### C. 参考片运镜与停顿的量化
- 工具：`antiboredom/camera-motion-detector`（OpenCV 光流 → 每帧平均运动角度/幅度/缩放因子 CSV，判摇/移/推拉）；帧差能量曲线判「停顿」（能量接近 0 的连续帧）。本机装 `opencv-python-headless` 即可（`workon text2video` 后 pip 装）。
- 产出：在 `SHOTLIST.md` 每镜加两列——运镜量化（如「上摇 large/fast，0.4 s 内完成」）与停顿点（如「1.2–1.6 s 定格」）；prompt 里对应写成 `tilts up with large amplitude at fast speed within half a second, then holds motionless for about half a second`。
- 局限：文字对时长与速度是软约束；它是 A 的底稿，不是替代。

### D. Blender
- 社区（Toonkit、Seele、arXiv 2608.00094）验证过「灰盒渲染当参考视频，AI 保留相机轨迹并补材质」，但验证对象是 Seedance 等；H3 的 R2V 视频输入会重绘输入画面，灰盒进去可能出灰盒。
- 更稳的用法：Blender 渲染**深度通道**（Z pass）作 A 的控制视频——相机轨迹、人物位置精确可控，且没有任何可被抄的外观。前提是要在 Blender 里做出舞剑动作，成本高；只值得用于参考片里没有、我们想自己设计的镜头。
- 远端装有 Blender headless 4.5.13，但 previz 链路始终没建；2026-09-16 连同方案文档一起放弃。

### E. Wan 系动作/相机迁移
- Wan Animate 2（端到端动作迁移，无需抽骨架，身份保持强，可独立控相机）、Uni3C（Wan2.1 I2V 14B + 控制模块，复制任意视频的相机运动，需 6 个模型、建议 48 GB）、MoCha（Wan2.1 14B，实拍视频换角色）。
- 与 H3 不同栈：另下几十 GB，无原生音频，画风不一致。只在 A 完全失败时考虑。

## 三、对本项目的执行计划（等开机）
1. **本机（免费）**：`workon text2video` 装 `opencv-python-headless`，跑光流/帧差脚本得到参考片每镜运镜量化与停顿表，写进 `SHOTLIST.md`。
2. ~~**远端（开机后）**：装 `ComfyUI-H3-FunControl` + Kijai 剪枝权重 + Depth Anything / DWPose 预处理节点（带护栏，看 `IMPORT FAILED`）；把当时的 `workflows/h3_r2v_official.api.json`（现 `workflows/h3/r2v.api.json`）复制成 `h3_r2v_funcontrol.api.json` 插入 Loader/Apply 两节点；`comfy_run.py` 加 `--control-video`（IMAGE 批）与 `--control-strength/--control-end`。~~（已执行并于 2026-09-16 全部回退，见文首结论更新）
3. **对照实验（480p，各约 5 分钟）**：同 C01、同 seed——① 纯文字（现状）② pose 0.7 + end 0.6 ③ depth 0.5 ④ depth 0.3 + pose 0.7。看运镜/停顿贴合度、脸与剑保持、墨效是否被深度「冻住」。
4. **可选对照**：B 路线跑一条 C01 看效果上限，仅作研究对照。
5. 选定配置后按 SHOTLIST 分条出 C02–C11，每条先 480p 后 1080p。

## 四、技能建设建议
- `h3-prompt` 技能加一道**必做的参考分析阶段**：场景检测 → 每镜中间帧 → 光流量化 → SHOTLIST（景别/机位/运镜/动作/墨效/停顿）→ 再写六段式；运镜词汇表从上级 `film-director/references/film-grammar.md` 摘「机位与信息」「运镜」段落。
- `comfy-run` 技能收录本次经验：`ref_image_size=max` + 面部裁图；`<Video 1>` 会整段重绘；ControlNet 的强度/end 预算。

## 来源
- Alibaba PAI 权重：https://huggingface.co/alibaba-pai/MiniMax-H3-Fun-Controlnet-Union
- ComfyUI 节点：https://github.com/wyzborrero/ComfyUI-H3-FunControl
- ComfyUI Wiki 新闻（2026-08-24）：https://comfyui-wiki.com/en/news/2026-08-24-minimax-h3-fun-controlnet-union
- RunComfy H3 Fun Control 工作流：https://www.runcomfy.com/comfyui-workflows/minimax-h3-fun-control-in-comfyui-depth-and-pose-video
- RunComfy H3 角色替换（SAM3 + Ref2VA）：https://www.runcomfy.com/comfyui-workflows/minimax-h3-character-replacement-comfyui-sam3-ref2va
- ComfyUI 官方 H3 教程（R2V 引用顺序与 ref_image_size）：https://docs.comfy.org/tutorials/video/minimax/minimax-h3
- Virse：H3 动作迁移与参考泄漏：https://www.virse.ai/blog/minimax-h3-motion-transfer
- RunDiffusion：H3 参考图实践：https://www.rundiffusion.com/minimax-h3-prompt-guide
- Uni3C 指南：https://learn.thinkdiffusion.com/uni3c-copy-camera-motion-from-any-video-full-guide-workflow/
- Wan Animate 2 官方教程：https://docs.comfy.org/tutorials/video/wan/wan-animate-2
- Blender + Seedance 灰盒预演：https://toonkit.io/en/models/seedance-blender ；论文 https://arxiv.org/html/2608.00094
- 相机运动检测：https://github.com/antiboredom/camera-motion-detector
