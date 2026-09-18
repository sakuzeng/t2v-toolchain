---
name: reference-video-director
description: 把参考视频当作电影语言证据来分析：切点、逐时间窗观察台账、可测量的运镜与主体轨迹、与生成产物的匹配时间码对比，产出导演分析报告，经批准后再翻译成目标模型 prompt。用于从真实片段反推调度、构图、运镜、剪辑转场、节奏，或诊断生成结果与参考片的偏差；没有源视频、只评审 prompt 文本时不用本技能。
---

# 参考视频导演分析

视频是证据，不是拿来改写的 prompt。输出必须区分"看见的""测出来的"和"推断的"，让一句听起来很电影的镜头指令没法顶替原片里真实发生的动作。C001A v005 的教训就是：没测过指尖轨迹，就写出了"锁定中央跟踪框"。

## 三种模式

- **分析**：参考视频 → 切点判定 → 测量 → 逐时间窗观察台账 → 导演解释 → prompt 含义。
- **对比**：参考 + 生成产物 → 按时间映射对齐后逐时间码比较，找最早的因果分歧，给最小必要修正。
- **prompt 交接**：已批准的分析 → 目标模型 prompt。禁止先写 prompt 再倒推理由。

## 证据流程

1. **读项目上下文**：`project.json`、`creative/{DECISIONS,SHOTLIST}.md`、`PROGRESS.md`、当前 prompt 版本、相关 run 的 `request.json`。遵守项目的资产与费用规则。
2. **锁定源**：确切的参考文件、时间范围、生成产物（若有）、目标模型。记录路径与哈希；不得用同名相近的片段偷换。产物若做过时间重采样（如 c001a 的 141 帧母版另存 69 帧加速版），先从 run 或 RUNBOOK 里取出映射，写成 `--compare-map 参考t:产物t,...`。
3. **取证** `scripts/prepare_evidence.py`（标准库 + ffmpeg；用 text2video 虚拟环境的 python 运行可自动烧录时间码）：
   - 探测、哈希、粗采样帧与拼图；
   - ffmpeg 场景分数给出**候选**切点，并默认在每个候选点 ±0.35 s 自动生成 24 fps 密集窗口，单窗口超过 48 帧自动降帧率；
   - `--compare` 时按映射逐对定位并排帧（左参考、右产物），文件名和烧录字幕都带两侧各自的时间；
   - 帧名里的时间是 showinfo 的真实 pts。
4. **测量** `scripts/measure_tracks.py`（`workon text2video`；opencv、numpy、rtmlib）：
   - `--cuts-json` 读入候选切点，按相邻帧差尖峰比与直方图相关判为 `hard_cut_likely` / `sustained_motion_not_cut` / `ambiguous`；快速甩镜会连续误报，**这一步必须做**；
   - 每帧全局光流（dx/dy/zoom/能量/主体残差）→ 每窗口运镜方向提示、峰值时刻、停顿段、镜头 vs 主体主导比；
   - DWPose 全身关键点归一化坐标与置信度，按"在画幅内且过门槛"的可见部位给出景别代理（全身/膝上/腰上/胸上/面部）；
   - `--track 标签:时间:x:y` 对指尖、剑尖等姿态模型抓不准的点做 LK 双向跟踪，输出漂移范围与 `screen-locked / loose tracking / 非跟踪` 候选判定；覆盖率不足 50% 时明确报"无法下结论"；
   - 输出 `windows.json`、`cuts.json`、`tracks.csv`、`motion.csv`、轨迹叠画与曲线图。
   - 已知边界：强运动模糊段里姿态和 LK 都会丢，光流中值会塌向 0。此时"测不到"本身就是观察结果，写进台账，禁止用目测坐标补位。
5. **先定镜头边界，再谈运镜**。硬切、一镜内重构图、甩镜模糊、前景遮挡、动作匹配剪辑是不同机制；候选切点要同时看 `cuts.json` 判定和密集帧。
6. **填观察台账**（见 [references/report-schema.md](references/report-schema.md)）。每个关键时间码分别记：主体/肢体/道具动作；主体与被跟踪特征的屏幕位置；景别与可见身体区域；背景运动与视差；焦点、运动模糊、遮挡；剪辑证据；置信度与未排除的替代解释。每格标来源：`measured`（来自 CSV/JSON）、`visible`（帧上直接可见）、`inferred`（推断）。
7. **导演解释**：台账填完后，先查 [references/cinematography-knowledge.md](references/cinematography-knowledge.md) 的术语与识别线索，再用 [references/motion-and-edit-tests.md](references/motion-and-edit-tests.md) 的判别测试推断调度、运镜与剪辑语法。每条结论写明支撑它的台账行与测量值。
8. **对比模式**：两条视频用同一参考相对时间码；报最早的有意义分歧，而不只是最后一张坏帧。
9. **先写验收，再写 prompt**（见 [references/acceptance-schema.md](references/acceptance-schema.md)）：把参考片的测量值加容差写成 `acceptance_<镜头>.json`（起始/峰值时刻、模糊窗口时长、抵达近景时刻、停顿、能量比、人工项），用 `scripts/check_acceptance.py` 对**参考片自身**跑一遍，全部通过才算校准。prompt frontmatter 单行引用它。
10. **翻译成 prompt**（见 [references/h3-handoff.md](references/h3-handoff.md)）：只翻译已批准的结论。MiniMax H3 按仓库现行指南保留六段、参考编号、时间码递增、350–500 词与可见性规则；运镜写"类型 + 幅度 + 速度"的句子，速度词依据测量值。强模糊段一律写成快速重构图 + 前景遮挡 + 落点景别，不写坐标、不写跟手。推断项只能进 frontmatter `assumptions:`。
11. **产物回测**：每次 run 后对 `picture.mp4` 跑 `check_acceptance.py`（带产物→参考的 `--time-map` 与参考测量目录），报告写进 run capsule `qa/acceptance_<镜头>.md`。review 先看这张表再看片；表格没覆盖的才由人裁决。未通过项对应回台账里的哪一行，改 prompt 只改那一行对应的句子。

## 这套流程能保证什么、不能保证什么

能保证：不再写出参考片里不存在的约束；每条运镜句有测量依据；通过与否由表格判定而不是观感。
不能保证：H3 一次执行到位。时机是概率事件，无 seed 确定性，480p 通常要抽 2–4 次；深度控制片这条路已于 2026-09-16 否决（见 `docs/research/CAMERA_REPLICATION.md` 文首：它压掉了 prompt 的作用），现在时机只能靠过程描写 + 多 seed 抽卡。所以标准是"可控迭代"，不是"一次写对"。

## 阅读预算

- 一次看图不超过约 40 张；`prepare_evidence.py` 总帧数超过 160 会警告。
- 顺序：拼图 → `plot_tracks.png` 曲线 → 只对争议窗口看密集帧。整段 32 s 参考片不要一次全抽。
- 需要更细时缩小窗口，而不是加总帧数。

## 硬性约束

- 不得因为"听起来像电影"就发明跟踪点、屏幕坐标、焦距、机械装置、切点或因果关系。
- "屏幕锁定"只有在测得的轨迹支持时才能写；否则描述可见的相对运动，不写固定坐标指令。
- 光流和整帧运动是佐证不是运镜证明；大面积前景动作会主导它。
- 画外道具按裁切或遮挡描述；正常重构图导致的消失不是连续性失败。
- 观察、解释、生成指令分三段，不混写。
- 两种解释都成立时明确标不确定，并指出需要哪个更密的窗口或哪条测量。
- 不启动视频/图片生成、不开付费算力、不装依赖；后续付费动作走仓库既有的确认门。

## 交付物

可复用的媒体证据放项目 `references/analysis/<镜头>/<分析ID>/`（媒体已被 gitignore），书面报告 `analysis.md` 放同一目录并纳入 Git；若项目对该目录整体忽略，则报告放 `docs/analysis/<镜头>/<分析ID>.md`。产出：

- `manifest.json`（源身份、探测、采样设置、候选切点、时间映射）；
- `windows.json`、`cuts.json`、`tracks.csv`、`motion.csv`、叠画与曲线图；
- 拼图、密集帧、并排帧；
- 按报告模板写的 `analysis.md`；
- 校准过的 `prompts/shots/<镜头>/acceptance_<镜头>.json`；
- 每个 run 的 `qa/acceptance_<镜头>.md` 回测表；
- 用户要求时，另交目标模型 prompt 与中文评审镜像。

用户未批准改 prompt 时，分析完即停。被否决的 prompt 版本不得覆盖，只能建新版本并链接到本次分析。

## 语言

台账、报告、评审镜像用中文；只有提交给生成模型的 prompt 正文用英文。
