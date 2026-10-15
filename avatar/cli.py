import argparse
from pathlib import Path

from avatar import config
from avatar.assemble import assemble
from avatar.backends import gpu, mac
from avatar.prepare import prepare
from avatar.segment import load, segment
from avatar.voice import voice


def video(cfg, video_id: str, backend: str, only: int | None = None, seed: int | None = None):
    for seg in load(cfg.work_dir(video_id) / "segments.json"):
        if only is not None and seg.id != only:
            continue
        if backend == "mac":
            mac.render(cfg, video_id, seg)
        else:
            gpu.render(cfg, video_id, seg, seed)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="avatar", description="Vidéos tuto avec avatar IA")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("prepare", help="extrait ref.wav, ref.png et les clips de clips.yaml")
    for name, text in [
        ("segment", "script -> segments.json (LLM)"),
        ("voice", "segments.json -> seg_N.wav"),
        ("video", "seg_N.wav -> seg_N.mp4"),
        ("assemble", "seg_N.mp4 + seg_N.wav -> final.mp4"),
        ("run", "segment, voice, video puis assemble"),
    ]:
        p = sub.add_parser(name, help=text)
        p.add_argument("script", type=Path, help="scripts/<video_id>.txt")
        p.add_argument("--backend", choices=["mac", "gpu"])
        if name == "video":
            p.add_argument("--segment", type=int, help="ne régénère que ce segment")
            p.add_argument("--seed", type=int, help="backend gpu : autre seed en cas de dérive")

    args = parser.parse_args(argv)
    cfg = config.load(args.config)
    if args.command == "prepare":
        prepare(cfg)
        return

    video_id = args.script.stem
    backend = args.backend or cfg["backend"]
    if args.command in ("segment", "run"):
        print(segment(cfg, args.script, backend))
    if args.command in ("voice", "run"):
        voice(cfg, video_id)
    if args.command == "video":
        video(cfg, video_id, backend, args.segment, args.seed)
    if args.command == "run":
        video(cfg, video_id, backend)
    if args.command in ("assemble", "run"):
        print(assemble(cfg, video_id))


if __name__ == "__main__":
    main()
