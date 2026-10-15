import json

import pytest

from avatar import cli, ffmpeg, segment, voice
from tests.conftest import set_config

SEGMENTS = [
    {"id": 1, "text": "Bienvenue dans le jeu.", "clip": "explique"},
    {"id": 2, "text": "Regardez à droite.", "clip": "montre_droite"},
    {"id": 3, "text": "Trois règles simples.", "clip": "enumere"},
]
# Durées audio factices : la 1re dépasse son clip (7 s) pour tester la boucle.
LENGTHS = {"Bienvenue dans le jeu.": 8.3, "Regardez à droite.": 2.1, "Trois règles simples.": 3.7}


def fake_synth(text, out):
    sine = f"sine=frequency=440:sample_rate=24000:duration={LENGTHS[text]}"
    ffmpeg.run("-f", "lavfi", "-i", sine, "-ac", "1", out)


def test_run_mac_produces_final_video(project, monkeypatch):
    # MuseTalk remplacé par une copie du clip bouclé : on teste la tuyauterie, pas le modèle.
    cfg = set_config(project, mac={"musetalk_cmd": "cp {video} {out}"})
    monkeypatch.setattr(segment, "gateway_llm", lambda url, model: lambda p: json.dumps(SEGMENTS))
    monkeypatch.setattr(voice, "load_engine", lambda cfg: fake_synth)

    cli.main(["--config", str(cfg.root / "config.yaml"), "prepare"])
    cli.main(["--config", str(cfg.root / "config.yaml"), "run",
              str(cfg.root / "scripts/regles.txt"), "--backend", "mac"])  # fmt: skip

    work = cfg.root / "work/regles"
    for s in SEGMENTS:
        assert ffmpeg.duration(work / f"seg_{s['id']}.mp4") == pytest.approx(
            LENGTHS[s["text"]], abs=0.1
        )
    final = ffmpeg.probe(work / "final.mp4")
    assert float(final["format"]["duration"]) == pytest.approx(sum(LENGTHS.values()), abs=0.2)
    v = next(s for s in final["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"], v["r_frame_rate"]) == (1920, 1080, "25/1")
