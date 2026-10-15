import argparse
from pathlib import Path

from avatar import config
from avatar.assemble import assemble
from avatar.prepare import prepare
from avatar.segment import segment
from avatar.service import Jobs, render_video
from avatar.voice import voice


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="avatar", description="Vidéos tuto avec avatar IA")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("prepare", help="extrait ref.wav, ref.png et les clips de clips.yaml")
    serve = sub.add_parser("serve", help="app web : API REST et UI React sur http://localhost:PORT")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)
    sub.add_parser("mcp", help="serveur MCP en stdio, pour Claude Code (.mcp.json)")
    sub.add_parser("worker", help="exécute les vidéos créées par l'app ou par Claude")
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
    if args.command == "serve":
        import uvicorn

        from avatar.server import create_app

        uvicorn.run(create_app(cfg, Jobs(cfg)), host=args.host, port=args.port)
        return
    if args.command == "mcp":
        from avatar.mcp_server import create_mcp

        create_mcp(cfg, Jobs(cfg)).run()
        return
    if args.command == "worker":
        print("worker prêt", flush=True)
        Jobs(cfg).work_forever()
        return

    video_id = args.script.stem
    backend = args.backend or cfg["backend"]
    if args.command in ("segment", "run"):
        print(segment(cfg, args.script, backend))
    if args.command in ("voice", "run"):
        voice(cfg, video_id)
    if args.command == "video":
        render_video(cfg, video_id, backend, args.segment, args.seed)
    if args.command == "run":
        render_video(cfg, video_id, backend)
    if args.command in ("assemble", "run"):
        print(assemble(cfg, video_id))


if __name__ == "__main__":
    main()
