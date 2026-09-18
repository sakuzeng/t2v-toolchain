"""把 ComfyUI 官方模板 video_wan21_scail2_character_replacement_int8 的 Base 子图展开成不含子图的 API 工作流（单段，≤81 帧）。
连线与参数逐条对照模板子图（2026-09-08 抓取）；省略了模板里只为 UI 服务的节点：ResizeImageMaskNode / ImageFromBatch /
ComfyMathExpression / ComfySwitchNode / Primitive*（宽高帧数直接写常量，turbo 预设写死，非 turbo 用 --steps 40 --cfg 5）。
建图命令：python3 -m t2v graph scail2 --driving <文件名> --ref <文件名> --out graph.api.json
"""

NEG_DEFAULT = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，"
               "丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，"
               "杂乱的背景，三条腿，背景人很多，倒着走")

def build(mode, driving, ref, prompt, negative, seed, length, width, height, sam3_word_video="human", sam3_word_ref="human", ref_extra=(),
          steps=6, cfg=1.0, distill_strength=0.8, dpo_strength=1.0, shift=5.0, pose_strength=1.0, pose_start=0.0, pose_end=1.0,
          replacement=True, detection_threshold=0.5, max_objects=4, fps=24.0, prefix="scail2/run"):
    def N(cls, inputs, title=None):
        node = {"class_type": cls, "inputs": inputs}
        if title: node["_meta"] = {"title": title}
        return node
    g = {}
    # 输入与 SAM3 掩膜（模板节点 155/30/193/191/212/196/198/197）
    g["1"] = N("LoadVideo", {"file": driving}, "驱动视频 pose_video")
    g["2"] = N("GetVideoComponents", {"video": ["1", 0]})
    g["3"] = N("LoadImage", {"image": ref}, "主参考图 reference_image")
    # 附加参考视图（SCAIL-2：批次里第 1 张为主参考，其余为同一身份的附加视图，如正脸近景、背面、裙靴细节；ImageBatch 会把后图缩放到首图尺寸）
    ref_batch = ["3", 0]
    for i, extra in enumerate(ref_extra):
        nid = str(40 + i); bid = str(50 + i)
        g[nid] = N("LoadImage", {"image": extra}, f"附加参考视图 {i+1}")
        g[bid] = N("ImageBatch", {"image1": ref_batch, "image2": [nid, 0]})
        ref_batch = [bid, 0]
    g["4"] = N("CheckpointLoaderSimple", {"ckpt_name": "sam3.1_multiplex_fp16.safetensors"}, "SAM3 模型")
    g["5"] = N("CLIPTextEncode", {"text": sam3_word_video, "clip": ["4", 1]}, "SAM3 词 · 驱动视频")
    g["6"] = N("CLIPTextEncode", {"text": sam3_word_ref, "clip": ["4", 1]}, "SAM3 词 · 参考图")
    g["7"] = N("SAM3_VideoTrack", {"images": ["2", 0], "model": ["4", 0], "detection_threshold": detection_threshold,
                                   "max_objects": max_objects, "detect_interval": 1, "conditioning": ["5", 0]}, "SAM3 追踪 · 驱动视频")
    g["8"] = N("SAM3_VideoTrack", {"images": ref_batch, "model": ["4", 0], "detection_threshold": detection_threshold,
                                   "max_objects": max_objects, "detect_interval": 1, "conditioning": ["6", 0]}, "SAM3 追踪 · 参考图")
    g["9"] = N("SCAIL2ColoredMask", {"driving_track_data": ["7", 0], "ref_track_data": ["8", 0], "object_indices": "",
                                     "sort_by": "left_to_right", "replacement_mode": bool(replacement)}, "SCAIL-2 彩色身份 mask")
    # mask 可视化输出（模板是 PreviewImage，这里落盘便于下载核对）
    g["27"] = N("CreateVideo", {"images": ["9", 0], "fps": fps}, "mask 视频")
    g["28"] = N("SaveVideo", {"video": ["27", 0], "filename_prefix": prefix + "_mask", "format": "auto", "codec": "auto"})
    g["29"] = N("SaveImage", {"images": ["9", 1], "filename_prefix": prefix + "_refmask"}, "参考图 mask")
    if mode == "maskcheck":
        return g
    # 模型链（模板 154 → 318 DPO → 11 lightx2v → 169 switch → 95 shift；BasicScheduler 取 11 的输出）
    g["10"] = N("UNETLoader", {"unet_name": "wan2.1_14B_SCAIL_2_int8_convrot.safetensors", "weight_dtype": "default"})
    g["11"] = N("LoraLoaderModelOnly", {"model": ["10", 0], "lora_name": "wan2.1_SCAIL_2_DPO_lora_bf16.safetensors", "strength_model": dpo_strength}, "DPO LoRA")
    if distill_strength > 0:
        g["12"] = N("LoraLoaderModelOnly", {"model": ["11", 0], "lora_name": "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
                                            "strength_model": distill_strength}, "lightx2v 蒸馏 LoRA")
        model_out = ["12", 0]
    else:
        model_out = ["11", 0]
    g["13"] = N("ModelSamplingSD3", {"model": model_out, "shift": shift})
    g["14"] = N("CLIPLoader", {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default"})
    g["15"] = N("CLIPTextEncode", {"text": prompt, "clip": ["14", 0]}, "正向 prompt")
    g["16"] = N("CLIPTextEncode", {"text": negative, "clip": ["14", 0]}, "负向 prompt")
    g["17"] = N("CLIPVisionLoader", {"clip_name": "clip_vision_h.safetensors"})
    g["18"] = N("CLIPVisionEncode", {"clip_vision": ["17", 0], "image": ["3", 0], "crop": "none"})
    g["19"] = N("VAELoader", {"vae_name": "Wan2_1_VAE_bf16.safetensors"})
    g["20"] = N("WanSCAILToVideo", {"positive": ["15", 0], "negative": ["16", 0], "vae": ["19", 0], "width": width, "height": height,
                                    "length": length, "batch_size": 1, "pose_strength": pose_strength, "pose_start": pose_start,
                                    "pose_end": pose_end, "video_frame_offset": 0, "previous_frame_count": 5,
                                    "pose_video": ["2", 0], "pose_video_mask": ["9", 0], "replacement_mode": bool(replacement),
                                    "reference_image": ref_batch, "reference_image_mask": ["9", 1], "clip_vision_output": ["18", 0]},
                "WanSCAILToVideo")
    g["21"] = N("KSamplerSelect", {"sampler_name": "euler"})
    g["22"] = N("BasicScheduler", {"model": model_out, "scheduler": "simple", "steps": steps, "denoise": 1.0})
    g["23"] = N("SamplerCustom", {"model": ["13", 0], "add_noise": True, "noise_seed": seed, "cfg": cfg, "positive": ["20", 0],
                                  "negative": ["20", 1], "sampler": ["21", 0], "sigmas": ["22", 0], "latent_image": ["20", 2]})
    g["24"] = N("VAEDecode", {"samples": ["23", 1], "vae": ["19", 0]})
    g["25"] = N("CreateVideo", {"images": ["24", 0], "fps": fps})
    g["26"] = N("SaveVideo", {"video": ["25", 0], "filename_prefix": prefix, "format": "auto", "codec": "auto"}, "成片")
    return g
