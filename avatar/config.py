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


def load(path: Path) -> Config:
    path = path.resolve()
    return Config(yaml.safe_load(path.read_text()), path.parent)
