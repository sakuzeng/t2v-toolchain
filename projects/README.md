# projects/ —— 远端链路的项目目录

每个项目一个子目录，装这个项目自己的**知识、prompt、参考、实验、运行记录与交付物**。共享代码在 `t2v/`，工作流模板在 `workflows/`，官方写作规范在 MiniMax-H3 模型卡的 prompt 指南，要点提炼见 `docs/guide/H3_PROMPT.md`。

新项目不要手工复制目录，使用：

```bash
python3 -m t2v init <project-slug> --title "项目名"
```

v2 完整结构、命名和迁移规则见 `docs/guide/PROJECT_SYSTEM.md`。旧项目的 `ref/`、`outputs/` 和根级 prompt 仍可读取，但不再作为新项目标准。

每个项目必须有自己的 `README.md`，作为人类接手首页，至少说明：项目目标、当前真实状态、正式输入、已确认决定、信息入口、运行方式、已知风险和 v1/v2 边界。README 不复制全部参数和运行流水账；机器配置以 `project.json` 为准，生成事实以 `runs/index.jsonl` 为准。

```
projects/<项目>/
  project.json    项目级默认值、资产别名、费用和路径（engine.name 决定用哪个引擎）
  README.md       人类接手首页
  PROGRESS.md     当前阻塞与下一步（项目状态的唯一源）
  run.sh          该项目的命令快捷入口
  creative/       故事、分镜、决策和临时笔记
  prompts/        shots/<镜头>/vNNN.md 与资产 prompt
  assets/         source / canonical / candidates / archive
  references/     source / clips / analysis（大文件 gitignored；原创项目可只留 analysis）
  experiments/    A/B 实验设计、对比图和结论
  workflows/      plan 导出的镜头画布
  runs/           每次生成的 run capsule + index.jsonl（媒体 gitignored）
  deliverables/   经过评审选中的 preview / master
  docs/           项目专属说明
```

`t2v init` 造出来的就是这些，一项不多一项不少（有测试钉住）。只有 `migrate-v1` 迁过来的项目
才额外有 `archive/layout-v1/`。工作笔记只写在 `creative/NOTES.md`，根级不留存根。

跑：`python3 -m t2v validate <项目> <镜头>` → `python3 -m t2v plan <项目> <镜头>` → 报价确认 → `python3 -m t2v run <项目> <镜头> --execute --cost-confirmed`。新产物自动进入 run capsule。

| 项目 | 类型 | 结构 | 当前状态 |
|---|---|---|---|
| `smoke` | H3 冒烟/性能基线，**不是作品** | v1 | 三类技术测试；结论已归档到 `docs/ops/BASELINE.md`。不走项目系统，`run.sh` 直接调 `t2v h3` |
| `guofeng-pov` | 古风牵手 POV，I2V（base 三段式） | v1 | 绿裙 v1 已通过测试；红袖、30 秒拼接与正式资产待定 |
| `anxia-handhold` | 安夏写实牵手 POV，R2V | v1 | 三档分辨率已通过；画幅与中段转身方案待定 |
| `chiling-ink-sword` | 赤翎水墨舞剑，H3 R2V + 提示词 | v2 | 已有多轮生成；2026-09-16 移除深度控制，C001A v021 / C001B v002 草稿 |
| `sunset-sofa` | 黄昏沙发，写实短片，**I2V 首帧对齐 + 9:16 竖屏**（每镜先出图；目标情绪＝怜爱） | v2 | 设计文档/剧本/分镜/1 张场景图 prompt + 6 张首帧图 prompt + 6 条 H3 prompt（各带中文镜像）已写完待评审；场景图与首帧图待远端出图，未生成 |
| `guofeng-maiden` | 国风少女角色资产与后续视频，R2V | v2 | 已生成至角色候选 v003，等待用户选角 |
| `russian-ponytail-girl` | 俄罗斯单马尾少女角色资产与后续视频，R2V | v2 | 已生成角色候选 v001，等待用户选角 |
