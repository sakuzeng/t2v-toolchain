"""从 T2V 的 API 版 + 官方 R2V 画布模板推出 R2V 的 API 版工作流（节点 id 与画布模板一致，便于画布同步）。
用法：python3 -m t2v graph h3  → 写 workflows/h3/r2v.api.json
接线依据 workflows/templates/minimax-h3/r2v.json 的 links（2026-09-06 核对）。"""
import copy
import json

from ...paths import ROOT


def build():
    t2v = json.loads((ROOT / "workflows/h3/t2v.api.json").read_text(encoding="utf-8"))
    inner = {k.split(":")[1]: v for k, v in t2v.items() if ":" in k}   # 子图内部节点，去掉 "140:" 前缀
    def node(cls, **inputs): return {"class_type": cls, "inputs": inputs}
    g = {}
    g["119"] = node("VAELoader", vae_name="minimax_h3_video_vae_fp16.safetensors")
    g["120"] = node("VAELoader", vae_name="minimax_h3_audio_vae_fp32.safetensors")
    g["127"] = node("UNETLoader", unet_name="minimax_h3_ref2va_pruned_int8_convrot.safetensors", weight_dtype="default")
    g["128"] = copy.deepcopy(inner["128"])                                   # CLIPLoader qwen3vl nvfp4 / minimax
    g["123"] = node("KSamplerSelect", sampler_name="res_multistep")
    g["146"] = node("PrimitiveBoolean", value=False)                         # turbo 开关
    g["143"] = node("PrimitiveInt", value=20)                                # 正常步数
    g["144"] = node("PrimitiveInt", value=4)                                 # turbo 步数（R2V turbo 是 4 步）
    g["145"] = node("LoraLoaderModelOnly", lora_name="minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors", strength_model=1.0, model=["127", 0])
    g["141"] = node("ComfySwitchNode", switch=["146", 0], on_false=["127", 0], on_true=["145", 0])
    g["142"] = node("ComfySwitchNode", switch=["146", 0], on_false=["143", 0], on_true=["144", 0])
    g["124"] = node("BasicScheduler", scheduler="simple", steps=["142", 0], denoise=1.0, model=["141", 0])
    g["129"] = node("RandomNoise", noise_seed=261662374822964)
    g["115"] = node("ResolutionSelector", aspect_ratio="16:9 (Widescreen)", megapixels=0.4, multiple=32)
    g["132"] = node("PrimitiveFloat", value=5.0)
    g["131"] = copy.deepcopy(inner["132"]); g["131"]["inputs"]["values.a"] = ["132", 0]   # 17k+5 帧数表达式
    g["137"] = node("LoadImage", image="red_superboy_on_city_roof.png")      # <Picture 1>
    ui = json.loads((ROOT / "workflows/templates/minimax-h3/r2v.json").read_text(encoding="utf-8"))
    tpl_prompt = next(n for n in ui["nodes"] if n["id"] == 138)["widgets_values"][0]   # 与画布模板同值，comfy_run 才能按旧值同步
    g["138"] = node("PrimitiveStringMultiline", value=tpl_prompt)              # prompt
    g["136"] = node("MiniMaxH3ReferenceToVideo", clip=["128", 0], vae=["119", 0], audio_vae=["120", 0],
                    prompt=["138", 0], width=["115", 0], height=["115", 1], length=["131", 1], ref_image_size="match")
    g["136"]["inputs"]["ref_images.ref_image_0"] = ["137", 0]
    g["126"] = node("BasicGuider", model=["141", 0], conditioning=["136", 0])
    g["125"] = node("SamplerCustomAdvanced", noise=["129", 0], guider=["126", 0], sampler=["123", 0], sigmas=["124", 0], latent_image=["136", 1])
    g["122"] = node("VAEDecode", samples=["125", 0], vae=["119", 0])
    g["121"] = node("VAEDecodeAudio", samples=["125", 0], vae=["120", 0])
    g["130"] = copy.deepcopy(inner["130"]); g["130"]["inputs"].update(images=["122", 0], audio=["121", 0])
    g["92"] = copy.deepcopy(t2v["92"]); g["92"]["inputs"]["video"] = ["130", 0]
    for k, v in g.items(): v.setdefault("_meta", {"title": v["class_type"]})
    return g


def write(destination=None):
    graph = build()
    destination = destination or ROOT / "workflows/h3/r2v.api.json"
    with open(destination, "w", encoding="utf-8") as stream:
        json.dump(graph, stream, indent=1, ensure_ascii=False)
    print(f"[graph] {destination} · {len(graph)} 节点")
    return destination
