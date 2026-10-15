# avatar-video

Génère des vidéos parlées où une personne réelle (avec son accord) dit un script avec sa voix et
son visage, à partir d'une seule vidéo source de 30 s : tutos, formations, communication interne,
présentations produit, messages personnalisés. Deux backends : Mac M5 (MLX, gestes de la source)
et GPU NVIDIA (ComfyUI, gestes générés).

```bash
make up     # installe, configure (passerelle LLM, une fois) et lance tout
make down   # arrête tout
```

`make up` détecte la machine :

- **Mac** : l'app (UI + API + MCP) tourne en Docker, le worker en natif, car MLX n'a pas accès
  au GPU Apple dans Docker. Prérequis : Docker Desktop et `uv` (`brew install uv`).
- **GPU NVIDIA** : tout tourne en Docker (app, worker CUDA, ComfyUI). Prérequis : Docker et
  NVIDIA Container Toolkit. Les poids des modèles vont dans `models/`.

Ensuite :

1. Dépose la vidéo de la personne filmée dans `source/source.mp4` et ajuste `source/clips.yaml`
   à ses gestes, puis relance `make up` : la source est préparée automatiquement.
2. Ouvre http://localhost:8787, colle un script, clique « Générer ».
3. Depuis Claude Code, ouvre ce dossier : `.mcp.json` branche Claude sur l'app lancée
   (outils `create_video`, `get_video`...).

Spec, plan et conformité (AI Act, données biométriques) : voir [CLAUDE.md](CLAUDE.md).
Les dossiers `source/`, `work/` et `models/` ne sont jamais versionnés.
