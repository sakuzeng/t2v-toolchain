"""参考片运镜/停顿量化：光流全局运动（摇/移/推拉）+ 帧差能量（停顿）→ 每镜一行 markdown。
用法：python3 -m t2v motion <video> --shots <shots.txt: "idx start end" 每行> [--width 320] [--md out.md] [--csv out.csv]
运动量单位：画幅宽度百分比/秒（%W/s）。全局运动 = 光流中值（大远景近似机位运动；近景/特写里主体占满画面时会混入主体运动，表里标注）。
"""
import argparse
import csv

from .deps import require_cv2


def analyze(video, shots, width=320):
    cv2, np = require_cv2()
    cap = cv2.VideoCapture(video); fps = cap.get(cv2.CAP_PROP_FPS)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    scale = width / W; h = int(H * scale)
    prev = None; rows = []  # t, dx, dy, zoom, energy, residual
    n = 0
    while True:
        ok, fr = cap.read()
        if not ok: break
        g = cv2.cvtColor(cv2.resize(fr, (width, h)), cv2.COLOR_BGR2GRAY)
        if prev is not None:
            flow = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            fx, fy = flow[..., 0], flow[..., 1]
            mag = np.sqrt(fx**2 + fy**2)
            dx, dy = np.median(fx), np.median(fy)              # 全局平移（px/frame，缩放后）
            ys, xs = np.mgrid[0:h, 0:width]; rx, ry = xs - width/2, ys - h/2
            r2 = rx**2 + ry**2 + 1e-6
            zoom = np.median(((fx - dx) * rx + (fy - dy) * ry) / r2)   # 径向分量 → 推(+)/拉(-)，1/frame
            energy = mag.mean()
            resid = np.sqrt((fx - dx)**2 + (fy - dy)**2).mean()       # 去掉全局平移后的主体运动
            t = n / fps
            rows.append((t, dx / width * 100 * fps, dy / width * 100 * fps, zoom * fps * 100, energy / width * 100 * fps, resid / width * 100 * fps))
        prev = g; n += 1
    cap.release()
    arr = np.array(rows)
    out = []
    for idx, a, b in shots:
        seg = arr[(arr[:, 0] >= a) & (arr[:, 0] < b)]
        if len(seg) < 2: continue
        # 切点附近 2 帧剔除（场景切换的假光流）
        seg = seg[1:-1] if len(seg) > 4 else seg
        dx, dy, zm = seg[:, 1].mean(), seg[:, 2].mean(), seg[:, 3].mean()
        en = seg[:, 4]; res = seg[:, 5]
        # 运镜判定
        parts = []
        if abs(dx) > 8: parts.append(("右摇/右移" if dx < 0 else "左摇/左移") + f" {abs(dx):.0f}%W/s")   # 内容左移=镜头右摇
        if abs(dy) > 8: parts.append(("下摇/下移" if dy < 0 else "上摇/上移") + f" {abs(dy):.0f}%W/s")   # 内容上移=镜头下摇…按内容运动标注见下
        if abs(zm) > 4: parts.append(("推" if zm > 0 else "拉") + f" {abs(zm):.0f}%/s")
        cam = " + ".join(parts) if parts else "基本固定"
        # 峰值速度与发生时间
        spd = np.sqrt(seg[:, 1]**2 + seg[:, 2]**2)
        pk = seg[spd.argmax(), 0]
        # 停顿：能量低于本镜峰值 15% 且低于绝对阈值，连续 ≥0.25 s
        thr = max(en.max() * 0.15, 6.0)
        holds = []; start = None
        for t, e in zip(seg[:, 0], en):
            if e < thr and start is None: start = t
            if e >= thr and start is not None:
                if t - start >= 0.25: holds.append((start, t))
                start = None
        if start is not None and seg[-1, 0] - start >= 0.25: holds.append((start, seg[-1, 0]))
        hold_s = "；".join(f"{s:.2f}–{e:.2f}" for s, e in holds) or "无"
        out.append(dict(idx=idx, start=a, end=b, cam=cam, dx=dx, dy=dy, zoom=zm, peak_t=pk, peak_spd=spd.max(),
                        energy=en.mean(), subject=res.mean(), holds=hold_s))
    return out, fps

def add_arguments(parser):
    parser.add_argument("video")
    parser.add_argument("--shots", required=True)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--md")
    parser.add_argument("--csv")
    return parser


def run(a):
    shots = [(int(l.split()[0]), float(l.split()[1]), float(l.split()[2])) for l in open(a.shots) if l.strip()]
    out, fps = analyze(a.video, shots, a.width)
    lines = ["| # | 时间 | 全局运动（光流中值）| 峰值速度@t | 画面能量 | 主体运动（去全局） | 停顿段（能量<15%峰值，≥0.25 s） |", "|---|---|---|---|---|---|---|"]
    for r in out:
        lines.append(f"| {r['idx']:02d} | {r['start']:.2f}–{r['end']:.2f} | {r['cam']} | {r['peak_spd']:.0f}%W/s @{r['peak_t']:.2f} | {r['energy']:.0f} | {r['subject']:.0f} | {r['holds']} |")
    md = "\n".join(lines); print(md)
    if a.md: open(a.md, "w").write(md + "\n")
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)


def main():
    run(add_arguments(argparse.ArgumentParser(description=__doc__)).parse_args())


if __name__ == "__main__":
    main()
