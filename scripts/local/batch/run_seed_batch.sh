#!/usr/bin/env bash
# 多 seed 抽卡批跑：逐个 seed 顺序执行 python -m t2v run（每条一个 run capsule），单条失败继续下一条，最后汇总。
# 前提：用户已看过 `python3 -m t2v plan` 报价并明确确认整批预算；本脚本不做任何报价确认，只是把确认过的批次顺序跑完。
# 用法：bash scripts/local/batch/run_seed_batch.sh <project> <shot> <seed> [seed ...] 2>&1 | tee -a <日志>
set -uo pipefail
PROJECT=${1:?project}; SHOT=${2:?shot}; shift 2
[ $# -ge 1 ] || { echo "至少给一个 seed"; exit 2; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
BASE=${COMFY_URL:-http://127.0.0.1:8188}
curl -sf --max-time 10 "$BASE/system_stats" >/dev/null || { echo "[batch] ComfyUI 不可达：$BASE（隧道没开或 ComfyUI 没起）"; exit 3; }
ok=(); bad=(); t0=$(date +%s)
for seed in "$@"; do
  echo "=== [batch] $SHOT seed=$seed  $(date '+%F %T') ==="
  if (cd "$ROOT" && python3 -m t2v run "$PROJECT" "$SHOT" --seed "$seed" --execute --cost-confirmed); then ok+=("$seed"); else bad+=("$seed"); echo "[batch] seed=$seed 失败，继续下一条"; fi
  curl -sf --max-time 10 "$BASE/system_stats" >/dev/null || { echo "[batch] ComfyUI 失联，停止批次"; break; }
done
echo "=== [batch] 完成：成功 ${#ok[@]} (${ok[*]:-}) 失败 ${#bad[@]} (${bad[*]:-}) 用时 $(( ($(date +%s)-t0)/60 )) 分钟 ==="
tail -n "${#@}" "$ROOT/projects/$PROJECT/runs/index.jsonl" 2>/dev/null | python3 -c '
import sys,json
for line in sys.stdin:
    try: r=json.loads(line)
    except Exception: continue
    print("  ", r.get("run_id") or r.get("id"), r.get("seed"), r.get("elapsed_s") or r.get("execution_s"), r.get("cost_cny") or r.get("estimated_cost"))
' || true
[ ${#bad[@]} -eq 0 ]
