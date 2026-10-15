import asyncio
import json
import sys
import time

import pytest
from fastapi.testclient import TestClient
from mcp import Client, StdioServerParameters

from avatar import segment, voice
from avatar.mcp_server import create_mcp
from avatar.prepare import prepare
from avatar.server import create_app
from avatar.service import Jobs, slug
from tests.conftest import set_config
from tests.test_run import SEGMENTS, fake_synth

SCRIPT = "Bienvenue dans le jeu. Regardez à droite. Trois règles simples."


@pytest.fixture
def jobs(project, monkeypatch):
    """Pipeline complet sur la source factice, LLM, voix et MuseTalk simulés."""
    cfg = set_config(project, mac={"musetalk_cmd": "cp {video} {out}"})
    prepare(cfg)
    monkeypatch.setattr(segment, "gateway_llm", lambda url, model: lambda p: json.dumps(SEGMENTS))
    monkeypatch.setattr(voice, "load_engine", lambda cfg: fake_synth)
    return Jobs(cfg)


def wait_done(get, video_id, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = get(video_id)
        if status["state"] in ("done", "error"):
            return status
        time.sleep(0.5)
    raise TimeoutError(video_id)


def test_slug():
    assert slug("Règles du jeu !") == "regles-du-jeu"
    assert slug("???") == "video"


def test_rest_creates_video_and_serves_final(jobs):
    client = TestClient(create_app(jobs.cfg, jobs))
    assert client.get("/api/info").json() == {
        "default_backend": "mac",
        "source_ready": True,
        "clips": ["explique", "montre_droite", "enumere", "conclut"],
        "drivers": [],
    }

    res = client.post("/api/videos", json={"name": "Règles du jeu", "script": SCRIPT})
    assert res.status_code == 201
    assert res.json()["id"] == "regles-du-jeu"
    # Même nom : nouvel identifiant, la première vidéo n'est pas écrasée.
    assert (
        client.post("/api/videos", json={"name": "Règles du jeu", "script": SCRIPT}).json()["id"]
        == "regles-du-jeu-2"
    )

    status = wait_done(lambda i: client.get(f"/api/videos/{i}").json(), "regles-du-jeu")
    assert status["state"] == "done", status["error"]
    assert [s["clip"] for s in status["segments"]] == ["explique", "montre_droite", "enumere"]
    video = client.get("/api/videos/regles-du-jeu/final.mp4")
    assert video.headers["content-type"] == "video/mp4" and len(video.content) > 1000
    assert [v["id"] for v in client.get("/api/videos").json()] == [
        "regles-du-jeu-2", "regles-du-jeu"
    ]  # fmt: skip


def test_rest_rejects_bad_input(jobs):
    client = TestClient(create_app(jobs.cfg, jobs))
    assert client.post("/api/videos", json={"name": "x", "script": "  "}).status_code == 422
    assert (
        client.post(
            "/api/videos", json={"name": "x", "script": SCRIPT, "backend": "tpu"}
        ).status_code
        == 422
    )
    assert client.get("/api/videos/inconnue").status_code == 404
    assert client.get("/api/videos/..%2Fsource").status_code == 404


def test_final_is_hidden_until_done(jobs, monkeypatch):
    monkeypatch.setattr(jobs.queue, "put", lambda video_id: None)  # pas d'exécution
    video_id = jobs.create("En cours", SCRIPT)["id"]
    (jobs.cfg.path("work") / video_id / "final.mp4").write_bytes(b"partiel")
    assert jobs.get(video_id)["final"] is None


def test_pipeline_error_is_reported(jobs, monkeypatch):
    monkeypatch.setattr(segment, "gateway_llm", lambda url, model: lambda p: "pas de JSON")
    video_id = jobs.create("Erreur", SCRIPT)["id"]
    status = wait_done(jobs.get, video_id)
    assert status["state"] == "error" and status["step"] == "segment"
    assert "sans tableau JSON" in status["error"]


def call_tool(server, tool, **args):
    """Appelle un outil MCP comme le ferait Claude, renvoie (erreur ?, contenu structuré)."""

    async def go():
        async with Client(server) as client:
            res = await client.call_tool(tool, args)
            if res.is_error:
                return True, res.content[0].text
            if res.structured_content:  # listes : {"result": [...]}
                return False, res.structured_content["result"]
            return False, json.loads(res.content[0].text)

    return asyncio.run(go())


def test_mcp_create_video_with_claude_segments(jobs, monkeypatch):
    # Claude fournit le découpage : la passerelle LLM ne doit pas être appelée.
    monkeypatch.setattr(segment, "gateway_llm", lambda url, model: pytest.fail("LLM appelé"))
    mcp = create_mcp(jobs.cfg, jobs)

    _, created = call_tool(mcp, "create_video", name="Par Claude", script=SCRIPT, segments=SEGMENTS)
    status = wait_done(lambda i: call_tool(mcp, "get_video", video_id=i)[1], created["id"])
    assert status["state"] == "done", status["error"]
    assert status["final"].endswith("work/par-claude/final.mp4")
    assert [v["id"] for v in call_tool(mcp, "list_videos")[1]] == ["par-claude"]


def test_mcp_rejects_unknown_clip_without_leaving_files(jobs):
    mcp = create_mcp(jobs.cfg, jobs)
    bad = [{"id": 1, "text": "Bonjour.", "clip": "danse"}]
    is_error, message = call_tool(mcp, "create_video", name="x", script="Bonjour.", segments=bad)
    assert is_error and "clip inconnu" in message
    assert not (jobs.cfg.path("work") / "x").exists()
    assert not (jobs.cfg.root / "scripts/x.txt").exists()


def test_mcp_stdio_server_lists_tools(project):
    """Le serveur tel que Claude Code le lance (.mcp.json) répond en stdio."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "avatar.cli", "--config", str(project.root / "config.yaml"), "mcp"],
    )

    async def tools():
        async with Client(params) as client:
            return sorted(t.name for t in (await client.list_tools()).tools)

    assert asyncio.run(tools()) == ["create_video", "get_source_info", "get_video", "list_videos"]
    is_error, info = call_tool(params, "get_source_info")
    assert not is_error
    assert info["source_ready"] is False and info["clips"][0] == "explique"
