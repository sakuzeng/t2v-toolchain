"""ComfyUI HTTP 客户端：提交、轮询、下载与文件上传。两个引擎共用这一份。"""
import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request

from .. import paths
from ..errors import ComfyError

CONTENT_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp",
                 "mp4": "video/mp4", "mov": "video/quicktime"}
DEFAULT_BASE = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")


def remote_name(upload):
    """/upload/image 返回的 {name, subfolder} 拼成节点里该填的文件名（同名会被改名，必须用返回值）。"""
    return upload["name"] if not upload.get("subfolder") else upload["subfolder"] + "/" + upload["name"]


class ComfyClient:
    def __init__(self, base=None, poll=5.0, client_id="auto"):
        self.base = base or DEFAULT_BASE
        self.poll = poll
        self.client_id = client_id      # 提交时冒用的浏览器会话；见 browser_client_id

    def api(self, path, data=None, raw=False):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers={"Content-Type": "application/json"} if data is not None else {})
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read() if raw else json.load(response)

    def system_stats(self):
        return self.api("/system_stats")

    def device(self):
        return self.system_stats()["devices"][0]

    def missing_nodes(self, class_types):
        missing = []
        for class_type in class_types:
            try:
                if not self.api(f"/object_info/{class_type}"):
                    missing.append(class_type)
            except urllib.error.HTTPError:
                missing.append(class_type)
        return missing

    def upload(self, path):
        """POST /upload/image（multipart，标准库手拼），返回 {name, subfolder, type}。"""
        boundary = "----comfyrun" + str(random.randint(10 ** 8, 10 ** 9))
        data = open(path, "rb").read()
        extension = os.path.splitext(str(path))[1].lower().lstrip(".")
        content_type = CONTENT_TYPES.get(extension, "application/octet-stream")
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; "
                f"filename=\"{os.path.basename(str(path))}\"\r\nContent-Type: {content_type}\r\n\r\n").encode() + data + \
               (f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\n"
                f"true\r\n--{boundary}--\r\n").encode()
        request = urllib.request.Request(self.base + "/upload/image", data=body,
                                         headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read())

    def submit(self, graph, client_id=None, extra_data=None):
        body = {"prompt": graph}
        if client_id:
            body["client_id"] = client_id
        if extra_data:
            body["extra_data"] = extra_data
        result = self.api("/prompt", body)
        if result.get("node_errors"):
            raise ComfyError("节点错误：" + json.dumps(result["node_errors"], ensure_ascii=False)[:800])
        return result["prompt_id"]

    def wait(self, prompt_id, started_at=None):
        """轮询到任务完成，返回该任务的 history 条目；执行失败抛 ComfyError（.history 带完整记录）。"""
        started_at = started_at if started_at is not None else time.time()
        while True:
            time.sleep(self.poll)
            history = self.api(f"/history/{prompt_id}")
            if prompt_id in history:
                status = history[prompt_id].get("status", {})
                if status.get("status_str") == "error":
                    error = ComfyError("执行失败：" + json.dumps(status.get("messages", [])[-1:], ensure_ascii=False)[:1200])
                    error.history = history[prompt_id]
                    raise error
                if status.get("completed"):
                    return history[prompt_id]
            queue = self.api("/queue")
            print(f"[wait] {int(time.time() - started_at)}s running={len(queue.get('queue_running', []))} "
                  f"pending={len(queue.get('queue_pending', []))}", end="\r", flush=True)

    @staticmethod
    def outputs(entry):
        """history 条目里的产物描述列表，保持节点顺序。"""
        found = []
        for values in entry.get("outputs", {}).values():
            for items in values.values():
                if isinstance(items, list):
                    found += [item for item in items if isinstance(item, dict) and item.get("filename")]
        return found

    @staticmethod
    def outputs_by_node(entry):
        for node_id, values in entry.get("outputs", {}).items():
            for items in values.values():
                if isinstance(items, list):
                    yield node_id, [item for item in items if isinstance(item, dict) and item.get("filename")]

    def download(self, item):
        query = urllib.parse.urlencode({"filename": item["filename"], "subfolder": item.get("subfolder", ""),
                                        "type": item.get("type", "output")})
        return self.api("/view?" + query, raw=True)

    @staticmethod
    def exec_seconds(entry):
        stamps = {m[0]: m[1].get("timestamp") for m in entry.get("status", {}).get("messages", [])
                  if isinstance(m, list) and len(m) == 2 and isinstance(m[1], dict)}
        if not stamps.get("execution_start"):
            return None
        return (stamps.get("execution_success", 0) - stamps["execution_start"]) / 1000

    def browser_client_id(self, want=None):
        """ComfyUI 只把 executing/progress/executed 事件发给提交该任务的 client_id（无 client_id 时干脆不发）。
        要让用户开着的画布实时看到进度和产物，脚本得用浏览器自己的会话 id 提交。
        取法：① 历史里最近一次浏览器提交的任务（带 extra_pnginfo）的 client_id；② 历史被重启清空时用本地缓存 .comfy_client_id。
        浏览器的 id 存在标签页 sessionStorage，刷新/服务器重启都不变，关标签页才换；换了就 --client-id <浏览器控制台 sessionStorage.clientId>。
        id 对不上也不影响任务和 /history 轮询，只是画布不动。"""
        want = self.client_id if want is None else want
        cache = paths.CLIENT_CACHE
        if want not in ("auto", "none", ""):
            cache.write_text(want.strip())
            return want
        if want != "auto":
            return "comfy_run"
        try:
            history = self.api("/history?max_items=50")
            items = sorted(history.values(), key=lambda v: v["prompt"][3].get("create_time", 0), reverse=True)
            for item in items:
                extra = item["prompt"][3]
                if "extra_pnginfo" in extra and extra.get("client_id") and extra["client_id"] != "comfy_run":
                    cache.write_text(extra["client_id"])
                    print("[client] 冒用浏览器会话", extra["client_id"], "（来自历史；画布开着同一工作流即可实时看到进度）")
                    return extra["client_id"]
        except Exception as exc:
            print("[client] 读历史失败：", exc)
        if cache.exists():
            cached = cache.read_text().strip()
            if cached:
                print("[client] 历史里没有浏览器任务（重启过？），用缓存会话", cached, "；若浏览器标签页换过则画布不会实时显示")
                return cached
        print("[client] 无浏览器会话可用，画布不会实时显示；跑完在队列面板「… → 加载工作流」看")
        return "comfy_run"
