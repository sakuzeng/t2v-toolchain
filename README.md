# t2v-toolchain

文生视频的工具链：把「分镜脚本 → 结构化提示词 → 云 GPU 生成 → 成片量化验收 → 交付」
收在一个命令行入口里，生成引擎按注册表插拔。

后端走 [ComfyUI](https://github.com/comfyanonymous/ComfyUI) 的 HTTP API，
当前带三个引擎：MiniMax H3（视频，含原生立体声）、SCAIL-2（角色替换实验）、FLUX.2 klein（出图）。本仓是私有创作工作台里**引擎层与方法论**的抽取版：
代码、规范、分析脚本与项目模板在这里，作品资产与参考片不在。

## 为什么是这样

做 AI 视频最容易变成"改一版 prompt、抽一次卡、凭观感说像不像"。这套工具链想解决的是后半句：

- **"像不像"要能被判定，不靠观感。** 对成片用光流与姿态估计量化剪辑点、运动时序、静止段与景别，
  写成带容差的验收表逐项判阈值；未达标项顺着 criterion 的 note 归因回对应的提示词语句，只改那一句。
  18 类判定里只有 1 类需要参考片，**其余 17 类只吃成片**。
  测不到的（强模糊段的轨迹）就写"无法下结论"，不许目测补位；判不了的显式标 `manual`。
- **要复刻某条参考片时**，才额外量化参考片并做时间轴映射对齐，报最早的分歧而不是最后一张坏帧。
  这是可选分支，不是每个项目都走。
- **一次生成 = 一个不可覆盖的目录。** 输入 SHA-256、提交时的工作流与 prompt 冻结、git commit、
  耗时与费用 sidecar，全部落在同一个 run capsule 里，并追加到 `runs/index.jsonl`。
- **付费动作要两道闸门。** `plan` 永远免费只报价，`run` 必须同时传 `--execute --cost-confirmed`。
- **加模型不改主干。** 每个引擎是 `t2v/engines/<name>/` 一个子包 + 注册表一行；
  `cli.py` 里没有任何引擎名的硬编码。

## 快速开始

```bash
pip install -e .                      # 需要 Python 3.10+
python3 -m t2v init my-film           # 从模板建项目
python3 -m t2v validate my-film       # 免费：配置、prompt 字段、输入文件
python3 -m t2v plan my-film c001      # 免费：建图 + dry-run 报价
# 把报价给人看过、拿到确认之后：
python3 -m t2v run my-film c001 --execute --cost-confirmed
```

仓里带一个可直接跑通校验的示例项目 `projects/sample-lake`。

两条执行地点共用同一套 `t2v` 与工作流 JSON：**AutoDL 租用实例**（`scripts/remote/`）与
**实验室共享 GPU 机的容器**（`scripts/lab/`）。二者只在环境初始化、路径与下权重工具上不同，
命令表与项目结构完全一致。

免费的辅助命令：`graph h3` / `graph scail2` / `graph flux` 重建工作流 JSON（不联网）、
`motion` 做运镜与静止段量化（成片或参考片都可）、`contact-sheet` 做并排接触表（后两个需要 OpenCV）。
完整命令表见 [`t2v/README.md`](t2v/README.md)。

## 目录

| 路径 | 内容 |
|---|---|
| `t2v/` | Python 包：`cli` 统一入口、`comfy/` HTTP 通信、`engines/<模型>/` 建图与执行、项目与提示词解析 |
| `tests/` | 102 条离线测试（含假 ComfyUI 跑通的付费链路），`python3 -m pytest`，约 1 s |
| `.claude/skills/` | 两个可复用 Skill：`reference-video-director`（成片量化验收 + 参考片取证）、`character-design-director`（角色资产规范化）。见下方「跨客户端单一来源」 |
| `workflows/` | `h3/` 在用的 API 图与配对画布；`templates/minimax-h3/` 与 `templates/flux2/` 官方模板原样捕获（只读） |
| `docs/guide/` | 常青规范：项目结构与 run capsule、H3 提示词语法、ComfyUI 与插件、权重手册（`MODELS.md`） |
| `docs/ops/` | 5090 上的实测基线与踩坑记录 |
| `docs/research/` | 调研快照，一题一文、文首标日期，**结论被推翻时加更新块不删原文** |
| `scripts/` | 环境初始化与权重下载，按执行位置分 `remote/`（AutoDL）、`lab/`（实验室容器）、`local/`（本机） |
| `projects/` | 项目模板 `_template` 与示例项目 `sample-lake` |

## 跨客户端单一来源

Skill 要同时给 Claude Code 和 Codex 用，两边各存一份必然漂移——改了常用的那份，另一份悄悄过期。
所以规则定死：

- 唯一实体目录是 `.claude/skills/<name>/`，正文、`references/`、`scripts/`、`agents/openai.yaml` 都只在这里维护
- `.agents/skills/<name>` 只能是指向 `../../.claude/skills/<name>` 的**相对软链接**，供 Codex 发现；
  不允许在 `.agents/skills/` 放实体目录，也不允许反向链接
- Claude Code 用 `/<name>`、Codex 用 `$<name>`，两种调用解析到同一份 `SKILL.md`

可当场验证：

```bash
git ls-files -s .agents/skills/   # 两行都应是 mode 120000
realpath .agents/skills/*         # 都应指回 .claude/skills/<同名>
```

## 值得一读的一篇

[`docs/research/CAMERA_REPLICATION.md`](docs/research/CAMERA_REPLICATION.md) ——
深度/姿态控制片一度被判为复刻运镜的首选，后来被实测推翻并删码。
关键证据不是"效果不好"：固定 seed 固定控制片、只换 prompt 跑三版，产物几乎逐帧一致，
说明**控制片把 prompt 的作用压掉了**。原文保留，结论写在文首更新块里。

## 边界

- 到**单镜生成 + 评审 + 交付晋级**为止。多镜时间线、配乐、字幕的自动剪辑没做。
- 生成效果受模型与 seed 支配，标准是"可控迭代"不是"一次写对"；480p 一个镜头通常抽 2–4 个 seed。
- 验收表里可自动判定的项之外，仍有需要人看帧的人工项，它们显式标 `manual`，不混进自动判定的分子分母。

## License

MIT，见 [LICENSE](LICENSE)。`workflows/templates/minimax-h3/` 是 ComfyUI 官方模板的原样捕获，版权归原作者。
