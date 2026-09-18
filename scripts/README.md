# 运维脚本

本目录先按执行位置分为 `remote/`（AutoDL GPU 机）、`lab/`（实验室 `lab-host` 的 `agent` 容器）和 `local/`（本机），再按职责放置 shell 运维入口。项目配置、提示词、校验、报价、单次运行和记录由 `t2v/` 包负责；入口为 `python3 -m t2v`。

| 位置 | 运行地点 | 用途 |
|---|---|---|
| `remote/bootstrap/setup_h3.sh` | AutoDL GPU 机 | 安装 H3、ComfyUI、插件和 Blender 环境 |
| `remote/models/h3/download.sh` + `manifest.txt` | AutoDL GPU 机 | 下载并校验 H3 权重（aria2 多线程） |
| `remote/models/scail2/download.sh` + `manifest.txt` | AutoDL GPU 机 | 下载并校验 SCAIL-2 权重；下载前检查剩余空间 |
| `lab/bootstrap/setup_h3.sh` | 实验室容器（`lab-host` / `agent`） | 同一套 H3 + ComfyUI 环境，但用 venv 而非 conda、torch 钉 cu124、clone 走 GitHub 代理、不装 Blender |
| `lab/models_download.sh` + `lab/fetch_manifest.py` | 实验室容器 | 读同一份 `remote/models/h3/manifest.txt` 下载权重；curl 分块并发（实验室里 aria2c 实测只有它一半速度），`ENGINE=aria2` 可回退 |
| `lab/env.sh` | 实验室容器 | `COMFY_HOME` / `HF_*` / `PIP_INDEX_URL` 与 `h3env`、`comfy`、`comfy-cpu`、`h3lab` 别名 |
| `local/batch/run_seed_batch.sh` | 本机 | 顺序提交一批已确认预算的 seed，单条失败后继续并汇总结果 |

每个模型有独立目录，下载脚本默认从自身目录读取对应清单，不依赖调用时的工作目录。部署时可复制整个 `scripts/` 目录，再在远端执行 `scripts/remote/bootstrap/setup_h3.sh` 或 `scripts/remote/models/<模型>/download.sh`；实验室侧见 `scripts/lab/README.md`。

`remote/bootstrap/setup_h3.sh` 与 `lab/bootstrap/setup_h3.sh` 会安装软件，下载脚本会占用网络和磁盘空间；AutoDL GPU 实例开机时按时间计费（实验室容器无按量费用，但机器是共享的）。下载脚本的 `--verify-only` 不下载权重，但可能写入 `.sha256.ok` 校验标记。`local/batch/run_seed_batch.sh` 会为每个 seed 提交生成；运行前先用 `python3 -m t2v plan <项目> <镜头>` 获取整批报价并经用户明确确认预算。单次生成入口及约束见 `t2v/README.md` 与 `docs/guide/PROJECT_SYSTEM.md`。
