from pathlib import Path

from avatar import ffmpeg
from avatar.config import Config
from avatar.segment import load


def assemble(cfg: Config, video_id: str) -> Path:
    """Concatène seg_N.mp4 avec un fondu vidéo, sur l'audio seg_N.wav mis bout à bout.

    Chaque vidéo est calée sur la durée exacte de son audio, puis prolongée de la durée du
    fondu en figeant sa dernière image : le fondu mange ce prolongement, si bien que les
    lèvres restent synchronisées et que la durée finale égale la somme des audios.
    """
    work = cfg.work_dir(video_id)
    ids = [s.id for s in load(work / "segments.json")]
    v = cfg["video"]
    w, h, fps = v["width"], v["height"], v["fps"]
    fade = v["fade_frames"] / fps
    lengths = [ffmpeg.duration(work / f"seg_{i}.wav") for i in ids]
    n = len(ids)

    inputs, graph = [], []
    for k, i in enumerate(ids):
        inputs += ["-i", work / f"seg_{i}.mp4"]
        keep = lengths[k] + (fade if k < n - 1 else 0)
        graph.append(
            f"[{k}:v]fps={fps},scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,"
            f"tpad=stop_mode=clone:stop_duration={keep + 1},"
            f"trim=duration={keep:.4f},setpts=PTS-STARTPTS[v{k}]"
        )
    for i in ids:
        inputs += ["-i", work / f"seg_{i}.wav"]

    last, offset = "v0", 0.0
    for k in range(1, n):
        offset += lengths[k - 1]
        graph.append(
            f"[{last}][v{k}]xfade=transition=fade:duration={fade:.4f}:offset={offset:.4f}[x{k}]"
        )
        last = f"x{k}"
    if v.get("ai_label"):
        text = v["ai_label"].replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        graph.append(
            f"[{last}]drawtext=text='{text}':fontsize={h // 36}:fontcolor=white:"
            f"box=1:boxcolor=black@0.5:boxborderw={h // 108}:x=w-tw-{h // 36}:y={h // 36}[vl]"
        )
        last = "vl"
    graph.append("".join(f"[{n + k}:a]" for k in range(n)) + f"concat=n={n}:v=0:a=1[a]")

    out = work / "final.mp4"
    ffmpeg.run(
        *inputs,
        "-filter_complex", ";".join(graph),
        "-map", f"[{last}]", "-map", "[a]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart",
        out,
    )  # fmt: skip
    return out
