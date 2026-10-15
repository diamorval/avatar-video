"""Moteur commun à l'app (REST) et à Claude (MCP) : crée et exécute les vidéos en tâche de fond.

L'état de chaque vidéo vit dans work/<id>/status.json : l'app et le serveur MCP, même lancés
dans deux processus, voient les mêmes vidéos.
"""

import json
import os
import queue
import re
import threading
import time
import unicodedata

from avatar import segment as seg
from avatar.assemble import assemble
from avatar.backends import gpu, mac
from avatar.config import Config
from avatar.voice import voice

STEPS = ["segment", "voice", "video", "assemble"]
ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "video"


def render_video(cfg: Config, video_id: str, backend: str, only=None, seed=None) -> None:
    for s in seg.load(cfg.work_dir(video_id) / "segments.json"):
        if only is not None and s.id != only:
            continue
        if backend == "mac":
            mac.render(cfg, video_id, s)
        else:
            gpu.render(cfg, video_id, s, seed)


def source_info(cfg: Config) -> dict:
    """Ce qu'il faut savoir avant de créer une vidéo, dont les gestes pour écrire des segments."""
    clips = list(seg.load_clips(cfg.path("clips"))) if cfg.path("clips").exists() else []
    return {
        "default_backend": cfg["backend"],
        "source_ready": cfg.path("ref_wav").exists() and cfg.path("ref_png").exists(),
        "clips": clips,
        "drivers": sorted(p.name for p in cfg.path("drivers").glob("*.mp4")),
    }


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class Jobs:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.queue: queue.Queue[str] = queue.Queue()
        self.lock = threading.Lock()
        for status in self.list():
            if status["state"] in ("queued", "running") and not _alive(status["pid"]):
                self._update(status["id"], state="error", error="interrompu (processus arrêté)")
        threading.Thread(target=self._worker, daemon=True).start()

    def _status_path(self, video_id: str):
        return self.cfg.path("work") / video_id / "status.json"

    def _update(self, video_id: str, **fields) -> dict:
        path = self._status_path(video_id)
        status = json.loads(path.read_text()) if path.exists() else {}
        status.update(fields, updated=time.time())
        path.write_text(json.dumps(status, ensure_ascii=False, indent=2))
        return status

    def create(self, name: str, script: str, backend: str | None = None, segments=None) -> dict:
        """Enregistre le script et met la vidéo en file. `segments` évite l'appel au LLM."""
        backend = backend or self.cfg["backend"]
        if backend not in ("mac", "gpu"):
            raise ValueError(f"backend inconnu : {backend}")
        if not script.strip():
            raise ValueError("script vide")
        with self.lock:
            base, n = slug(name), 1
            video_id = base
            while (self.cfg.path("work") / video_id).exists():
                n += 1
                video_id = f"{base}-{n}"
            self.cfg.work_dir(video_id)
        scripts = self.cfg.root / "scripts"
        scripts.mkdir(exist_ok=True)
        (scripts / f"{video_id}.txt").write_text(script)
        try:
            if segments is not None:
                seg.save(self.cfg, video_id, seg.Segments.validate_python(segments), backend)
        except Exception:
            (scripts / f"{video_id}.txt").unlink()
            (self.cfg.path("work") / video_id).rmdir()
            raise
        status = self._update(
            video_id, id=video_id, name=name, backend=backend, state="queued", step=None,
            error=None, created=time.time(), pid=os.getpid(),
        )  # fmt: skip
        self.queue.put(video_id)
        return status

    def list(self) -> list[dict]:
        work = self.cfg.path("work")
        paths = work.glob("*/status.json") if work.exists() else []
        statuses = [json.loads(p.read_text()) for p in paths]
        return sorted(statuses, key=lambda s: s["created"], reverse=True)

    def get(self, video_id: str) -> dict | None:
        if not ID.match(video_id) or not self._status_path(video_id).exists():
            return None
        work = self.cfg.path("work") / video_id
        status = json.loads(self._status_path(video_id).read_text())
        segments = work / "segments.json"
        status["segments"] = json.loads(segments.read_text()) if segments.exists() else []
        # final.mp4 existe déjà pendant que ffmpeg l'écrit : il n'est livré qu'une fois terminé.
        done = status["state"] == "done" and (work / "final.mp4").exists()
        status["final"] = str(work / "final.mp4") if done else None
        return status

    def _worker(self) -> None:
        # Une vidéo à la fois : le Mac comme le GPU n'ont la mémoire que pour un modèle.
        while True:
            self.run(self.queue.get())

    def run(self, video_id: str) -> None:
        status = json.loads(self._status_path(video_id).read_text())
        backend = status["backend"]
        work = self.cfg.path("work") / video_id
        script = self.cfg.root / "scripts" / f"{video_id}.txt"
        try:
            for step in STEPS:
                if step == "segment" and (work / "segments.json").exists():
                    continue  # segments fournis à la création
                self._update(video_id, state="running", step=step)
                if step == "segment":
                    seg.segment(self.cfg, script, backend)
                elif step == "voice":
                    voice(self.cfg, video_id)
                elif step == "video":
                    render_video(self.cfg, video_id, backend)
                else:
                    assemble(self.cfg, video_id)
            self._update(video_id, state="done", step=None)
        except Exception as e:  # l'erreur est rendue à l'app et à Claude via status.json
            self._update(video_id, state="error", error=f"{type(e).__name__}: {e}")
