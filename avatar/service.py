"""Moteur commun à l'app (REST) et à Claude (MCP) : crée et exécute les vidéos en tâche de fond.

L'app et le serveur MCP ne font que créer et lire des vidéos. Un processus `avatar worker` les
exécute : en conteneur sur une machine GPU, en natif sur Mac (MLX n'a pas accès au GPU en Docker).
Tout passe par le disque partagé : work/<id>/status.json porte l'état, et work/<id>/claim, créé
de façon exclusive puis touché régulièrement, dit quel worker exécute la vidéo et s'il vit encore.
"""

import json
import os
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


HEARTBEAT = 10  # s entre deux signes de vie du worker
STALE = 60  # s sans signe de vie : le worker est considéré comme arrêté


class Jobs:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.lock = threading.Lock()

    def _claim_path(self, video_id: str):
        return self.cfg.path("work") / video_id / "claim"

    def _status_path(self, video_id: str):
        return self.cfg.path("work") / video_id / "status.json"

    def _update(self, video_id: str, **fields) -> dict:
        path = self._status_path(video_id)
        status = json.loads(path.read_text()) if path.exists() else {}
        status.update(fields, updated=time.time())
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2))
        tmp.replace(path)  # atomique : un lecteur ne voit jamais un fichier à moitié écrit
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
            error=None, created=time.time(),
        )  # fmt: skip
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

    def claim_next(self) -> str | None:
        """Réserve la plus ancienne vidéo en file, ou None. Sûr entre plusieurs workers."""
        for status in reversed(self.list()):
            if status["state"] != "queued":
                continue
            try:
                os.close(os.open(self._claim_path(status["id"]), os.O_CREAT | os.O_EXCL))
            except FileExistsError:
                continue
            return status["id"]
        return None

    def reap(self) -> None:
        """Passe en erreur les vidéos dont le worker ne donne plus signe de vie."""
        for status in self.list():
            claim = self._claim_path(status["id"])
            if status["state"] in ("queued", "running") and claim.exists():
                if time.time() - claim.stat().st_mtime > STALE:
                    self._update(status["id"], state="error", error="interrompu (worker arrêté)")

    def work_forever(self, stop: threading.Event | None = None, poll: float = 2) -> None:
        # Une vidéo à la fois : le Mac comme le GPU n'ont la mémoire que pour un modèle.
        stop = stop or threading.Event()
        while not stop.is_set():
            self.reap()
            video_id = self.claim_next()
            if video_id:
                self.run(video_id)
            else:
                stop.wait(poll)

    def run(self, video_id: str) -> None:
        status = json.loads(self._status_path(video_id).read_text())
        backend = status["backend"]
        work = self.cfg.path("work") / video_id
        script = self.cfg.root / "scripts" / f"{video_id}.txt"
        done = threading.Event()

        def heartbeat():
            while not done.wait(HEARTBEAT):
                self._claim_path(video_id).touch()

        threading.Thread(target=heartbeat, daemon=True).start()
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
        finally:
            done.set()
