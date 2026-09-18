#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
project="$(basename "$(dirname "$0")")"
shot="${1:?用法: run.sh <shot-id> [t2v.py plan 参数]}"
shift
exec python3 -m t2v plan "$project" "$shot" "$@"
