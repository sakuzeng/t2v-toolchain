#!/usr/bin/env python
"""验收闭环：对生成产物跑同一套测量，逐条核对 prompt 附带的可测量验收项，输出通过/不通过表。

依赖 text2video 虚拟环境（内部调用 measure_tracks.py）。只读视频，只写报告，不做付费动作。

用法：
  python check_acceptance.py --video 产物.mp4 (--spec acceptance.json | --prompt prompts/shots/c001a/v006.md)
      [--measure-dir DIR]            # 测量输出目录；已存在且含 windows.json 则直接复用
      [--ref-measure-dir DIR]        # 参考片的测量目录（含 motion.csv），用于 energy_ratio_vs_ref_min
      [--time-map 产物t:参考t,...]    # 产物时间 → 参考时间的分段线性映射；不给则恒等
      [--report out.md] [--json out.json] [--strict]

验收规格（JSON）：{"tracks": [{"label":..,"t":..,"x":..,"y":..}], "criteria": [ {...}, ... ]}
criteria 每项含 id、type、参数与可选 note。支持的 type 见 references/acceptance-schema.md。
prompt frontmatter 里写 `acceptance: acceptance_v006.json`（相对 prompt 所在目录）或单行 JSON。"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PTS_RE = re.compile(r"pts_time:([0-9.]+)")


def detect_cuts(video: Path, threshold: float = 0.28) -> list[float]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf", f"select=gt(scene\\,{threshold}),showinfo", "-an", "-f", "null", "-"],
                       text=True, capture_output=True)
    return sorted({round(float(v), 6) for v in PTS_RE.findall(r.stderr)})


def load_spec(args) -> dict:
    if args.spec:
        return json.loads(Path(args.spec).read_text(encoding="utf-8"))
    text = Path(args.prompt).read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        sys.exit("prompt 没有 frontmatter")
    end = text.find("\n---\n", 4)
    for line in text[4:end].splitlines():
        if line.startswith("acceptance:"):
            value = line.split(":", 1)[1].strip()
            if value.startswith("{") or value.startswith("["):
                data = json.loads(value)
                return data if isinstance(data, dict) else {"criteria": data}
            return json.loads((Path(args.prompt).parent / value.strip("'\"")).read_text(encoding="utf-8"))
    sys.exit("prompt frontmatter 里没有 acceptance 字段")


def parse_map(text: str | None):
    if not text:
        return lambda t: t
    pairs = sorted(tuple(float(v) for v in p.split(":")) for p in text.split(","))
    xs = np.array([p[0] for p in pairs]); ys = np.array([p[1] for p in pairs])
    return lambda t: float(np.interp(t, xs, ys))


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def fcol(rows, key):
    out = []
    for r in rows:
        v = r.get(key, "")
        out.append(float(v) if v not in ("", None) else np.nan)
    return np.array(out, dtype=np.float64)


def roi_series(video: Path, roi: list[float], cache_dir: Path, dark_thr: int = 70) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ROI（归一化 x0,y0,x1,y1）内两条序列：相邻帧绝对差均值（变化量）与暗像素占比（占位量，亮背景上的深色主体/墨迹）。"""
    key = "_".join(f"{v:.2f}" for v in roi) + f"_d{dark_thr}"
    cache = cache_dir / f"roi_{key}.json"
    if cache.is_file():
        d = json.loads(cache.read_text()); return np.array(d["t"]), np.array(d["v"]), np.array(d["dark"])
    import cv2
    cap = cv2.VideoCapture(str(video)); fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    x0, y0, x1, y1 = int(roi[0] * W), int(roi[1] * H), int(roi[2] * W), int(roi[3] * H)
    ts, vs, ds, prev, n = [], [], [], None, 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(fr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
        ts.append(n / fps); vs.append(float(cv2.absdiff(prev, g).mean()) if prev is not None else 0.0)
        ds.append(float((g < dark_thr).mean())); prev = g; n += 1
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"t": ts, "v": vs, "dark": ds}))
    return np.array(ts), np.array(vs), np.array(ds)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True, type=Path)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--spec", type=Path); g.add_argument("--prompt", type=Path)
    ap.add_argument("--measure-dir", type=Path)
    ap.add_argument("--ref-measure-dir", type=Path)
    ap.add_argument("--time-map", type=str, default=None)
    ap.add_argument("--report", type=Path); ap.add_argument("--json", type=Path)
    ap.add_argument("--strict", action="store_true", help="有未通过项时返回非零")
    args = ap.parse_args()
    if not args.video.is_file():
        ap.error(f"视频不存在：{args.video}")
    spec = load_spec(args)
    criteria = spec.get("criteria", [])
    mdir = args.measure_dir or (args.video.parent / "qa" / "measure")
    to_ref = parse_map(args.time_map)

    if not (mdir / "windows.json").is_file():
        mdir.mkdir(parents=True, exist_ok=True)
        cuts = detect_cuts(args.video)
        (mdir / "candidate_cuts.json").write_text(json.dumps({"candidate_cuts": cuts}))
        cmd = [sys.executable, str(HERE / "measure_tracks.py"), str(args.video), "--output-dir", str(mdir), "--cuts-json", str(mdir / "candidate_cuts.json")]
        for tr in spec.get("tracks", []):
            cmd += ["--track", f"{tr['label']}:{tr['t']}:{tr['x']}:{tr['y']}"]
        for c in criteria:
            if "window" in c:
                cmd += ["--window", f"{c['window'][0]}:{c['window'][1]}"]
        r = subprocess.run(cmd, text=True, capture_output=True)
        if r.returncode != 0:
            sys.exit(f"measure_tracks 失败：\n{r.stderr[-2000:]}")

    motion = read_csv(mdir / "motion.csv"); tracks = read_csv(mdir / "tracks.csv")
    cuts_info = json.loads((mdir / "cuts.json").read_text()) if (mdir / "cuts.json").is_file() else []
    windows = json.loads((mdir / "windows.json").read_text())["windows"]
    t = fcol(motion, "time"); energy = fcol(motion, "energy"); eye = fcol(tracks, "eye_dist_W"); tt = fcol(tracks, "time")
    person = fcol(tracks, "person")
    base = float(np.nanmedian(energy[1:])) if len(energy) > 1 else 0.0
    hard_cuts = [c["time"] for c in cuts_info if c["verdict"] == "hard_cut_likely"]
    ref_motion = read_csv(args.ref_measure_dir / "motion.csv") if args.ref_measure_dir and (args.ref_measure_dir / "motion.csv").is_file() else None

    def in_win(arr_t, a, b):
        return (arr_t >= a) & (arr_t <= b)

    def find_window(a, b):
        for w in windows:
            if abs(w["window"][0] - a) < 0.03 and abs(w["window"][1] - b) < 0.03:
                return w
        return None

    results = []
    for c in criteria:
        cid, ctype = c.get("id", c["type"]), c["type"]
        ok, measured, expect = None, "", ""
        try:
            if ctype == "cut_within":
                a, b = c["range"]; hits = [x for x in hard_cuts if a <= x <= b]
                ok, measured, expect = bool(hits), f"硬切 {hits or '无'}", f"[{a},{b}] 内有硬切"
            elif ctype == "no_cut_between":
                a, b = c["range"]; hits = [x for x in hard_cuts if a <= x <= b]
                ok, measured, expect = not hits, f"硬切 {hits or '无'}", f"[{a},{b}] 内无硬切"
            elif ctype == "motion_onset_within":
                a, b = c["range"]; factor = c.get("factor", 3.0)
                idx = np.where((energy >= factor * base) & (t >= c.get("search_from", 0.0)))[0]
                onset = float(t[idx[0]]) if len(idx) else None
                ok, measured, expect = onset is not None and a <= onset <= b, f"起始 {onset}（基线 {base:.2f}×{factor}）", f"[{a},{b}]"
            elif ctype == "motion_peak_within":
                a, b = c["range"]; m = in_win(t, c.get("search", [0, 1e9])[0], c.get("search", [0, 1e9])[1])
                pk = float(t[m][int(np.nanargmax(energy[m]))]); ok, measured, expect = a <= pk <= b, f"峰值 {pk}", f"[{a},{b}]"
            elif ctype == "high_motion_duration_min":
                a, b = c["window"]; factor = c.get("factor", 2.0); m = in_win(t, a, b)
                dt = float(np.median(np.diff(t))) if len(t) > 1 else 0
                dur = float((energy[m] >= factor * base).sum() * dt)
                ok, measured, expect = dur >= c["min_seconds"], f"{dur:.2f}s", f"≥{c['min_seconds']}s"
            elif ctype in ("hold_min", "no_hold"):
                a, b = c["window"]; w = find_window(a, b)
                holds = [h for h in (w["camera"]["holds"] if w else [])]
                longest = max([h[1] - h[0] for h in holds], default=0.0)
                if ctype == "hold_min":
                    ok, measured, expect = longest >= c["min_seconds"], f"最长停顿 {longest:.2f}s {holds}", f"≥{c['min_seconds']}s"
                else:
                    ok, measured, expect = longest < c.get("max_seconds", 0.2), f"最长停顿 {longest:.2f}s {holds}", f"<{c.get('max_seconds', 0.2)}s"
            elif ctype == "eye_dist_min_by":
                idx = np.where(eye >= c["min"])[0]; first = float(tt[idx[0]]) if len(idx) else None
                ok, measured, expect = first is not None and first <= c["by"], f"首次达到 {first}", f"≤{c['by']}s 时眼距≥{c['min']}W"
            elif ctype == "eye_dist_range_at":
                m = in_win(tt, c["t"] - c.get("tol", 0.1), c["t"] + c.get("tol", 0.1)); vals = eye[m][~np.isnan(eye[m])]
                v = float(np.median(vals)) if len(vals) else None
                ok, measured, expect = v is not None and c["min"] <= v <= c.get("max", 1.0), f"眼距 {v}", f"[{c['min']},{c.get('max', 1.0)}] @ {c['t']}s"
            elif ctype == "person_visible_frac_min":
                a, b = c["window"]; m = in_win(tt, a, b); frac = float(np.nanmean(person[m])) if m.any() else 0
                ok, measured, expect = frac >= c["min"], f"{frac:.2f}", f"≥{c['min']}"
            elif ctype in ("track_range_max", "track_coverage_min"):
                a, b = c["window"]; w = find_window(a, b); trk = (w or {}).get("lk_tracks", {}).get(c["label"])
                if not trk:
                    ok, measured = None, "跟踪点缺失或覆盖不足"
                elif ctype == "track_range_max":
                    ok, measured, expect = trk["tracked_frac"] >= 0.5 and max(trk["range_xy"]) <= c["max"], f"漂移 {trk['range_xy']} 覆盖 {trk['tracked_frac']}", f"≤{c['max']} 且覆盖≥0.5"
                else:
                    ok, measured, expect = trk["tracked_frac"] >= c["min"], f"覆盖 {trk['tracked_frac']}", f"≥{c['min']}"
            elif ctype == "energy_ratio_vs_ref_min":
                if ref_motion is None:
                    ok, measured = None, "缺 --ref-measure-dir"
                else:
                    a, b = c["ref_window"]; rt = fcol(ref_motion, "time"); re_ = fcol(ref_motion, "energy")
                    ref_mean = float(np.nanmean(re_[in_win(rt, a, b)]))
                    mapped = np.array([to_ref(x) for x in t]); out_mean = float(np.nanmean(energy[in_win(mapped, a, b)]))
                    ratio = out_mean / (ref_mean + 1e-6)
                    ok, measured, expect = ratio >= c["min"], f"产物 {out_mean:.2f} / 参考 {ref_mean:.2f} = {ratio:.2f}", f"≥{c['min']}"
            elif ctype in ("roi_motion_onset_within", "roi_quiet_until", "roi_energy_ratio_vs_ref_min", "roi_energy_min",
                           "roi_occupancy_onset_within", "roi_occupancy_quiet_until", "roi_occupancy_at"):
                rt_, rv, rd = roi_series(args.video, c["roi"], mdir, c.get("dark_thr", 70))
                rbase = float(np.median(rv[1:])) if len(rv) > 1 else 0.0
                if ctype == "roi_occupancy_onset_within":
                    a, b = c["range"]; idx = np.where(rd >= c.get("min_frac", 0.10))[0]
                    onset = float(rt_[idx[0]]) if len(idx) else None
                    ok, measured, expect = onset is not None and a <= onset <= b, f"暗像素占比首次≥{c.get('min_frac', 0.10):.0%} 于 {onset}", f"[{a},{b}]"
                elif ctype == "roi_occupancy_quiet_until":
                    m = rt_ < c["until"]; peak = float(rd[m].max()) if m.any() else 0.0
                    ok, measured, expect = peak < c.get("max_frac", 0.08), f"{c['until']}s 前占比峰值 {peak:.1%}", f"<{c.get('max_frac', 0.08):.0%}"
                elif ctype == "roi_occupancy_at":
                    m = in_win(rt_, c["t"] - c.get("tol", 0.08), c["t"] + c.get("tol", 0.08)); v = float(np.median(rd[m])) if m.any() else None
                    ok, measured, expect = v is not None and c["min"] <= v <= c.get("max", 1.0), f"占比 {v:.1%}" if v is not None else "无帧", f"[{c['min']:.0%},{c.get('max', 1.0):.0%}] @ {c['t']}s"
                elif ctype == "roi_motion_onset_within":
                    a, b = c["range"]; factor = c.get("factor", 3.0)
                    idx = np.where((rv >= factor * rbase) & (rt_ >= c.get("search_from", 0.0)))[0]
                    onset = float(rt_[idx[0]]) if len(idx) else None
                    ok, measured, expect = onset is not None and a <= onset <= b, f"ROI 起始 {onset}（基线 {rbase:.2f}×{factor}）", f"[{a},{b}]"
                elif ctype == "roi_quiet_until":
                    factor = c.get("factor", 2.0); m = rt_ < c["until"]
                    peak = float(rv[m].max()) if m.any() else 0.0
                    ok, measured, expect = peak < factor * rbase, f"{c['until']}s 前 ROI 峰值 {peak:.2f}（基线 {rbase:.2f}）", f"<{factor}×基线"
                elif ctype == "roi_energy_min":
                    a, b = c["window"]; m = in_win(rt_, a, b); mean_v = float(rv[m].mean()) if m.any() else 0.0
                    ok, measured, expect = mean_v >= c["min"], f"ROI 均值 {mean_v:.2f}", f"≥{c['min']}"
                else:
                    if not args.ref_measure_dir:
                        ok, measured = None, "缺 --ref-measure-dir"
                    else:
                        ref_video = Path(json.loads((args.ref_measure_dir / "windows.json").read_text())["video"])
                        rrt, rrv, _ = roi_series(ref_video, c["roi"], args.ref_measure_dir, c.get("dark_thr", 70))
                        a, b = c["ref_window"]; ref_mean = float(rrv[in_win(rrt, a, b)].mean())
                        mapped = np.array([to_ref(x) for x in rt_]); out_mean = float(rv[in_win(mapped, a, b)].mean())
                        ratio = out_mean / (ref_mean + 1e-6)
                        ok, measured, expect = ratio >= c["min"], f"产物 {out_mean:.2f} / 参考 {ref_mean:.2f} = {ratio:.2f}", f"≥{c['min']}"
            elif ctype == "manual":
                ok, measured, expect = None, "待人工看帧", c.get("text", "")
            else:
                ok, measured = None, f"未知类型 {ctype}"
        except Exception as exc:  # 单条失败不影响其他条
            ok, measured = None, f"计算失败：{exc}"
        results.append({"id": cid, "type": ctype, "pass": ok, "measured": measured, "expect": expect, "note": c.get("note", "")})

    passed = sum(1 for r in results if r["pass"] is True); failed = sum(1 for r in results if r["pass"] is False)
    pending = sum(1 for r in results if r["pass"] is None)
    lines = [f"# 验收核对：{args.video.name}", "", f"测量目录：`{mdir}`　硬切判定：{hard_cuts or '无'}　能量基线（中值）：{base:.2f}", "",
             f"**通过 {passed} / 未通过 {failed} / 待人工或无法计算 {pending}**", "",
             "| 项 | 类型 | 判定 | 测得 | 要求 | 备注 |", "|---|---|---|---|---|---|"]
    for r in results:
        mark = "✅" if r["pass"] is True else ("❌" if r["pass"] is False else "⏳")
        lines.append(f"| {r['id']} | {r['type']} | {mark} | {r['measured']} | {r['expect']} | {r['note']} |")
    report = "\n".join(lines) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True); args.report.write_text(report, encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps({"video": str(args.video), "measure_dir": str(mdir), "results": results}, ensure_ascii=False, indent=2))
    print(report)
    return 1 if (args.strict and failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
