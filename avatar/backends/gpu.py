"""Backend GPU : workflows ComfyUI pilotés par son API HTTP.

Les workflows sont exportés depuis ComfyUI (« Export (API) ») dans comfy_workflows/, avec des
marqueurs {{ref_image}}, {{audio}}, {{driver}}, {{video}}, {{prompt}}, {{seed}} à la place des
entrées. Voir comfy_workflows/README.md.
"""

import json
import re
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from avatar import ffmpeg
from avatar.config import Config
from avatar.segment import Segment

MARKER = re.compile(r"\{\{(\w+)\}\}")


def fill(node, values: dict):
    """Remplace les marqueurs {{nom}} ; un marqueur seul garde le type de la valeur (seed)."""
    if isinstance(node, dict):
        return {k: fill(v, values) for k, v in node.items()}
    if isinstance(node, list):
        return [fill(v, values) for v in node]
    if isinstance(node, str):
        whole = MARKER.fullmatch(node)
        if whole:
            return values[whole.group(1)]
        return MARKER.sub(lambda m: str(values[m.group(1)]), node)
    return node


class Comfy:
    def __init__(self, url: str, timeout: float):
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.client_id = uuid.uuid4().hex

    def _get(self, path: str) -> bytes:
        with urllib.request.urlopen(self.url + path) as r:
            return r.read()

    def _post(self, path: str, body: bytes, content_type: str) -> dict:
        req = urllib.request.Request(
            self.url + path, data=body, headers={"Content-Type": content_type}
        )
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())

    def upload(self, path: Path) -> str:
        """Envoie un fichier dans input/ de ComfyUI et renvoie le nom à mettre dans le workflow."""
        boundary = uuid.uuid4().hex
        head = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="image"; '
            f'filename="{path.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
        )
        tail = (
            f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\n'
            f"true\r\n--{boundary}--\r\n"
        )
        body = head.encode() + path.read_bytes() + tail.encode()
        res = self._post("/upload/image", body, f"multipart/form-data; boundary={boundary}")
        return f"{res['subfolder']}/{res['name']}" if res.get("subfolder") else res["name"]

    def run(self, workflow: dict, out: Path) -> None:
        """Exécute le workflow et télécharge la première vidéo produite dans `out`."""
        body = json.dumps({"prompt": workflow, "client_id": self.client_id}).encode()
        prompt_id = self._post("/prompt", body, "application/json")["prompt_id"]
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            history = json.loads(self._get(f"/history/{prompt_id}"))
            if prompt_id in history:
                break
            time.sleep(5)
        else:
            raise TimeoutError(f"ComfyUI : workflow {prompt_id} non terminé")

        entry = history[prompt_id]
        if entry.get("status", {}).get("status_str") == "error":
            raise RuntimeError(f"ComfyUI : échec du workflow {prompt_id}")
        for node in entry["outputs"].values():
            for files in node.values():
                for f in files if isinstance(files, list) else []:
                    if isinstance(f, dict) and f.get("filename", "").endswith(".mp4"):
                        query = urllib.parse.urlencode(
                            {k: f.get(k, "") for k in ("filename", "subfolder", "type")}
                        )
                        out.write_bytes(self._get(f"/view?{query}"))
                        return
        raise RuntimeError(f"ComfyUI : aucune vidéo .mp4 en sortie de {prompt_id}")


def workflow(cfg: Config, name: str, values: dict) -> dict:
    path = cfg.root / cfg["gpu"]["workflows"][name]
    return fill(json.loads(path.read_text()), values)


def render(cfg: Config, video_id: str, seg: Segment, seed: int | None = None) -> None:
    g = cfg["gpu"]
    comfy = Comfy(g["comfy_url"], g["timeout"])
    work = cfg.work_dir(video_id)
    out = work / f"seg_{seg.id}.mp4"
    values = {
        "ref_image": comfy.upload(cfg.path("ref_png")),
        "audio": comfy.upload(work / f"seg_{seg.id}.wav"),
        "prompt": seg.prompt or "",
        "seed": g["seed"] if seed is None else seed,
    }
    if seg.driver:
        # Geste précis : Wan2.2-Animate transfère le mouvement, puis MuseTalk cale la bouche.
        animated = work / f"seg_{seg.id}_animate.mp4"
        values["driver"] = comfy.upload(cfg.path("drivers") / seg.driver)
        comfy.run(workflow(cfg, "animate", values), animated)
        values["video"] = comfy.upload(animated)
        comfy.run(workflow(cfg, "musetalk", values), out)
    else:
        # Geste libre : InfiniteTalk génère une vidéo déjà synchronisée.
        comfy.run(workflow(cfg, "infinitetalk", values), out)
    quality_frames(out, work / "qc")


def quality_frames(video: Path, qc_dir: Path) -> None:
    """3 images (25 %, 50 %, 75 %) pour vérifier les mains et l'identité."""
    qc_dir.mkdir(exist_ok=True)
    d = ffmpeg.duration(video)
    for k, t in enumerate((0.25, 0.5, 0.75), start=1):
        ffmpeg.run("-ss", f"{d * t:.3f}", "-i", video, "-frames:v", "1",
                   qc_dir / f"{video.stem}_{k}.png")  # fmt: skip
