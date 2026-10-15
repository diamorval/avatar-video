import shutil
from pathlib import Path

import pytest
import yaml

from avatar import config, ffmpeg

ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="session")
def source_mp4(tmp_path_factory) -> Path:
    """Vidéo source factice : 30 s, 1080p, 25 i/s, avec du son."""
    out = tmp_path_factory.mktemp("src") / "source.mp4"
    ffmpeg.run(
        "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=25:duration=30",
        "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=30",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", out,
    )  # fmt: skip
    return out


@pytest.fixture
def project(tmp_path, source_mp4):
    """Copie du projet avec la source factice et clips.yaml, renvoie la config chargée."""
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    (tmp_path / "source/drivers").mkdir(parents=True)
    shutil.copy(source_mp4, tmp_path / "source/source.mp4")
    shutil.copy(ROOT / "source/clips.example.yaml", tmp_path / "source/clips.yaml")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/regles.txt").write_text(
        "Bienvenue dans le jeu. Regardez à droite. Trois règles simples."
    )
    return config.load(tmp_path / "config.yaml")


def set_config(cfg, **sections):
    data = yaml.safe_load((cfg.root / "config.yaml").read_text())
    for section, values in sections.items():
        data[section].update(values)
    (cfg.root / "config.yaml").write_text(yaml.safe_dump(data, allow_unicode=True))
    return config.load(cfg.root / "config.yaml")
