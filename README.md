# avatar-video

Génère des vidéos tuto où un partenaire (avec son accord) dit un script avec sa voix et son
visage, à partir d'une seule vidéo source de 30 s. Deux backends : Mac M5 (MLX, gestes de la
source) et GPU NVIDIA (ComfyUI, gestes générés).

```bash
uv sync --extra chatterbox
cp source/clips.example.yaml source/clips.yaml   # puis ajuster aux gestes filmés
uv run avatar prepare
uv run avatar run scripts/exemple.txt --backend mac
```

Spec, plan et conformité (AI Act, données biométriques) : voir [CLAUDE.md](CLAUDE.md).
Les dossiers `source/` et `work/` ne sont jamais versionnés.
