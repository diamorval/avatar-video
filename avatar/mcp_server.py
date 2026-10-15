"""Serveur MCP (stdio) : Claude Code pilote les mêmes vidéos que l'app web."""

import os

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from avatar.config import Config
from avatar.service import Jobs, source_info


def create_mcp(cfg: Config, jobs: Jobs) -> MCPServer:
    mcp = MCPServer("avatar-video")

    @mcp.tool()
    def get_source_info() -> dict:
        """Backend par défaut, source prête ou non, gestes disponibles (clips mac, drivers gpu)."""
        return source_info(cfg)

    @mcp.tool()
    def create_video(
        name: str, script: str, backend: str | None = None, segments: list[dict] | None = None
    ) -> dict:
        """Crée une vidéo à partir d'un script et lance sa génération en tâche de fond.

        Sans `segments`, la passerelle LLM découpe le script. Pour découper toi-même, passe
        `segments` au format [{"id": 1, "text": "...", "clip": "..."}] (backend mac) ou avec
        "driver" / "prompt" (backend gpu), en prenant les gestes de get_source_info.
        Suis l'avancement avec get_video.
        """
        try:
            return jobs.create(name, script, backend, segments)
        except ValueError as e:  # message renvoyé à Claude pour qu'il corrige son appel
            raise ToolError(str(e)) from e

    @mcp.tool()
    def list_videos() -> list[dict]:
        """Toutes les vidéos, la plus récente d'abord, avec leur état et l'étape en cours."""
        return jobs.list()

    @mcp.tool()
    def get_video(video_id: str) -> dict:
        """État d'une vidéo, ses segments, et l'URL de final.mp4 une fois terminée."""
        status = jobs.get(video_id)
        if status is None:
            raise ToolError(f"vidéo inconnue : {video_id}")
        if status["final"]:
            # Le chemin vaut dans le conteneur ; l'URL vaut pour l'utilisateur.
            base = os.environ.get("AVATAR_PUBLIC_URL", "http://localhost:8787")
            status["url"] = f"{base}/api/videos/{video_id}/final.mp4"
        return status

    return mcp
