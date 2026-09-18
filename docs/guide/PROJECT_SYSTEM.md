# 项目系统（v2）

> 常青规范。原文件为 `docs/PROJECT_SYSTEM_V2.md`，2026-09-16 迁入 `guide/`：
> v2 是当前也是唯一的版本，版本号不必写进文件名（v1 布局只作只读归档，见文末迁移原则）。

## 目标

把创作事实、正式资产、参考分析、实验和每次生成结果分开管理。核心不变量是：**一次生成对应一个不可覆盖的 run capsule**，任何成片都能反查 prompt、工作流、参数、输入哈希、Git 提交和费用。

## 标准目录

角色型项目需要进一步按“角色 → 单图 / 一致性参考板”拆分 prompt、候选与正式资产；可复制模板见 `projects/russian-ponytail-girl/docs/pipeline/CHARACTER_ASSET_ORGANIZATION.md`。

```text
projects/<slug>/
├── project.json                 # 唯一项目级配置与资产别名
├── README.md                    # 人类接手首页
├── PROGRESS.md                  # 当前阻塞与下一步（项目状态的唯一源）
├── run.sh                       # 该项目的命令快捷入口
├── creative/                    # 故事、分镜、决定、工作笔记
├── prompts/
│   ├── shots/<shot>/v001.md     # 镜头 prompt，版本不可覆盖
│   └── assets/                  # 资产生成 prompt
├── assets/
│   ├── source/                  # 用户给出的原始图
│   ├── canonical/               # 已定稿且由别名引用的正式资产
│   ├── candidates/              # 候选资产
│   └── archive/                 # 被替代资产
├── references/                  # 复刻类项目才需要；原创项目可只留 analysis/
│   ├── source/                  # 原始参考视频
│   ├── clips/                   # 镜头切片
│   └── analysis/                # 抽帧、接触表、数据分析
├── experiments/<experiment>/    # 明确假设的 A/B 实验及结论
├── workflows/                   # `plan` 导出的镜头画布（<shot>__<version>.ui.json）
├── runs/<shot>/<run-id>/        # 一次生成的完整封装
├── runs/index.jsonl             # 可检索运行索引
├── deliverables/{preview,master}/
└── docs/                        # 项目专属说明
```

`t2v init` 造出来的就是上面这些，一项不多一项不少（`tests/test_runs.py` 钉住了这一点）。
只有 `migrate-v1` 迁过来的项目才额外有 `archive/layout-v1/`（旧结构只读归档）；
新项目没有 v1 历史，不会有这个目录，也不会有 v1 的 `ref/`。

## 配置分层

- `project.json`：引擎、共享工作流、默认参数、资产别名、费用模型与标准路径。
  `engine.name` 决定 `plan` / `run` 用哪个引擎（当前可选 `h3`；缺省也是 `h3`，历史项目不写也能跑），
  取值必须是 `t2v/engines/__init__.py` 注册表里的名字。`engine.mode` 只是任务类型备注，代码不读它。
- prompt frontmatter：镜头时长、该镜头的参考图、状态；只写与项目默认值不同的内容。`control` / `control_videos` / `guides` 已退役，`validate` 见到会告警并忽略。
- CLI 参数：仅作本次实验覆盖，最终解析值必须进入 run capsule。

配置采用 JSON 而非 YAML，以便 Python 3.9 环境只用标准库即可校验和运行；JSON 也更适合稳定 schema 和自动迁移。

## Run capsule

每次成功提交创建：

```text
runs/<shot>/<timestamp>_seed<seed>_<prompt-id>/
├── request.json                 # 解析后的请求、输入路径与哈希
├── prompt.md                    # 本次 prompt 冻结副本
├── workflow.api.json            # 本次实际提交图
├── workflow.ui.json             # 可选，ComfyUI 可视化图
├── output.mp4                   # H3 原始声画输出，留作追溯
├── picture.mp4                  # 可选；strip_audio=true 时生成的无音轨画面母版
├── run.json                     # prompt id、设备、耗时、费用与媒体信息
├── logs/
└── qa/review.md
```

`runs/index.jsonl` 每行一个精简记录。run 生成后不覆盖；重跑就是新 run。

需要后期统一配乐的项目可在 `project.json` 默认参数或 prompt frontmatter 中设 `strip_audio: true`。运行时保留原始 `output.mp4`，并用视频流直拷贝生成 `picture.mp4`；`promote` 优先选择后者，避免 H3 临时环境声进入交付物。

## 状态与命名

- 项目：稳定、小写 kebab-case，例如 `chiling-ink-sword`。
- 镜头：`c001a`；镜头拆分也使用稳定 ID，不把描述写进 ID。
- prompt：`v001.md`、`v002.md`；旧版本保留。
- 状态：`draft → reviewed → validated → final`。
- 实验：`e001_depth_strength`，必须有假设、变量、固定项、结果和结论。

## 标准工作流

```text
init → 资产归档/定稿 → prompt 六审 → validate → plan/报价确认
     → run → review → promote → pack
```

`plan` 和 `validate` 免费。`run` 必须同时显式传入执行与费用确认开关；这道技术门槛不替代向用户展示 dry-run 报价并获得确认。

## 迁移原则

1. 先复制、建清单、算哈希，不删除旧文件。
2. 正式资产复制到 `assets/canonical/`，原文件作为旧路径兼容层暂留。
3. `ref/` 复制到 `references/`；`outputs/` 按 sidecar 基名归入 run capsule。
4. 无法匹配到某次运行的拼图/日志放进 `experiments/legacy-import/`。
5. 验证新索引和数量后，再由用户单独决定是否清理旧目录。
