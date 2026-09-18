#!/usr/bin/env python
"""测量层：把"镜头在动还是人在动""指尖到底有没有固定在画面某处"变成数字，而不是看图猜。

依赖 text2video 虚拟环境（opencv、numpy、rtmlib；`workon text2video`）。只读视频、只写 CSV/JSON/PNG，不做任何付费动作。

用法：
  python measure_tracks.py VIDEO --output-dir DIR [--start S --end E]
      [--track 标签:时间:x:y ...]      # 在某时刻以归一化坐标播种一个特征点，用 LK 光流前后双向跟踪（指尖、剑尖等姿态模型抓不准的点）
      [--window 起:止 ...]             # 需要汇总的时间窗；不给则用候选切点 ±margin 自动生成
      [--cuts-json manifest.json]      # 读取 prepare_evidence.py 的 candidate_cuts，判别"硬切"还是"持续运动误报"
      [--time-map a:b,c:d,...]         # 本视频时间 → 参考时间的分段线性映射（分析生成产物时用），输出 ref_time 列
      [--pose-mode balanced|performance|lightweight] [--min-score 0.45] [--analysis-width 640]

产物（都在 --output-dir）：
  motion.csv      每帧：全局平移 dx/dy（%W/s）、径向缩放 zoom、总能量、去全局后的主体残差、相邻帧绝对差、直方图相关
  tracks.csv      每帧：人物是否检出、可见部位、包围盒高度占比、各关键点归一化 xy 与置信度、LK 跟踪点 xy 与状态
  cuts.json       每个候选切点的尖峰比、邻域能量、直方图相关与判定
  windows.json    每个时间窗：运镜方向/幅度/停顿段、镜头 vs 主体主导比、景别代理（起→止）、每个关键点/跟踪点的可见率、均值、漂移范围
  overlay_*.png   跟踪点轨迹叠画在窗口中间帧上（按时间渐变着色，每 0.25 s 标时间）
  plot_tracks.png 关键点与跟踪点的 x(t)、y(t) 曲线
所有坐标为归一化屏幕坐标（0–1，原点左上）。"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np

# rtmlib Wholebody(to_openpose=True) 134 点：0–17 身体（OpenPose18）、18–23 脚、24–91 脸、92–112 左手、113–133 右手
LANDMARKS = {
    "nose": 0, "neck": 1, "r_eye": 14, "l_eye": 15,
    "r_shoulder": 2, "r_elbow": 3, "r_wrist": 4,
    "l_shoulder": 5, "l_elbow": 6, "l_wrist": 7,
    "r_hip": 8, "r_knee": 9, "r_ankle": 10,
    "l_hip": 11, "l_knee": 12, "l_ankle": 13,
    "l_index_tip": 92 + 8, "l_middle_tip": 92 + 12,
    "r_index_tip": 113 + 8, "r_middle_tip": 113 + 12,
}
HAND_POINTS = {"l_index_tip", "l_middle_tip", "r_index_tip", "r_middle_tip"}
KPT_THR = 0.3


def parse_window(text: str) -> tuple[float, float]:
    a, b = text.split(":", 1)
    a, b = float(a), float(b)
    if a < 0 or b <= a:
        raise argparse.ArgumentTypeError("窗口须满足 0 <= 起 < 止")
    return a, b


def parse_track(text: str) -> tuple[str, float, float, float]:
    label, t, x, y = text.split(":")
    return label, float(t), float(x), float(y)


def parse_time_map(text: str | None):
    if not text:
        return None
    pairs = sorted(tuple(float(v) for v in p.split(":")) for p in text.split(","))
    xs = np.array([p[0] for p in pairs]); ys = np.array([p[1] for p in pairs])
    return lambda t: float(np.interp(t, xs, ys))


def merge_windows(windows: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[list[float]] = []
    for a, b in sorted(windows):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def shot_scale_label(vis: dict[str, bool], eye_dist: float | None = None) -> str:
    """景别代理：脸可见时用两眼间距占画幅宽度比例（近景里躯干关节常被模型幻觉到画内，不可靠）；否则按在画幅内的可见部位。"""
    if eye_dist is not None:
        if eye_dist >= 0.05:
            return "CU/面部或胸上"
        if eye_dist >= 0.03:
            return "MCU/胸上"
        if eye_dist >= 0.018:
            return "MS/腰上"
    if vis["ankle"]:
        return "WS/全身"
    if vis["knee"]:
        return "MS+/膝上"
    if vis["hip"]:
        return "MS/腰上"
    if vis["shoulder"]:
        return "MCU/胸上"
    if vis["face"]:
        return "CU/面部"
    return "无人或不可判"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--track", action="append", type=parse_track, default=[])
    ap.add_argument("--window", action="append", type=parse_window, default=[])
    ap.add_argument("--cuts-json", type=Path)
    ap.add_argument("--cut-margin", type=float, default=0.35)
    ap.add_argument("--time-map", type=str, default=None)
    ap.add_argument("--pose-mode", default="balanced")
    ap.add_argument("--min-score", type=float, default=0.45)
    ap.add_argument("--analysis-width", type=int, default=640)
    ap.add_argument("--hold-ratio", type=float, default=0.2, help="能量低于窗口峰值的该比例且持续 ≥0.2 s 记为停顿")
    args = ap.parse_args()

    if not args.video.is_file():
        ap.error(f"视频不存在：{args.video}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    time_map = parse_time_map(args.time_map)

    cap = cv2.VideoCapture(str(args.video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total / fps
    end = min(args.end if args.end is not None else duration, duration)
    f0 = int(round(args.start * fps)); f1 = int(round(end * fps))
    if f1 - f0 > 600:
        print(f"[warn] 分析范围 {f1 - f0} 帧较长，建议用 --start/--end 缩到争议段", file=sys.stderr)
    cap.set(cv2.CAP_PROP_POS_FRAMES, f0)

    from rtmlib import Wholebody  # 延迟导入，便于先报参数错误
    wb = Wholebody(to_openpose=True, mode=args.pose_mode, backend="onnxruntime", device="cpu")

    aw = args.analysis_width; ah = int(H * aw / W)
    grays: list[np.ndarray] = []
    frames_mid: dict[int, np.ndarray] = {}
    motion_rows = []; track_rows = []
    prev = None; prev_hist = None
    ys, xs = np.mgrid[0:ah, 0:aw]; rx, ry = xs - aw / 2, ys - ah / 2; r2 = rx ** 2 + ry ** 2 + 1e-6

    for fi in range(f0, f1):
        ok, fr = cap.read()
        if not ok:
            break
        t = fi / fps
        small = cv2.resize(fr, (aw, ah)); g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        grays.append(g)
        hist = cv2.calcHist([g], [0], None, [64], [0, 256]); cv2.normalize(hist, hist)
        row = {"frame": fi, "time": round(t, 4)}
        if time_map:
            row["ref_time"] = round(time_map(t), 4)
        if prev is not None:
            flow = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            fx, fy = flow[..., 0], flow[..., 1]
            dx, dy = float(np.median(fx)), float(np.median(fy))
            zoom = float(np.median(((fx - dx) * rx + (fy - dy) * ry) / r2))
            mag = np.sqrt(fx ** 2 + fy ** 2)
            resid = float(np.sqrt((fx - dx) ** 2 + (fy - dy) ** 2).mean())
            k = 100.0 * fps / aw
            row.update({
                "dx_pctW_s": round(dx * k, 2), "dy_pctW_s": round(dy * k, 2),
                "zoom_pct_s": round(zoom * fps * 100, 3),
                "energy": round(float(mag.mean()) * k, 2), "residual": round(resid * k, 2),
                "absdiff": round(float(cv2.absdiff(prev, g).mean()), 2),
                "hist_corr": round(float(cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)), 3),
            })
        else:
            row.update({"dx_pctW_s": 0, "dy_pctW_s": 0, "zoom_pct_s": 0, "energy": 0, "residual": 0, "absdiff": 0, "hist_corr": 1.0})
        motion_rows.append(row)
        prev, prev_hist = g, hist

        # 姿态
        trow = {"frame": fi, "time": round(t, 4)}
        if time_map:
            trow["ref_time"] = row["ref_time"]
        kps, scores = wb(fr)
        found = False
        if len(kps):
            body = scores[:, :18].mean(axis=1); i = int(np.argmax(body))
            if body[i] >= args.min_score:
                found = True
                k = kps[i] / np.array([W, H], dtype=np.float32); s = scores[i]
                good = s[:18] >= KPT_THR
                if good.any():
                    pts = k[:18][good]
                    trow["bbox_h_ratio"] = round(float(pts[:, 1].max() - pts[:, 1].min()), 3)
                    trow["bbox_cx"] = round(float(pts[:, 0].mean()), 3); trow["bbox_cy"] = round(float(pts[:, 1].mean()), 3)
                def inframe(*ids):  # 置信度过门槛且落在画幅内；模型会给画外关节"幻觉"坐标
                    return any(s[j] >= 0.5 and 0 <= k[j][0] <= 1 and 0 <= k[j][1] <= 1 for j in ids)
                vis = {"face": inframe(0, 14, 15), "shoulder": inframe(2, 5), "hip": inframe(8, 11), "knee": inframe(9, 12), "ankle": inframe(10, 13)}
                eye_dist = None
                if s[14] >= 0.5 and s[15] >= 0.5 and 0 <= k[14][0] <= 1 and 0 <= k[15][0] <= 1:
                    eye_dist = float(np.linalg.norm(k[14] - k[15]))
                    trow["eye_dist_W"] = round(eye_dist, 4)
                trow["scale_proxy"] = shot_scale_label(vis, eye_dist)
                for name, idx in LANDMARKS.items():
                    trow[f"{name}_x"] = round(float(k[idx][0]), 4); trow[f"{name}_y"] = round(float(k[idx][1]), 4)
                    trow[f"{name}_s"] = round(float(s[idx]), 2)
        trow["person"] = int(found)
        if not found:
            trow["scale_proxy"] = "无人或不可判"
        track_rows.append(trow)

    n = len(grays)
    times = np.array([r["time"] for r in motion_rows])

    # LK 双向点跟踪（在分析分辨率上）
    lk_params = dict(winSize=(31, 31), maxLevel=4, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    lk_tracks: dict[str, dict] = {}
    for label, t_seed, x, y in args.track:
        si = int(round(t_seed * fps)) - f0
        if not (0 <= si < n):
            print(f"[warn] 跟踪点 {label} 的播种时间 {t_seed}s 不在分析范围内，跳过", file=sys.stderr)
            continue
        xy = np.full((n, 2), np.nan, dtype=np.float32); status = np.zeros(n, dtype=np.int8)
        p = np.array([[[x * aw, y * ah]]], dtype=np.float32); xy[si] = p[0, 0]; status[si] = 1
        for direction in (1, -1):
            cur = p.copy(); j = si
            while 0 <= j + direction < n:
                nxt, st, _ = cv2.calcOpticalFlowPyrLK(grays[j], grays[j + direction], cur, None, **lk_params)
                j += direction
                if st is None or st[0, 0] == 0:
                    break
                # 前后一致性校验：回跟一步，误差 > 2 px 视为丢失
                back, st2, _ = cv2.calcOpticalFlowPyrLK(grays[j], grays[j - direction], nxt, None, **lk_params)
                if st2 is None or st2[0, 0] == 0 or np.linalg.norm(back - cur) > 3.0:
                    break
                cur = nxt; xy[j] = cur[0, 0]; status[j] = 1
        xy_norm = xy / np.array([aw, ah], dtype=np.float32)
        lk_tracks[label] = {"seed": {"time": t_seed, "x": x, "y": y}, "xy": xy_norm, "status": status}
        for r, (px, py), st in zip(track_rows, xy_norm, status):
            r[f"lk_{label}_x"] = round(float(px), 4) if st else ""
            r[f"lk_{label}_y"] = round(float(py), 4) if st else ""
            r[f"lk_{label}_ok"] = int(st)

    # 候选切点判别
    cuts_out = []
    candidate_cuts: list[float] = []
    if args.cuts_json and args.cuts_json.is_file():
        candidate_cuts = list(json.loads(args.cuts_json.read_text())["candidate_cuts"])
    absd = np.array([r["absdiff"] for r in motion_rows]); hc = np.array([r["hist_corr"] for r in motion_rows])
    for ct in candidate_cuts:
        ci = int(round(ct * fps)) - f0
        if not (1 <= ci < n):
            continue
        # showinfo 给的是切后第一帧的 pts；absdiff[ci] 是 ci 与 ci-1 的差
        lo = max(1, ci - 4); hi = min(n, ci + 5)
        neigh = np.concatenate([absd[lo:max(lo, ci - 1)], absd[min(hi, ci + 2):hi]])
        neigh_med = float(np.median(neigh)) if len(neigh) else 0.0
        spike = float(absd[ci] / (neigh_med + 1e-6))
        if spike >= 2.5 and hc[ci] < 0.7:
            verdict = "hard_cut_likely"
        elif neigh_med >= 0.5 * absd[ci]:
            verdict = "sustained_motion_not_cut"
        else:
            verdict = "ambiguous_check_dense_frames"
        cuts_out.append({"time": ct, "frame": ci + f0, "absdiff": round(float(absd[ci]), 2), "neighbor_median": round(neigh_med, 2),
                         "spike_ratio": round(spike, 2), "hist_corr": round(float(hc[ci]), 3), "verdict": verdict})

    # 时间窗
    windows = list(args.window)
    if not windows:
        windows = [(max(args.start, c - args.cut_margin), min(end, c + args.cut_margin)) for c in candidate_cuts] or [(args.start, end)]
    windows = merge_windows(windows)

    def col(rows, key):
        return np.array([r.get(key, np.nan) if r.get(key, "") != "" else np.nan for r in rows], dtype=np.float64)

    win_out = []
    for wa, wb_ in windows:
        m = (times >= wa) & (times <= wb_)
        if m.sum() < 2:
            continue
        mr = [r for r, keep in zip(motion_rows, m) if keep]; tr = [r for r, keep in zip(track_rows, m) if keep]
        e = col(mr, "energy"); res = col(mr, "residual"); dx = col(mr, "dx_pctW_s"); dy = col(mr, "dy_pctW_s"); zm = col(mr, "zoom_pct_s")
        glob = np.sqrt(dx ** 2 + dy ** 2)
        # 停顿段
        thr = args.hold_ratio * float(np.nanmax(e)) if np.nanmax(e) > 0 else 0
        holds = []; run_start = None
        for tt, ev in zip(times[m], e):
            if ev <= thr:
                run_start = tt if run_start is None else run_start
            else:
                if run_start is not None and tt - run_start >= 0.2:
                    holds.append([round(run_start, 3), round(tt, 3)])
                run_start = None
        if run_start is not None and times[m][-1] - run_start >= 0.2:
            holds.append([round(run_start, 3), round(float(times[m][-1]), 3)])
        mdx, mdy = float(np.nanmean(dx)), float(np.nanmean(dy))
        direction = []
        if abs(mdy) > 3: direction.append("画面内容向下流动=镜头向上重构图" if mdy > 0 else "画面内容向上流动=镜头向下重构图")
        if abs(mdx) > 3: direction.append("画面内容向右流动=镜头向左" if mdx > 0 else "画面内容向左流动=镜头向右")
        if abs(float(np.nanmean(zm))) > 0.5: direction.append("尺度增大(推/变焦/靠近)" if np.nanmean(zm) > 0 else "尺度减小(拉/变焦/远离)")
        scales = [r.get("scale_proxy", "") for r in tr]
        w = {
            "window": [round(wa, 3), round(wb_, 3)],
            "frames": int(m.sum()),
            "camera": {
                "mean_dx_pctW_s": round(mdx, 2), "mean_dy_pctW_s": round(mdy, 2), "mean_zoom_pct_s": round(float(np.nanmean(zm)), 3),
                "peak_global_pctW_s": round(float(np.nanmax(glob)), 2), "peak_time": round(float(times[m][int(np.nanargmax(glob))]), 3),
                "direction_hint": direction or ["全局平移不显著"],
                "global_over_residual": round(float(np.nanmean(glob) / (np.nanmean(res) + 1e-6)), 2),
                "dominance": "镜头/整体运动主导" if np.nanmean(glob) > 1.5 * np.nanmean(res) else ("主体运动主导" if np.nanmean(res) > 1.5 * np.nanmean(glob) else "混合，需看背景锚点"),
                "holds": holds,
                "caveat": "全局平移取光流中值；强运动模糊段中值会塌向 0，此时 peak/energy 只说明'有大运动'，方向以密集帧背景锚点为准",
            },
            "scale_proxy": {"start": scales[0], "end": scales[-1], "person_visible_frac": round(float(np.mean([r["person"] for r in tr])), 2),
                            "note": "人物检出率低且运动能量高：该段为强运动/模糊，姿态与 LK 不可靠，只能用密集帧目视描述，且不能声称任何屏幕锁定" if np.mean([r["person"] for r in tr]) < 0.6 and np.nanmax(e) > 2 * np.nanmedian(e) else ""},
            "landmarks": {}, "lk_tracks": {},
        }
        for name in LANDMARKS:
            sx, sy, ss = col(tr, f"{name}_x"), col(tr, f"{name}_y"), col(tr, f"{name}_s")
            ok = ss >= KPT_THR
            if ok.sum() < 2:
                continue
            w["landmarks"][name] = {
                "visible_frac": round(float(ok.mean()), 2),
                "mean_xy": [round(float(np.nanmean(sx[ok])), 3), round(float(np.nanmean(sy[ok])), 3)],
                "std_xy": [round(float(np.nanstd(sx[ok])), 3), round(float(np.nanstd(sy[ok])), 3)],
                "range_xy": [round(float(np.ptp(sx[ok])), 3), round(float(np.ptp(sy[ok])), 3)],
                "first_xy": [round(float(sx[ok][0]), 3), round(float(sy[ok][0]), 3)],
                "last_xy": [round(float(sx[ok][-1]), 3), round(float(sy[ok][-1]), 3)],
                "note": "手部关键点在 256×192 全身模型上精度有限，指尖以 LK 跟踪点为准" if name in HAND_POINTS else "",
            }
        for label, trk in lk_tracks.items():
            xy = trk["xy"][m]; st = trk["status"][m].astype(bool)
            if st.sum() < 2:
                continue
            rng = [round(float(np.ptp(xy[st, 0])), 3), round(float(np.ptp(xy[st, 1])), 3)]
            if st.mean() < 0.5:
                lock = f"跟踪覆盖仅 {st.mean():.0%}，特征点在运动模糊/遮挡中丢失，不能对该窗口下跟踪结论"
            else:
                lock = "screen-locked 候选" if max(rng) < 0.05 else ("loose tracking 候选" if max(rng) < 0.15 else "非跟踪关系/大幅漂移")
            w["lk_tracks"][label] = {
                "tracked_frac": round(float(st.mean()), 2), "mean_xy": [round(float(xy[st, 0].mean()), 3), round(float(xy[st, 1].mean()), 3)],
                "range_xy": rng, "first_xy": [round(float(xy[st][0, 0]), 3), round(float(xy[st][0, 1]), 3)],
                "last_xy": [round(float(xy[st][-1, 0]), 3), round(float(xy[st][-1, 1]), 3)], "lock_hint": lock,
            }
        win_out.append(w)

    # 写文件
    def write_csv(path: Path, rows: list[dict]):
        keys: list[str] = []
        for r in rows:
            for k in r:
                if k not in keys:
                    keys.append(k)
        with path.open("w", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=keys); wr.writeheader(); wr.writerows(rows)

    write_csv(args.output_dir / "motion.csv", motion_rows)
    write_csv(args.output_dir / "tracks.csv", track_rows)
    (args.output_dir / "cuts.json").write_text(json.dumps(cuts_out, ensure_ascii=False, indent=2) + "\n")
    (args.output_dir / "windows.json").write_text(json.dumps({
        "video": str(args.video.resolve()), "fps": fps, "size": [W, H], "range": [args.start, round(end, 4)],
        "analysis_width": aw, "units": "坐标归一化 0–1；速度为画幅宽度百分比/秒；zoom 为每秒径向缩放百分比",
        "windows": win_out}, ensure_ascii=False, indent=2) + "\n")

    # 轨迹叠画与曲线图
    cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    want = {int(round(((a + b) / 2) * fps)) for a, b in windows}
    for fi in range(f0, f1):
        ok, fr = cap.read()
        if not ok:
            break
        if fi in want:
            frames_mid[fi] = fr
    for wi, (wa, wb_) in enumerate(windows, 1):
        mid = int(round(((wa + wb_) / 2) * fps))
        if mid not in frames_mid or not lk_tracks:
            continue
        img = frames_mid[mid].copy()
        m = (times >= wa) & (times <= wb_); idx = np.where(m)[0]
        for li, (label, trk) in enumerate(lk_tracks.items()):
            pts = []
            for j in idx:
                if trk["status"][j]:
                    pts.append((j, trk["xy"][j]))
            for a_, b_ in zip(pts, pts[1:]):
                frac = (a_[0] - idx[0]) / max(1, len(idx))
                color = (int(255 * (1 - frac)), int(80 + 100 * li) % 255, int(255 * frac))
                cv2.line(img, (int(a_[1][0] * W), int(a_[1][1] * H)), (int(b_[1][0] * W), int(b_[1][1] * H)), color, 2, cv2.LINE_AA)
            for j, p in pts:
                if abs((times[j] * 4) - round(times[j] * 4)) < 0.5 / fps:
                    cv2.circle(img, (int(p[0] * W), int(p[1] * H)), 4, (255, 255, 255), -1)
                    cv2.putText(img, f"{times[j]:.2f}", (int(p[0] * W) + 6, int(p[1] * H) - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(img, f"{label}: blue->red = {wa:.2f}s->{wb_:.2f}s", (10, 22 + 20 * li), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imwrite(str(args.output_dir / f"overlay_w{wi:02d}_{wa:.2f}-{wb_:.2f}.png"), img)

    # 简易曲线图：每条曲线一行，x 轴时间
    series = []
    for name in ("nose", "l_wrist", "r_wrist"):
        series.append((f"{name}.y", col(track_rows, f"{name}_y"), col(track_rows, f"{name}_s") >= KPT_THR))
        series.append((f"{name}.x", col(track_rows, f"{name}_x"), col(track_rows, f"{name}_s") >= KPT_THR))
    for label, trk in lk_tracks.items():
        st = trk["status"].astype(bool)
        series.append((f"lk_{label}.y", trk["xy"][:, 1].astype(np.float64), st))
        series.append((f"lk_{label}.x", trk["xy"][:, 0].astype(np.float64), st))
    series.append(("energy(norm)", col(motion_rows, "energy") / (np.nanmax(col(motion_rows, "energy")) + 1e-6), np.ones(n, bool)))
    series.append(("dy(norm)", 0.5 + col(motion_rows, "dy_pctW_s") / (2 * np.nanmax(np.abs(col(motion_rows, "dy_pctW_s"))) + 1e-6), np.ones(n, bool)))
    rowh, pw, left = 70, 900, 150
    canvas = np.full((rowh * len(series) + 30, left + pw + 20, 3), 30, np.uint8)
    for si, (label, vals, okm) in enumerate(series):
        y0 = si * rowh + 10
        cv2.rectangle(canvas, (left, y0), (left + pw, y0 + rowh - 15), (60, 60, 60), 1)
        cv2.putText(canvas, label, (8, y0 + rowh // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1, cv2.LINE_AA)
        prev_pt = None
        for j in range(n):
            if not okm[j] or np.isnan(vals[j]):
                prev_pt = None; continue
            px = left + int((times[j] - times[0]) / max(1e-6, times[-1] - times[0]) * pw)
            py = y0 + int(np.clip(vals[j], 0, 1) * (rowh - 15))
            if prev_pt is not None:
                cv2.line(canvas, prev_pt, (px, py), (90, 200, 255), 1, cv2.LINE_AA)
            prev_pt = (px, py)
        for c in candidate_cuts:
            if times[0] <= c <= times[-1]:
                px = left + int((c - times[0]) / max(1e-6, times[-1] - times[0]) * pw)
                cv2.line(canvas, (px, y0), (px, y0 + rowh - 15), (0, 0, 255), 1)
    for k in range(0, int(times[-1] * 4) + 1):
        tt = k / 4
        if tt < times[0]:
            continue
        px = left + int((tt - times[0]) / max(1e-6, times[-1] - times[0]) * pw)
        cv2.putText(canvas, f"{tt:.2f}", (px - 12, canvas.shape[0] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.imwrite(str(args.output_dir / "plot_tracks.png"), canvas)

    print(json.dumps({"output_dir": str(args.output_dir), "frames": n, "windows": [w["window"] for w in win_out],
                      "cuts": [(c["time"], c["verdict"]) for c in cuts_out],
                      "lk_tracks": [{"window": w["window"], **{k: v["lock_hint"] for k, v in w["lk_tracks"].items()}} for w in win_out],
                      "person_visible_frac": [{"window": w["window"], "frac": w["scale_proxy"]["person_visible_frac"]} for w in win_out]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
