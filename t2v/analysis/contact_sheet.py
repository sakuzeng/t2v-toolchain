"""多条产物 vs 参考片的并排接触表（零费用，本机 CPU）。
每行一个视频，按归一化时间等距抽 N 帧（各视频帧数可不同），第一行放参考片；用于抽卡挑片。
用法：
  python3 -m t2v contact-sheet --ref references/clips/c001a/reference.mp4 \
      --take "seed 20260908=runs/c001a/<run>/picture.mp4" --take "seed 20260909=..." \
      --cols 12 --tile-width 288 --out sheet.png [--absolute]
--absolute：按相同帧号抽（要求各视频帧数一致，例如 69 帧 retimed 版 vs 69 帧参考片），否则按归一化时间抽。
依赖 OpenCV/NumPy（pip install 't2v[analysis]' 或 text2video 虚拟环境）。"""
import argparse
import os

from .deps import require_cv2


def read_frames(path):
    cv2, _ = require_cv2()
    capture = cv2.VideoCapture(path)
    frames = []
    fps = capture.get(cv2.CAP_PROP_FPS)
    fps = fps if fps and fps > 0 else 24.0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(frame)
    capture.release()
    if not frames:
        raise SystemExit(f"读不到帧：{path}")
    return frames, fps


def row(label, frames, fps, cols, tile_width, absolute_idx=None):
    cv2, np = require_cv2()
    total = len(frames)
    indexes = absolute_idx if absolute_idx is not None else [round(k * (total - 1) / (cols - 1)) for k in range(cols)]
    tiles = []
    for index in indexes:
        index = min(max(int(index), 0), total - 1)
        frame = frames[index]
        height, width = frame.shape[:2]
        tile = cv2.resize(frame, (tile_width, int(tile_width * height / width)), interpolation=cv2.INTER_AREA)
        cv2.rectangle(tile, (0, 0), (tile_width, 22), (0, 0, 0), -1)
        cv2.putText(tile, f"f{index} {index / fps:.2f}s", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(tile)
    strip = np.hstack(tiles)
    head = np.zeros((28, strip.shape[1], 3), np.uint8)
    cv2.putText(head, f"{label}  ({total} frames @ {fps:g} fps)", (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                (0, 255, 255), 2, cv2.LINE_AA)
    return np.vstack([head, strip])


def build_sheet(items, cols, tile_width, absolute=False):
    cv2, np = require_cv2()
    rows, absolute_idx = [], None
    for label, path in items:
        frames, fps = read_frames(path)
        if absolute and absolute_idx is None:
            absolute_idx = [round(k * (len(frames) - 1) / (cols - 1)) for k in range(cols)]
        rows.append(row(label, frames, fps, cols, tile_width, absolute_idx if absolute else None))
    width = max(item.shape[1] for item in rows)
    rows = [item if item.shape[1] == width
            else np.hstack([item, np.zeros((item.shape[0], width - item.shape[1], 3), np.uint8)]) for item in rows]
    return np.vstack(rows)


def add_arguments(parser):
    parser.add_argument("--ref")
    parser.add_argument("--take", action="append", default=[], help='"标签=路径"')
    parser.add_argument("--cols", type=int, default=12)
    parser.add_argument("--tile-width", type=int, default=288)
    parser.add_argument("--out", required=True)
    parser.add_argument("--absolute", action="store_true")
    return parser


def run(args):
    cv2, _ = require_cv2()
    items = [("REFERENCE", args.ref)] if args.ref else []
    for spec in args.take:
        label, _, path = spec.partition("=")
        if not path:
            label, path = os.path.basename(os.path.dirname(spec)), spec
        items.append((label, path))
    if not items:
        raise SystemExit("没有输入")
    sheet = build_sheet(items, args.cols, args.tile_width, args.absolute)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    cv2.imwrite(args.out, sheet, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    print(f"{len(items)} rows x {args.cols} cols -> {args.out} ({sheet.shape[1]}x{sheet.shape[0]})")


def main():
    run(add_arguments(argparse.ArgumentParser(description=__doc__)).parse_args())


if __name__ == "__main__":
    main()
