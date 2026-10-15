import json

import pytest

from avatar.segment import build_prompt, load, segment

SCRIPT = "Bienvenue dans le jeu. Regardez à droite. Trois règles simples."


def fake_llm(reply):
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        return reply

    ask.prompts = prompts
    return ask


def test_mac_writes_valid_segments(project):
    reply = """Voici :
    [{"id": 1, "text": "Bienvenue dans le jeu.", "clip": "explique"},
     {"id": 2, "text": "Regardez à droite.", "clip": "montre_droite"},
     {"id": 3, "text": "Trois règles simples.", "clip": "enumere"}]"""
    llm = fake_llm(reply)
    out = segment(project, project.root / "scripts/regles.txt", "mac", llm)

    assert out == project.root / "work/regles/segments.json"
    assert [s.clip for s in load(out)] == ["explique", "montre_droite", "enumere"]
    assert "explique, montre_droite, enumere, conclut" in llm.prompts[0]


def test_mac_rejects_unknown_clip(project):
    reply = '[{"id": 1, "text": "Bienvenue.", "clip": "danse"}]'
    with pytest.raises(ValueError, match="clip inconnu"):
        segment(project, project.root / "scripts/regles.txt", "mac", fake_llm(reply))


def test_gpu_falls_back_to_prompt_when_driver_missing(project):
    (project.path("drivers") / "pointe_droite.mp4").touch()
    reply = json.dumps(
        [
            {"id": 1, "text": "Regardez à droite.", "driver": "pointe_droite.mp4"},
            {"id": 2, "text": "Trois règles.", "driver": "absent.mp4", "prompt": "il énumère"},
        ]
    )
    out = segment(project, project.root / "scripts/regles.txt", "gpu", fake_llm(reply))
    data = json.loads(out.read_text())
    assert data[0] == {"id": 1, "text": "Regardez à droite.", "driver": "pointe_droite.mp4"}
    assert data[1] == {"id": 2, "text": "Trois règles.", "prompt": "il énumère"}


def test_gpu_rejects_missing_driver_without_prompt(project):
    reply = '[{"id": 1, "text": "Regardez.", "driver": "absent.mp4"}]'
    with pytest.raises(ValueError, match="driver introuvable"):
        segment(project, project.root / "scripts/regles.txt", "gpu", fake_llm(reply))


def test_segment_without_gesture_is_invalid(project):
    with pytest.raises(ValueError, match="ni clip"):
        segment(project, project.root / "scripts/regles.txt", "mac",
                fake_llm('[{"id": 1, "text": "Bienvenue."}]'))  # fmt: skip


def test_gpu_prompt_lists_drivers():
    prompt = build_prompt(SCRIPT, "gpu", [], ["pointe_droite.mp4"])
    assert "pointe_droite.mp4" in prompt and SCRIPT in prompt
