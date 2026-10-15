import shlex
import subprocess

from avatar import ffmpeg
from avatar.config import Config
from avatar.segment import Segment


def render(cfg: Config, video_id: str, seg: Segment) -> None:
    """Boucle le clip choisi sur la durée de l'audio, puis MuseTalk recale la bouche."""
    work = cfg.work_dir(video_id)
    audio = work / f"seg_{seg.id}.wav"
    looped = work / f"seg_{seg.id}_clip.mp4"
    ffmpeg.run(
        "-stream_loop", "-1", "-i", cfg.path("clips_dir") / f"{seg.clip}.mp4",
        "-t", f"{ffmpeg.duration(audio):.3f}", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        looped,
    )  # fmt: skip
    cmd = cfg["mac"]["musetalk_cmd"].format(
        video=shlex.quote(str(looped)),
        audio=shlex.quote(str(audio)),
        out=shlex.quote(str(work / f"seg_{seg.id}.mp4")),
    )
    subprocess.run(shlex.split(cmd), check=True)
