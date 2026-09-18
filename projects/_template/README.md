# __PROJECT_TITLE__

> 项目类型｜生成模式｜项目系统 v2

项目代号：`__PROJECT_SLUG__`

## 项目目标

用一至两段话说明最终要交付什么、受众/平台、画幅与大致时长。不要把迁移记录或工具说明当作项目目标。

## 当前状态

| 项目项 | 状态 | 说明 |
|---|---|---|
| 正式资产 | 未齐备 | 列出仍缺的角色、服装、道具、场景或声线 |
| 当前镜头 | draft | 写当前正在推进的镜头与边界 |
| 实际生成 | 尚未开始 | 区分 dry-run、实验 run 和通过评审的 run |
| 正式交付物 | 无 | 只有 `deliverables/` 内的内容才算交付物 |

## 已确认的制作决定

只列会改变生成路线的关键决定，详细理由链接到 `creative/DECISIONS.md`。

## 正式输入

列出 `project.json` 中的 canonical 资产别名与职责。README 用于帮助人理解，文件路径和默认参数仍以 `project.json` 为准。

## 信息入口

| 文件/目录 | 用途 |
|---|---|
| `project.json` | 机器可读的默认参数、工作流、资产别名和费用基线 |
| `creative/` | 故事、分镜、决策和工作笔记 |
| `prompts/shots/` | 按镜头和版本保存的 H3 prompt |
| `runs/index.jsonl` | 实际生成事实索引 |
| `deliverables/` | 经过评审提升的预览或母版 |

## 已知风险

列出模型、素材、显存、连续性和合规风险。

## 开工顺序

1. 在 `creative/` 写清故事、分镜和关键决策。
2. 将原始素材放进 `assets/source/`，选定素材复制到 `assets/canonical/` 并在 `project.json` 建立别名。
3. 每个镜头使用 `prompts/shots/<shot-id>/v001.md`，一次只修改一个版本。
4. 运行 `python3 -m t2v validate __PROJECT_SLUG__`。
5. 运行 `python3 -m t2v plan __PROJECT_SLUG__ <shot-id>`；报价确认后才可执行付费生成。
6. 每次生成封装在 `runs/<shot-id>/<run-id>/`，评审后再提升到 `deliverables/`。

## 数据边界

- Git 跟踪：配置、创作文档、prompt、正式小型资产、运行索引、评审结论。
- Git 忽略：参考视频、控制视频、生成视频、临时缓存和迁移归档。
- `runs/` 是不可变运行记录；不要覆盖旧运行。
- `deliverables/` 只放经评审选中的预览或母版，不作为实验区。
