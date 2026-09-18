# 交接给 MiniMax H3：把已批准的分析翻译成 prompt

权威规范是 MiniMax-H3 模型卡里的 `docs/VIDEO_PROMPT_WRITING_GUIDE_{base,ref}_en.md`，本文只列翻译时最容易违反的点。`h3-prompt` 技能建成后本节并入它。

## 结构（全参考模式六段，顺序固定）

`subject_definitions` → `summary` → `retention_analysis` → `detailed_description` → `overall_soundscape` → `non_diegetic_music`。

- `<Subject N>` 定义里引用 `<Picture N>`；只用来定义角色/道具的图不单列条目。
- `retention_analysis` 用固定标记：`fully_preserved` / `partially_preserved` / `attribute_transfer` / `weak_reference`，并写出现在哪些 `[Shot]`。
- `detailed_description` 生成任务 350–500 英文词；第一镜不写时间戳，后续 `[Shot N] At MM:SS.mmm` 严格递增且在时长内。**时间戳只出现在切镜行**，官方 base/ref 指南全部范例都如此；镜头内部按播放顺序用连词描述。
- 帧数 17k+5；带对白禁用 Turbo LoRA（本项目无对白）。
- 本项目声画分离：`overall_soundscape` 写明无声，`non_diegetic_music: N/A`。

## 运镜写法：类型 + 幅度 + 速度，写成句子

官方词表：`Zoom In/Out`、`Push In/Pull Out`、`Pan Left/Right`、`Truck Left/Right`、`Tilt Up/Down`、`Pedestal Up/Down`、`Arc Shot`、`Tracking Shot`、`Static Shot`、`Shake Slightly/Strongly`、`POV`、`Roll`；幅度 `with small/large amplitude`；速度 `at slow/fast speed`。

```text
The camera tilts up with large amplitude at fast speed as her sleeve sweeps across the foreground in heavy motion blur, and the move settles into a chest-up close-up.
```

- 一次连续重构图只写一个 `[Shot]`，不因为景别变了就拆镜。
- 测量能分清机制时用具体词（Tilt Up / Push In）；分不清 Tilt 与 Pedestal 时写 `reframes upward`，把设备运动列入 `assumptions`。
- 速度词的依据是 `windows.json` 的峰值与时长，不是感觉。

## 从测量到措辞的对应

| 测量结果 | 写法 | 禁止 |
|---|---|---|
| `sustained_motion_not_cut` | 一镜内快速重构图 + 运动模糊 | 写成 `the camera cuts to` |
| `hard_cut_likely` @ t | `[Shot N] At t, the camera cuts to ...` | 让模型用长镜头模拟切 |
| 强模糊段（人物检出率低、LK 丢失） | 快速上扫 + 前景遮挡（袖/手/剑穗）+ 落点景别 | 任何屏幕坐标、"锁定指尖"、"镜头以指尖为锚点" |
| LK `screen-locked 候选`（覆盖≥0.5，漂移<0.05） | `Tracking Shot` 跟随该特征，可写"stays near frame centre" | 给百分比坐标框 |
| LK `loose tracking 候选` | `loosely follows` | 写成锁定 |
| `holds` 段 | `holds motionless for about 0.4 s` | 省略停顿 |
| 起始/峰值时刻 | 镜头内**不写时间戳**：用 then / as / until / as soon as 排先后，用幅度速度词定节奏；精确时刻交给 acceptance 由回测核对，出不来就换 seed 再抽（深度控制片已于 2026-09-16 退役） | 在一个 [Shot] 里写 `At MM:SS.mmm`（官方只在切镜行用它，训练数据里它就是切镜标记，C001A v007 用了 12 个） |
| 景别代理 起→止 | 起点景别 + 落点景别（"from a low knee-level frame to a chest-up close-up"） | 只写 `Close-up` |

## 密度与动作写法（来自官方范例与社区经验，见 `docs/research/H3_PROMPT_PATTERNS.md`）

- **一个镜头一个主动作、一条相机路径**，镜头 2–5 秒；每拍 ≤2–3 秒且只含一个事件。参考片一镜里有三个主动作时，要么拆镜，要么放慢生成再后期提速，不要指望文字让模型在 3 秒里做完三件事。
- 镜头内时间用时间短语（early in the clip / as the clip progresses / with X now settled / throughout the remainder），不用数字。
- 动作写成**动词链 + 中间姿态 + 环境反应 + 跟随相机**（cdance 特技范例：runs, plants, clears, lands, rolls, rises；dust lifts and settles；camera follows from three meters back）。画面断裂的修法是补中间姿态。
- 主体动作、相机动作、切镜分开成句。
- 否定句 0 句或结尾 1 句，只列会毁片的项。身份特征在 subject_definitions 定义一次，正文不复述。

## 推断项的去处

- 只有 `measured` / `visible` 的结论进正文。
- `inferred` 项若非写不可，放 frontmatter `assumptions:`（单行 JSON 列表），评审时可逐条否决；正文里对应句子要能单独删除而不破坏结构。
- 台账里的"替代解释"不进 prompt。

## 交接前误读模拟（必做，逐句问“模型为了兑现这句话会做出什么合理但错误的选择”）

本项目实测过的误读，写 prompt 时对照：

| 写法 | 模型的字面执行 | 应改为 |
|---|---|---|
| "the two legs read as one slender line" / "form a slim X" | 画成一根靴子（v011 0–0.5 s） | 写身体结构：右腿垂直、左膝微屈、左靴交叠在右小腿前、两只靴子都可见 |
| "the left foot directly behind the right" | 双脚并排（v008/v009） | 写从镜头看到的前后遮挡关系 + “两只都可见” |
| 每段三四个 never | 全部无视，动作反而被压缩 | 0 句或结尾 1 句 |
| "hand at hip … then salute" 中间没有姿态 | 手以完成态突现 | 写出中间姿态（前臂横扫、指尖朝侧）并给它时间 |
| 一个镜头里写 `At 00:00.550` 等十几个时间戳 | 无效，且有诱发跳变风险 | 时间短语排先后，时序靠过程描写与多 seed 抽卡 |
| 剪影/构图观感词（"one line"、"X"、"silhouette"） | 被当成要画的形状 | 只写物体与身体的实际配置 |

规则：**描述身体与物体的实际配置，不描述它在画面里看起来像什么。** 观感是分析报告里的事，不是 prompt 里的事。

## 交接前自检

1. 每个 `[Shot]` 至少一个运镜句；当前是无控制 R2V，运镜完全由文字承担。
2. 时间戳与 `acceptance` 规格里的区间一致（起始、峰值、抵达近景）。
3. 识别点按机位可见性裁剪：拍不到的写"本镜看不到"，不整段复制。
4. 新增约束后回扫同维度旧句（景别 vs 取景、静止 vs 动作、方向 vs 地形）。
5. 词数 350–500；六段齐全；`python3 -m t2v validate <项目> <镜头>` 通过（`control` / `guides` 等退役键会告警）。
