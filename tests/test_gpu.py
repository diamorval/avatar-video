import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from avatar import ffmpeg
from avatar.backends import gpu
from avatar.segment import Segment
from tests.conftest import set_config


def test_fill_keeps_type_of_whole_marker():
    wf = {"1": {"inputs": {"seed": "{{seed}}", "text": "geste : {{prompt}}", "n": 3}}}
    assert gpu.fill(wf, {"seed": 7, "prompt": "il pointe"}) == {
        "1": {"inputs": {"seed": 7, "text": "geste : il pointe", "n": 3}}
    }


@pytest.fixture
def comfy(tmp_path):
    """Faux ComfyUI : garde les fichiers envoyés et les workflows reçus, rend une vidéo."""
    video = tmp_path / "out.mp4"
    ffmpeg.run("-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25:duration=2",
               "-pix_fmt", "yuv420p", video)  # fmt: skip
    state = {"uploads": [], "prompts": []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, data):
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            if self.path == "/upload/image":
                name = body.split(b'filename="')[1].split(b'"')[0].decode()
                state["uploads"].append(name)
                self._json({"name": name, "subfolder": "", "type": "input"})
            else:
                state["prompts"].append(json.loads(body)["prompt"])
                self._json({"prompt_id": f"p{len(state['prompts'])}"})

        def do_GET(self):
            url = urlparse(self.path)
            if url.path.startswith("/history/"):
                pid = url.path.rsplit("/", 1)[1]
                out = {"9": {"gifs": [{"filename": "r.mp4", "subfolder": "", "type": "output"}]}}
                self._json({pid: {"status": {"status_str": "success"}, "outputs": out}})
            else:
                assert parse_qs(url.query)["filename"] == ["r.mp4"]
                data = video.read_bytes()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{server.server_port}"
    yield state
    server.shutdown()


def write_workflows(cfg):
    for name in ("infinitetalk", "animate", "musetalk"):
        wf = {
            "1": {
                "class_type": name,
                "inputs": {k: f"{{{{{k}}}}}" for k in ("ref_image", "audio", "prompt", "seed")},
            }
        }
        if name == "animate":
            wf["1"]["inputs"]["driver"] = "{{driver}}"
        if name == "musetalk":
            wf["1"]["inputs"] = {"video": "{{video}}", "audio": "{{audio}}"}
        path = cfg.root / cfg["gpu"]["workflows"][name]
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(wf))


def prepare_segment(cfg):
    work = cfg.work_dir("regles")
    ffmpeg.run("-f", "lavfi", "-i", "sine=duration=2", work / "seg_1.wav")
    ffmpeg.run("-f", "lavfi", "-i", "color=size=64x64", "-frames:v", "1", cfg.path("ref_png"))
    return work


def test_prompt_segment_uses_infinitetalk(project, comfy):
    cfg = set_config(project, gpu={"comfy_url": comfy["url"]})
    write_workflows(cfg)
    work = prepare_segment(cfg)

    gpu.render(cfg, "regles", Segment(id=1, text="t", prompt="il énumère"), seed=11)

    [wf] = comfy["prompts"]
    assert wf["1"]["class_type"] == "infinitetalk"
    assert wf["1"]["inputs"] == {
        "ref_image": "ref.png",
        "audio": "seg_1.wav",
        "prompt": "il énumère",
        "seed": 11,
    }
    assert ffmpeg.duration(work / "seg_1.mp4") == pytest.approx(2, abs=0.1)
    assert sorted(p.name for p in (work / "qc").iterdir()) == [
        "seg_1_1.png",
        "seg_1_2.png",
        "seg_1_3.png",
    ]


def test_driver_segment_chains_animate_then_musetalk(project, comfy):
    cfg = set_config(project, gpu={"comfy_url": comfy["url"]})
    write_workflows(cfg)
    prepare_segment(cfg)
    ffmpeg.run("-f", "lavfi", "-i", "testsrc2=duration=1", cfg.path("drivers") / "pointe.mp4")

    gpu.render(cfg, "regles", Segment(id=1, text="t", driver="pointe.mp4"))

    animate, musetalk = comfy["prompts"]
    assert animate["1"]["inputs"]["driver"] == "pointe.mp4"
    assert musetalk["1"]["inputs"] == {"video": "seg_1_animate.mp4", "audio": "seg_1.wav"}
