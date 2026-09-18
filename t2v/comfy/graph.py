"""API 工作流图的查找、构造，以及画布（.ui.json）同步。"""
import json
import os
import re

from ..errors import GraphError


def find(graph, class_type, nth=0, pred=None):
    """按 class_type 取第 nth 个节点，返回 (id, node)；找不到抛 GraphError。"""
    hits = [(key, value) for key, value in graph.items()
            if value["class_type"] == class_type and (pred is None or pred(value))]
    if len(hits) <= nth:
        raise GraphError(f"图里找不到第 {nth + 1} 个 {class_type} 节点")
    return hits[nth]


def node(class_type, title=None, **inputs):
    built = {"class_type": class_type, "inputs": inputs}
    if title:
        built["_meta"] = {"title": title}
    return built


def same(x, y):
    if x == y:
        return True
    try:
        return float(x) == float(y) and not isinstance(x, bool) and not isinstance(y, bool)
    except (TypeError, ValueError):
        return False


def synced_ui_workflow(api_path, graph0, graph, workflow_label=None):
    """把 API 图里改过的字面量同步进同名 .ui.json 画布版，返回可塞进 extra_pnginfo.workflow 的画布 JSON。
    这样脚本提交的运行在浏览器「队列」面板里也能点「加载工作流」（否则报 No workflow data available）。
    对应规则：API 节点 id "140:131" = 画布上子图实例节点 140 里的内部节点 131；纯数字 id = 顶层节点。
    widgets_values 无名字，按「旧值相等」替换（子图实例节点上提升出来的同名控件一起替换）。"""
    ui_path = re.sub(r"\.api\.json$", ".ui.json", str(api_path))
    if ui_path == str(api_path) or not os.path.exists(ui_path):
        return None
    ui = json.load(open(ui_path))
    top = {n["id"]: n for n in ui["nodes"]}
    subgraphs = {sg["id"]: sg for sg in ui.get("definitions", {}).get("subgraphs", [])}

    def swap(target, old, new):
        values = target.get("widgets_values")
        if not isinstance(values, list):
            return 0
        hits = [i for i, w in enumerate(values) if not isinstance(w, (list, dict)) and same(w, old)]
        for i in hits:
            values[i] = new
        return len(hits)

    for nid, n in graph.items():
        for key, new in n["inputs"].items():
            old = graph0.get(nid, {}).get("inputs", {}).get(key)
            if isinstance(new, list) or same(old, new):
                continue
            if ":" in nid:
                inst_id, inner_id = nid.split(":", 1)
                inst = top.get(int(inst_id))
                sg = subgraphs.get(inst["type"]) if inst else None
                inner = next((x for x in sg["nodes"] if str(x["id"]) == inner_id), None) if sg else None
                count = (swap(inner, old, new) if inner else 0) + (swap(inst, old, new) if inst else 0)
            else:
                count = swap(top.get(int(nid), {}), old, new)
            if count == 0 and old is None and n["class_type"] == "LoadImage" and ":" not in nid:
                values = top.get(int(nid), {}).get("widgets_values")
                if isinstance(values, list):
                    for i, w in enumerate(values):
                        if isinstance(w, str) and re.search(r"\.(png|jpe?g|webp)$", w, re.I):
                            values[i] = new
                            count += 1
                            break
            if count == 0:
                print(f"[ui] 警告：{nid}.{key} 在画布版里找不到旧值 {str(old)[:40]!r}，画布显示会是模板值")
    if workflow_label:
        ui.setdefault("extra", {})["t2v_workflow_label"] = workflow_label
        for item in ui.get("nodes", []):
            if item.get("type") != "PrimitiveStringMultiline":
                continue
            values = item.get("widgets_values", [])
            if any(isinstance(value, str) and value == graph.get(str(item.get("id")), {}).get("inputs", {}).get("value")
                   for value in values):
                item["title"] = f"Input Text (Prompt) · {workflow_label}"
                break
    return ui
