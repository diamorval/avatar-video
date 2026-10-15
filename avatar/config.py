import os
from pathlib import Path

import yaml


class Config(dict):
    """config.yaml chargé, avec les chemins résolus par rapport à son dossier."""

    def __init__(self, data: dict, root: Path):
        super().__init__(data)
        self.root = root

    def path(self, key: str) -> Path:
        return self.root / self["paths"][key]

    def work_dir(self, video_id: str) -> Path:
        d = self.path("work") / video_id
        d.mkdir(parents=True, exist_ok=True)
        return d


# Variables d'environnement qui priment sur config.yaml (Docker, .env).
ENV = {
    "AVATAR_BACKEND": ("backend",),
    "AVATAR_VOICE_DEVICE": ("voice", "device"),
    "AVATAR_COMFY_URL": ("gpu", "comfy_url"),
    "LLM_GATEWAY_URL": ("segment", "base_url"),
    "LLM_GATEWAY_MODEL": ("segment", "model"),
}


def load(path: Path) -> Config:
    path = path.resolve()
    data = yaml.safe_load(path.read_text())
    for var, keys in ENV.items():
        if os.environ.get(var):
            node = data
            for key in keys[:-1]:
                node = node[key]
            node[keys[-1]] = os.environ[var]
    return Config(data, path.parent)
