# make up    installe, configure et lance toute l'app
# make down  arrête tout
#
# Mode détecté automatiquement (forçable : make up MODE=gpu) :
#   mac  Docker pour l'app, worker en natif (MLX n'a pas accès au GPU Apple dans Docker)
#   gpu  tout en Docker : app, worker CUDA, ComfyUI

SHELL := /bin/bash
MODE ?= $(shell if [ "$$(uname -s)" = Darwin ]; then echo mac; \
	elif command -v nvidia-smi >/dev/null 2>&1; then echo gpu; else echo none; fi)
VOICE ?= chatterbox
PORT ?= 8787
COMPOSE := AVATAR_PORT=$(PORT) AVATAR_UID=$(shell id -u) AVATAR_GID=$(shell id -g) docker compose --profile gpu

.PHONY: up down

up: .env
	@command -v docker >/dev/null || { echo "Docker manquant : installe Docker Desktop."; exit 1; }
	@mkdir -p source/drivers scripts work models/huggingface
	@[ -f source/clips.yaml ] || cp source/clips.example.yaml source/clips.yaml
ifeq ($(MODE),mac)
	@command -v uv >/dev/null || { echo "uv manquant : brew install uv"; exit 1; }
	AVATAR_BACKEND=mac $(COMPOSE) up -d --build app
	uv sync $(if $(VOICE),--extra $(VOICE))
	@if [ -f .worker.pid ] && kill -0 $$(cat .worker.pid) 2>/dev/null; then \
		echo "Worker déjà lancé (pid $$(cat .worker.pid))"; \
	else \
		set -a; source .env; set +a; \
		AVATAR_BACKEND=mac nohup uv run avatar worker > work/worker.log 2>&1 & echo $$! > .worker.pid; \
		echo "Worker natif lancé (pid $$(cat .worker.pid)), journal : work/worker.log"; \
	fi
else ifeq ($(MODE),gpu)
	AVATAR_BACKEND=gpu $(COMPOSE) up -d --build
else
	@echo "Ni Mac ni GPU NVIDIA détecté : le pipeline a besoin de l'un des deux. Force avec MODE=mac|gpu."
	@exit 1
endif
	@if [ -f source/source.mp4 ] && [ ! -f source/ref.wav ]; then \
		echo "Préparation de la source (ref.wav, ref.png, clips)…"; \
		$(COMPOSE) exec -T app avatar prepare; \
	fi
	@[ -f source/source.mp4 ] || echo "À faire : dépose la vidéo de la personne filmée dans source/source.mp4 puis relance make up."
	@echo "App : http://localhost:$(PORT)  (mode $(MODE))"

down:
	@if [ -f .worker.pid ]; then kill $$(cat .worker.pid) 2>/dev/null || true; rm -f .worker.pid; echo "Worker natif arrêté"; fi
	$(COMPOSE) down

# Le worker appelle la passerelle : en natif (mac) localhost, en conteneur (gpu) l'hôte Docker.
GATEWAY_DEFAULT := $(if $(filter gpu,$(MODE)),http://host.docker.internal:4000/v1,http://localhost:4000/v1)

# Créé une seule fois : la passerelle LLM qui découpe les scripts.
.env:
	@echo "Configuration de la passerelle LLM (compatible OpenAI), enregistrée dans .env"
	@read -rp "URL de base [$(GATEWAY_DEFAULT)] : " url; \
	 read -rsp "Clé d'API : " key; echo; \
	 read -rp "Modèle [claude-sonnet-5-5] : " model; \
	 { echo "LLM_GATEWAY_URL=$${url:-$(GATEWAY_DEFAULT)}"; \
	   echo "LLM_GATEWAY_API_KEY=$$key"; \
	   echo "LLM_GATEWAY_MODEL=$${model:-claude-sonnet-5-5}"; } > .env
	@chmod 600 .env
