"""分析工具的可选依赖：只有真正跑分析时才要求 OpenCV/NumPy，import 包本身不需要。"""


def require_cv2():
    try:
        import cv2
        import numpy
    except ImportError as exc:
        raise SystemExit("分析工具需要 OpenCV 与 NumPy：pip install 'opencv-python' numpy"
                         f"（或在 text2video 虚拟环境里运行）；原始错误：{exc}")
    return cv2, numpy
