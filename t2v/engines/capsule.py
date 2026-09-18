"""不可覆盖的 run capsule：一次生成的输入、图、产物与记账写在一个目录里，并登记到运行索引。"""
import json
import os
from pathlib import Path


class RunCapsule:
    def __init__(self, directory, index_path=None, subdirs=()):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        for name in subdirs:
            (self.dir / name).mkdir(exist_ok=True)
        self.index_path = Path(index_path) if index_path else None

    def path(self, *parts):
        return self.dir.joinpath(*parts)

    def write_json(self, name, data, indent=2):
        target = self.path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=indent) + ("\n" if indent else ""),
                          encoding="utf-8")
        return target

    def write_text(self, name, text):
        target = self.path(name)
        target.write_text(text, encoding="utf-8")
        return target

    def write_bytes(self, name, data):
        target = self.path(name)
        target.write_bytes(data)
        return target

    def append_index(self, item):
        """追加一行运行索引；path 字段写成相对索引文件所在目录的位置。"""
        if not self.index_path:
            return None
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        row = dict(item)
        row["path"] = os.path.relpath(str(self.dir), str(self.index_path.parent))
        with self.index_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        return self.index_path
