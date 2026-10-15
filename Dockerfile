# Image unique, deux cibles :
#   app         API REST + UI React + serveur MCP (léger, sans modèle)
#   worker-gpu  exécute les vidéos sur GPU NVIDIA : voix Chatterbox (CUDA), vidéo via ComfyUI
# Sur Mac, le worker tourne en natif (MLX n'a pas accès au GPU dans Docker).

FROM node:22-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY ui/ ./
RUN npm run build

FROM python:3.13-slim AS base
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
 && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.11.32
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/venv PATH=/venv/bin:$PATH
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./

FROM base AS app
RUN uv sync --frozen --no-dev --no-install-project
COPY avatar/ avatar/
RUN uv sync --frozen --no-dev
COPY --from=ui /ui/dist ui/dist
EXPOSE 8787
CMD ["avatar", "serve", "--host", "0.0.0.0", "--port", "8787"]

FROM base AS worker-gpu
RUN uv sync --frozen --no-dev --no-install-project --extra chatterbox
COPY avatar/ avatar/
RUN uv sync --frozen --no-dev --extra chatterbox
CMD ["avatar", "worker"]
