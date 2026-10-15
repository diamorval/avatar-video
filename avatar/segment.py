import json
import os
import re
import urllib.request
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, TypeAdapter, model_validator

from avatar.config import Config
from avatar.prepare import load_clips


class Segment(BaseModel):
    id: int
    text: str
    clip: str | None = None
    driver: str | None = None
    prompt: str | None = None

    @model_validator(mode="after")
    def has_gesture(self):
        if not (self.clip or self.driver or self.prompt):
            raise ValueError(f"segment {self.id} : ni clip, ni driver, ni prompt")
        return self


Segments = TypeAdapter(list[Segment])

PROMPT = """Tu découpes le script d'une vidéo tuto en segments, une phrase par segment.
Un avatar dit chaque segment avec un geste adapté à son sens.

{gesture_rules}

Réponds uniquement avec un tableau JSON, sans texte autour :
[{{"id": 1, "text": "...", {example}}}, ...]
Les ids commencent à 1. Les textes recopient le script mot pour mot, dans l'ordre,
sans rien omettre.

Script :
{script}"""

MAC_RULES = """Pour chaque segment, choisis un "clip" parmi ces gestes filmés : {clips}."""

GPU_RULES = """Pour chaque segment, donne soit un "driver" (vidéo de geste) parmi : {drivers},
soit un "prompt" : une courte description du geste en français (ex. "il énumère sur ses doigts").
Préfère un driver quand il correspond exactement au sens, sinon un prompt."""


def build_prompt(script: str, backend: str, clips: list[str], drivers: list[str]) -> str:
    if backend == "mac":
        rules, example = MAC_RULES.format(clips=", ".join(clips)), '"clip": "..."'
    else:
        rules = GPU_RULES.format(drivers=", ".join(drivers) or "(aucun)")
        example = '"driver": "..." ou "prompt": "..."'
    return PROMPT.format(gesture_rules=rules, example=example, script=script.strip())


def validate(segments: list[Segment], backend: str, clips: list[str], drivers: list[str]) -> None:
    for s in segments:
        if backend == "mac" and s.clip not in clips:
            raise ValueError(f"segment {s.id} : clip inconnu {s.clip!r} (clips.yaml : {clips})")
        if backend == "gpu":
            if s.driver and s.driver not in drivers:
                if not s.prompt:
                    raise ValueError(f"segment {s.id} : driver introuvable {s.driver!r}")
                s.driver = None  # retombe sur le prompt
            if not (s.driver or s.prompt):
                raise ValueError(f"segment {s.id} : ni driver ni prompt")


def parse(reply: str) -> list[Segment]:
    match = re.search(r"\[.*\]", reply, re.DOTALL)
    if not match:
        raise ValueError(f"réponse du LLM sans tableau JSON : {reply[:200]}")
    return Segments.validate_python(json.loads(match.group(0)))


def gateway_llm(base_url: str, model: str) -> Callable[[str], str]:
    """Passerelle LLM compatible OpenAI (POST /chat/completions), clé dans LLM_GATEWAY_API_KEY."""
    key = os.environ.get("LLM_GATEWAY_API_KEY", "")

    def ask(prompt: str) -> str:
        body = {"model": model, "messages": [{"role": "user", "content": prompt}]}
        req = urllib.request.Request(
            base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]

    return ask


def gestures(cfg: Config, backend: str) -> tuple[list[str], list[str]]:
    """Gestes disponibles : (clips de clips.yaml pour mac, vidéos driver pour gpu)."""
    clips = list(load_clips(cfg.path("clips"))) if backend == "mac" else []
    drivers = sorted(p.name for p in cfg.path("drivers").glob("*.mp4"))
    return clips, drivers


def save(cfg: Config, video_id: str, segments: list[Segment], backend: str) -> Path:
    """Valide les segments contre les gestes disponibles et écrit segments.json."""
    validate(segments, backend, *gestures(cfg, backend))
    out = cfg.work_dir(video_id) / "segments.json"
    out.write_text(
        json.dumps(
            [s.model_dump(exclude_none=True) for s in segments], ensure_ascii=False, indent=2
        )
    )
    return out


def segment(
    cfg: Config, script_path: Path, backend: str, llm: Callable[[str], str] | None = None
) -> Path:
    llm = llm or gateway_llm(cfg["segment"]["base_url"], cfg["segment"]["model"])
    prompt = build_prompt(script_path.read_text(), backend, *gestures(cfg, backend))
    return save(cfg, script_path.stem, parse(llm(prompt)), backend)


def load(path: Path) -> list[Segment]:
    return Segments.validate_json(path.read_text())
