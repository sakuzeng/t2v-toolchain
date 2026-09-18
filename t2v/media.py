"""Local video probing and picture-master retiming."""
import json
import subprocess

def probe_video(path):
    output = subprocess.check_output([
        "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,nb_read_frames,r_frame_rate,duration",
        "-of", "json", path,
    ], text=True)
    stream = json.loads(output)["streams"][0]
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "frames": int(stream["nb_read_frames"]),
        "fps": stream["r_frame_rate"],
        "duration": float(stream["duration"]),
    }


def retime_video(source, destination, output_frames, fps):
    source_info = probe_video(source)
    source_frames = source_info["frames"]
    if source_frames <= 0 or output_frames <= 0 or fps <= 0:
        raise ValueError("retime requires positive source frames, output frames and fps")
    ratio = f"{output_frames}/{source_frames}"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", source,
        "-vf", f"setpts=PTS*{ratio},fps={fps:g}",
        "-frames:v", str(output_frames), "-an",
        "-c:v", "libx264", "-crf", "16", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", destination,
    ], check=True, timeout=600)
    output_info = probe_video(destination)
    if output_info["frames"] != output_frames:
        raise RuntimeError(f"retime produced {output_info['frames']} frames, expected {output_frames}")
    return {"source_frames": source_frames, "output_frames": output_frames, "fps": fps,
            "duration": output_frames / fps, "setpts_ratio": ratio}
