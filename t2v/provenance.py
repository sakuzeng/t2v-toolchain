"""运行记录的来源证据：输入哈希与仓库状态。写进 run.json / request.json。"""
import hashlib
import os
import subprocess


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_record(path):
    return {"path": os.path.abspath(path), "sha256": sha256_file(path), "bytes": os.path.getsize(path)}


def git_state():
    try:
        cwd = os.path.dirname(os.path.abspath(__file__))
        root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=cwd, text=True).strip()
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip())
        return {"root": root, "commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return None
