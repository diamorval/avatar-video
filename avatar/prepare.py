from pathlib import Path

import yaml

from avatar import ffmpeg
from avatar.config import Config


def parse_time(t: str) -> float:
    """'00:02', '01:00:02.5' -> secondes."""
    seconds = 0.0
    for part in t.strip().split(":"):
        seconds = seconds * 60 + float(part)
    return seconds


def load_clips(path: Path) -> dict[str, tuple[float, float]]:
    """clips.yaml (`nom: "début-fin"`) -> {nom: (début, fin)}."""
    clips = {}
    for name, span in (yaml.safe_load(path.read_text()) or {}).items():
        start, end = (parse_time(t) for t in str(span).split("-"))
        if end <= start:
            raise ValueError(f"clips.yaml : {name} se termine avant de commencer ({span})")
        clips[name] = (start, end)
    return clips


def prepare(cfg: Config) -> None:
    src = cfg.path("source")
    p = cfg["prepare"]
    ffmpeg.run(
        "-ss", p["ref_wav_start"], "-t", p["ref_wav_duration"], "-i", src,
        "-vn", "-ac", "1", "-ar", "24000", cfg.path("ref_wav"),
    )  # fmt: skip
    ffmpeg.run("-ss", p["ref_png_time"], "-i", src, "-frames:v", "1", cfg.path("ref_png"))

    clips_file = cfg.path("clips")
    if not clips_file.exists():
        return
    out_dir = cfg.path("clips_dir")
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (start, end) in load_clips(clips_file).items():
        # Réencodé pour couper à l'image près (un -c copy coupe aux images clés).
        ffmpeg.run(
            "-ss", start, "-t", end - start, "-i", src,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", out_dir / f"{name}.mp4",
        )  # fmt: skip
