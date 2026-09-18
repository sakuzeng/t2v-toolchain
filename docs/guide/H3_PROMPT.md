# H3 prompt 规范

> 常青手册。官方原文（base 版 + ref 版）在 [MiniMax-H3 模型卡](https://huggingface.co/MiniMaxAI/MiniMax-H3)
> 的 `docs/VIDEO_PROMPT_WRITING_GUIDE_{base,ref}_en.md`，本文是要点提炼。
> 正文来自 `research/WORKFLOW.md` §2（2026-09-05 调研）——该文 2026-09-16 按章节拆进 `guide/` 后退场：
> 这不是某天的调研结论，是每次写 prompt 都要查的东西。
> 好 prompt 的写法与密度上限另见 `research/H3_PROMPT_PATTERNS.md`（含实测教训）。

H3 官方要求 **三段固定字段**，而不是自由散文：

```
[首行对齐指令，仅 I2VA/FL2VA/L2VA 有]
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, ... [Shot 2] At 00:03.500, the camera cuts to ...
overall_soundscape: 1–4 句环境音/动作音/非语言人声（不含对白与配乐）
non_diegetic_music: 1–3 句只描述配器、速度、节奏、动态，不写情绪词；无配乐写 N/A
```

关键语法：
- 镜头 `[Shot N] At MM:SS.mmm,` 严格递增；第一镜无时间戳。
- 运镜 = 类型 + 幅度 + 速度，写成动作句：`The camera pushes in with small amplitude at slow speed toward ...`。类型表：Zoom/Push/Pull/Pan/Truck/Tilt/Pedestal/Arc/Tracking/Static/Shake/POV/Roll。
- 说话者稳定编号 `(S1)`，对白只在 `<d>[语言] 台词</d>` 内；画外音固定写 `says in an off-screen voiceover` 并声明嘴唇闭合；跨镜台词用 `<scenetrans>`，被截断用 `<cutoff>`。
- 画面文字用英文双引号原样保留（如 `"营业中"`）。
- R2V 另有六段结构：`subject_definitions`（`<Subject N>` 从图/视频抽取的可复用内容，`<Picture N>` 帧锚点，`<Video N>` 整段结构/续写源，`<Audio N>` 声线/音轨）→ `summary` → `retention_analysis`（`fully_preserved / partially_preserved / attribute_transfer / weak_reference`；音频 `fully_copy / partially_copy / reference / weak_reference`）→ `detailed_description`（350–500 词）→ 两个声音字段。
- I2V（base 三段式）的首帧走项目链路：prompt frontmatter 写 `first_frame: "@别名"`，别名在 `project.json` 的 `assets` 里指向本机图片（`defaults.first_frame` 可给默认值）；`project.json` 的 `engine.mode: i2v` 时缺首帧会直接报错，`fl2v`/`l2v` 会报「引擎只接线了 first_frame」。即 `refs` 只在 R2V 下可用，I2V 用 `first_frame`。
- 语言：**正文送进模型的是什么语言，模型就吃进什么语言**；字段名与对齐指令固定英文。用户 2026-09-18 的口径是「提交到远端的 prompt 都应是英文，中文是给人看的」，据此 `rooftop-afternoon` 定为正文全英文、中文只放 frontmatter 与 `script.md`；用户同日明确 **`languid-afternoon` 保持中文正文不动**（只改新项目），将来要统一口径时以两边实拍对比为准。
- 与上级仓库的映射：上级 `/film-director` 的轴线/景别/剪辑审依旧适用于内容层，但**输出格式必须是 H3 三段式**，运镜词汇对齐官方表。把导演分析改写成三段式的 `h3-prompt` skill 尚未建（见 `status/TODO.md`）。


## 校验

`python3 -m t2v validate <项目> <镜头>` 检查 R2V 六段齐全、`detailed_description` 词数 350–500、
`status` 合法、输入文件存在，并对 `control` / `control_videos` / `guides` 等退役键告警。
帧数桶（24 fps 的 17k+5）由 `t2v/prompt.py:expected_frames` 计算，`plan` 会打印。

## prompt 文件约定（2026-09-18 起）

- 文件名用 **`.md`**，YAML frontmatter 写元信息（`title` / `status` / `lang` / `zh` / `workflow` / `params` / `surface`），
  **正文才是送进模型的内容**。`t2v` 读 `.md` 时剥掉 frontmatter，读 `.txt` 则原样送（早期 smoke 用的 `.txt` 仍兼容，
  但新 prompt 一律 `.md`）。
- 每个 prompt 配一份**中文对照 `<名>.zh.md`**：`lang: zh` + `submit: false`，只给人看，**永远不提交**
  —— H3 是「正文什么语言就吃什么语言」，中英混着发会把语言先验带偏。
- 这条只约束**新写的** prompt；`languid-afternoon` 的中文正文按 2026-09-18 的口径保持不动，将来用实拍对比再定是否统一。
- 例子：`projects/smoke/prompts/cute_girl_playful.md`（英文，提交）+ `cute_girl_playful.zh.md`（中文，对照）。
