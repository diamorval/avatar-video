"""API REST de l'app web (/api) et service de l'UI React compilée (ui/dist)."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from avatar.config import Config
from avatar.service import Jobs, source_info

UI_DIST = Path(__file__).parent.parent / "ui" / "dist"


class NewVideo(BaseModel):
    name: str
    script: str
    backend: str | None = None


def create_app(cfg: Config, jobs: Jobs) -> FastAPI:
    app = FastAPI(title="avatar-video")

    @app.get("/api/info")
    def info():
        return source_info(cfg)

    @app.get("/api/videos")
    def list_videos():
        return jobs.list()

    @app.post("/api/videos", status_code=201)
    def create_video(body: NewVideo):
        try:
            return jobs.create(body.name, body.script, body.backend)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    def found(video_id: str) -> dict:
        status = jobs.get(video_id)
        if status is None:
            raise HTTPException(404, "vidéo inconnue")
        return status

    @app.get("/api/videos/{video_id}")
    def get_video(video_id: str):
        return found(video_id)

    @app.get("/api/videos/{video_id}/final.mp4")
    def final(video_id: str):
        status = found(video_id)
        if not status["final"]:
            raise HTTPException(404, "vidéo pas encore assemblée")
        return FileResponse(status["final"], media_type="video/mp4")

    if UI_DIST.exists():
        app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
    return app
