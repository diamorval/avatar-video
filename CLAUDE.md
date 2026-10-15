# Avatar vidéo IA : spec projet (Mac / GPU)

15/10/2026

## Objectif

Générer des vidéos parlées avec la voix et le visage d'une personne réelle, à partir d'une seule vidéo de 30 s, avec une gestuelle qui varie selon le contexte du script. L'outil est générique : tutos, formations, communication interne, présentations produit, messages personnalisés. Premier cas d'usage : les tutos du jeu d'acculturation.

- **Entrée** : une vidéo source de 30 s (fixe) et un script texte (un par vidéo).
- **Sortie** : un MP4 où la personne dit le script avec sa voix, dans la langue de `config.yaml` (français par défaut).
- **Cadre** : la personne filmée a donné son accord, et il n'y a pas de question de propriété intellectuelle.
- **Deux cibles d'exécution** : Mac M5 16 Go (local, gestuelle limitée) ou GPU NVIDIA (gestuelle générée).

## Choisir son option

Le Mac suffit si les gestes de la vidéo source conviennent. Le GPU devient nécessaire dès que tu veux des gestes de mains nouveaux à chaque vidéo.

| Critère | Option A : Mac M5 16 Go | Option B : GPU NVIDIA |
| --- | --- | --- |
| Gestuelle | Celle des 30 s, réordonnée par segments, plus les mouvements de tête générés | Gestes nouveaux : à la demande (transfert) ou libres (prompt) |
| Réalisme | Très élevé (vrais gestes) | Bon, mains et identité à vérifier |
| Vitesse | Lip-sync en temps réel | 10 à 30 min de calcul par minute de vidéo |
| Matériel | Mac M5, environ 7 Go de mémoire au pic | 24 Go de VRAM minimum (RTX 3090) ; 48 Go et plus pour produire en série (RunPod) |
| Coût | Nul | Location GPU, ou 3090 locale |
| Usage type | Vidéos courtes, ton constant, volume élevé | Vidéos variées, mises en scène, gestes précis |

Les deux options partagent la préparation de la source et l'étape de génération de la voix. Seule l'étape vidéo change : le projet expose donc un paramètre `--backend mac|gpu`.

## Entrée commune : la vidéo source

La vidéo de 30 s est préparée une seule fois. Tout le reste en découle.

**Consignes de tournage**

- Cadrage en buste, mains visibles, face caméra, en 1080p.
- Lumière stable, fond neutre, rien devant le visage.
- La personne parle naturellement, dans la langue des vidéos à produire, avec 3 ou 4 gestuelles distinctes : explique, montre à droite, énumère sur les doigts, conclut.
- Une seconde bouche fermée au début, pour l'image de référence.

**Extraction (étape `prepare`)**

```bash
# Voix de référence : 15 à 20 s propres, mono 24 kHz
ffmpeg -i source.mp4 -ss 00:00:05 -t 20 -ac 1 -ar 24000 ref.wav
# Image de référence : buste de face, bouche fermée
ffmpeg -i source.mp4 -ss 00:00:00.5 -frames:v 1 ref.png
```

Pour l'option A, `prepare` découpe aussi la source en segments étiquetés dans `clips.yaml` (ex. `explique: 00:02-00:09`). Le découpage peut être fait à la main la première fois.

## Option A : Mac M5 16 Go

Tout tourne en local en MLX ou MPS. La gestuelle vient des vrais segments de la source, choisis par un LLM à chaque passage du script.

**Pipeline**

1. **Segmenter** : un LLM découpe le script en phrases et étiquette chacune avec un clip de `clips.yaml`.
2. **Voix** : OmniVoice (MPS) ou Chatterbox, avec `ref.wav`, produisent un `seg_N.wav` par segment.
3. **Lip-sync** : MuseTalk 1.5 MLX recale la bouche du clip choisi sur `seg_N.wav`, en bouclant le clip si l'audio est plus long.
4. **Variante tête seule** (facultative) : JoyVASA + LivePortrait génèrent les mouvements de tête à partir de `ref.png` et de l'audio. Utile pour les plans serrés.
5. **Assemblage** : concat ffmpeg avec un fondu de 6 frames entre les segments.

**Modèles**

| Brique | Modèle | Licence | Notes |
| --- | --- | --- | --- |
| Voix | OmniVoice | Apache 2.0 | Supporte MPS, 3 à 10 s de référence |
| Voix (alt.) | Chatterbox | MIT | Environ 5 s de référence, 23 langues |
| Lip-sync | [MuseTalk 1.5 MLX](https://huggingface.co/mlx-community/MuseTalk-1.5-fp16) | MIT | Temps réel sur M-series, environ 7 Go au pic |
| Tête générée | JoyVASA + LivePortrait ([skill talking-head](https://github.com/puntorigen/skills)) | À vérifier | Apple Silicon, environ 6 Go de disque |

**Limites**

- Pas de geste de main nouveau : la variété se limite aux 30 s de source. Avec un Mac 32 Go, [ComfyUI-LTX-MLX-A2V](https://trendshift.io/repositories/74168) (LTX-2.3 en MLX) est une piste à tester pour générer du mouvement.

## Option B : GPU NVIDIA

Chaque segment est généré de zéro à partir de `ref.png`. Les gestes sont nouveaux et pilotés soit par une vidéo de mouvement, soit par un prompt.

**Pipeline**

1. **Segmenter** : un LLM découpe le script et attribue à chaque segment soit un `driver` (vidéo de geste), soit un `prompt` (description du geste).
2. **Voix** : identique à l'option A (Chatterbox ou OmniVoice sur CUDA).
3. **Vidéo**, deux modes selon le segment :
    - **Geste précis** : Wan2.2-Animate applique le mouvement d'une vidéo `driver` (toi filmé en train de faire le geste) à la personne filmée, puis MuseTalk cale la bouche sur l'audio.
    - **Geste libre** : InfiniteTalk (image vers vidéo) génère la vidéo à partir de `ref.png`, de l'audio et du prompt, déjà synchronisée.
4. **Contrôle qualité** : extraire 3 images par segment pour vérifier les mains et l'identité. Régénérer avec un autre seed en cas de dérive.
5. **Assemblage** : identique à l'option A.

**Modèles**

| Brique | Modèle | Notes |
| --- | --- | --- |
| Geste précis | Wan2.2-Animate (14B) | Transfert de mouvement depuis une vidéo `driver` |
| Geste libre | InfiniteTalk (base Wan2.1, 14B) | Image + audio + prompt, mouvements de tête et de buste |
| Lip-sync | MuseTalk 1.5 | Après Wan2.2-Animate uniquement |

**Matériel**

- RTX 4070 Ti Super 16 Go : versions quantifiées (GGUF) dans ComfyUI, possibles mais lentes. Bon pour prototyper.
- RTX 3090 24 Go : confortable pour un usage régulier.
- RunPod, 48 Go et plus : pour produire en série. Exécuter les workflows ComfyUI via son API.

## Architecture du projet

Un CLI Python unique, dont seule l'étape vidéo dépend du backend. Chaque étape lit et écrit des fichiers dans `work/<video_id>/`, ce qui permet de relancer une étape sans refaire les autres.

```text
avatar-video/
├── CLAUDE.md              # ce document
├── config.yaml            # backend, modèles, chemins, langue
├── source/
│   ├── source.mp4
│   ├── ref.wav, ref.png   # produits par prepare
│   ├── clips.yaml         # option A : segments étiquetés
│   └── drivers/           # option B : vidéos de gestes
├── scripts/               # un .txt par vidéo à produire
├── avatar/
│   ├── cli.py             # prepare | segment | voice | video | assemble | run
│   ├── segment.py         # LLM : script -> segments.json
│   ├── voice.py           # OmniVoice / Chatterbox
│   ├── assemble.py        # ffmpeg concat + fondus
│   └── backends/
│       ├── mac.py         # MuseTalk MLX, LivePortrait
│       └── gpu.py         # ComfyUI API : Wan2.2-Animate, InfiniteTalk, MuseTalk
├── comfy_workflows/       # option B : workflows ComfyUI exportés en JSON
└── work/<video_id>/       # segments.json, seg_N.wav, seg_N.mp4, final.mp4
```

**Contrat `segments.json`** (sortie de `segment`, entrée des étapes suivantes)

```json
[
  {"id": 1, "text": "Bienvenue dans cette présentation.", "clip": "explique"},
  {"id": 2, "text": "Regardez à droite.", "driver": "pointe_droite.mp4"},
  {"id": 3, "text": "Trois points à retenir.", "prompt": "il énumère sur ses doigts"}
]
```

`clip` est utilisé par le backend Mac. `driver` ou `prompt` sont utilisés par le backend GPU, qui retombe sur `prompt` si aucun driver n'est fourni.

**Commande cible**

```bash
avatar run scripts/regles.txt --backend mac   # ou --backend gpu
```

## Plan d'implémentation

Construire d'abord le backend Mac de bout en bout, puis brancher le GPU. Chaque étape a un critère de validation vérifiable avant de passer à la suivante.

1. **`prepare`** : extrait `ref.wav` et `ref.png`. Vérification : `ref.wav` dure entre 15 et 20 s en mono 24 kHz, et `ref.png` montre la bouche fermée.
2. **`voice`** : une phrase de test produit un `.wav`. Vérification : à l'écoute, la voix est reconnaissable et le français intelligible.
3. **`video --backend mac`** : un clip et un `.wav` produisent un `.mp4`. Vérification : décalage lèvres/son inférieur à 2 frames à l'œil.
4. **`segment`** : le script produit un `segments.json` valide. Vérification : validation du schéma, et chaque `clip` existe dans `clips.yaml`.
5. **`assemble` et `run`** : un script de 3 phrases produit `final.mp4`. Vérification : pas de saut visible entre segments, durée égale à la somme des audios à 0,2 s près.
6. **`video --backend gpu`** : un segment en `prompt` (InfiniteTalk), puis un en `driver` (Wan2.2-Animate + MuseTalk). Vérification : identité stable sur 3 images, mains sans artefact.

Compte environ 1 jour pour les étapes 1 à 5 sur Mac, et 1 à 2 jours pour l'étape 6, installation ComfyUI comprise.

## Conformité et points à vérifier

- [ ] Accord écrit de la personne filmée : périmètre d'usage, durée, suppression des données (`ref.wav`, `ref.png`, source).
- [ ] Mention « vidéo générée par IA » à l'écran : l'AI Act (article 50) impose cette transparence pour les contenus de type deepfake.
- [ ] Vérifier les licences des poids d'InfiniteTalk, Wan2.2-Animate, JoyVASA et LivePortrait avant tout usage client. Les versions de ces modèles sont citées de mémoire et évoluent vite.
- [ ] Ne pas versionner `source/` ni `work/` dans git (données biométriques de la personne filmée).

## Sources

- [MuseTalk 1.5 MLX (Hugging Face)](https://huggingface.co/mlx-community/MuseTalk-1.5-fp16)
- [puntorigen/skills, talking-head](https://github.com/puntorigen/skills)
- [ComfyUI-LTX-MLX-A2V](https://trendshift.io/repositories/74168)
- [OmniVoice (DEV Community)](https://dev.to/sangrokjung/omnivoice-open-source-tts-with-600-languages-and-zero-shot-voice-cloning-1mpn)
- [Comparatif TTS open source 2026 (Second Talent)](https://www.secondtalent.com/resources/open-source-ai-voice-generators/)
- [GitHub topic talking-avatar](https://github.com/topics/talking-avatar)

## App web et MCP

Deux portes, un moteur : l'app web (REST) et Claude (MCP) appellent le même `avatar/service.py`.
Tout est automatique : on envoie un script, un processus `avatar worker` enchaîne segment, voice,
video et assemble, une vidéo à la fois. L'état de chaque vidéo vit dans `work/<id>/status.json`,
et `work/<id>/claim` (créé de façon exclusive, touché toutes les 10 s) dit quel worker l'exécute :
une vidéo lancée par Claude apparaît dans l'app, et inversement.

```text
avatar/service.py      Jobs : création, file, exécution, état (status.json)
avatar/server.py       API REST /api + UI compilée (ui/dist), lancé par `avatar serve`
avatar/mcp_server.py   outils MCP, lancé en stdio par `avatar mcp` (.mcp.json)
ui/                    UI React réutilisable : <AvatarStudio apiBase="..." />
Dockerfile             cibles app (UI + API + MCP) et worker-gpu (Chatterbox CUDA)
docker/                image ComfyUI (Wan2.2-Animate, InfiniteTalk, MuseTalk)
docker-compose.yml     app ; profil gpu : worker + comfyui
Makefile               make up / make down, détection mac ou gpu
```

- **Docker** : sur Mac, seule l'app est en conteneur et le worker tourne en natif (MLX n'a pas
  accès au GPU Apple dans Docker). Sur GPU NVIDIA, tout est en conteneur. Les conteneurs
  tournent avec l'UID de l'utilisateur. Les variables `AVATAR_BACKEND`, `AVATAR_VOICE_DEVICE`,
  `AVATAR_COMFY_URL`, `LLM_GATEWAY_URL`, `LLM_GATEWAY_MODEL` priment sur `config.yaml`.

- **Découpage** : la passerelle LLM compatible OpenAI de `config.yaml` (`segment.base_url`,
  `segment.model`, clé dans `LLM_GATEWAY_API_KEY`), ou `.env` créé par `make up`. Via MCP, Claude peut passer ses propres
  `segments` à `create_video` et se passer de la passerelle.
- **API REST** : `GET /api/info`, `GET|POST /api/videos`, `GET /api/videos/{id}`,
  `GET /api/videos/{id}/final.mp4`.
- **Outils MCP** : `get_source_info`, `create_video`, `list_videos`, `get_video`.
- **Réutiliser l'UI** : `import { AvatarStudio } from "@avatar-video/ui"` et
  `import "@avatar-video/ui/styles.css"`. Les composants (`ScriptForm`, `VideoList`, `VideoPanel`)
  et le client `createApi` sont exportés séparément. La charte par défaut est celle de Diametral
  (Geist, Ufficio 300, logo, palette V.1, dans `ui/src/assets/diametral/`). Elle se change en surchargeant les
  variables `--av-*` de `.av-studio`.

## Commandes

```bash
make up                                   # tout : Docker, worker, .env, préparation de la source
make down
uv sync                                   # dépendances de base (prepare, segment, assemble, app, MCP)
uv sync --extra chatterbox               # ou --extra omnivoice (torch, sur la machine cible)
uv run avatar prepare                     # ref.wav, ref.png, source/clips/<nom>.mp4
uv run avatar run scripts/regles.txt --backend mac
uv run avatar segment|voice|video|assemble scripts/regles.txt [--backend mac|gpu]
uv run avatar serve                       # app web sur http://localhost:8787
uv run avatar worker                      # exécute les vidéos créées par l'app ou Claude
uv run avatar mcp                         # serveur MCP stdio (.mcp.json passe par le conteneur app)
uv run pytest                             # tests (ffmpeg requis, pas de modèle)
uv run ruff check . && uv run ruff format --check .
cd ui && npm install && npm run build     # UI servie ensuite par `avatar serve`
cd ui && npm run dev                      # UI en dev (Vite), proxy /api vers :8787
cd ui && npm run typecheck && npm test
```

## État de l'implémentation

- Implémenté et testé (Linux, ffmpeg) : `prepare`, `segment` (passerelle simulée dans les tests),
  `assemble`, `run`, service de jobs et worker, API REST, serveur MCP (stdio), UI React (vitest et
  vérification Playwright sur un pipeline simulé), `make up` / `make down` en mode mac
  (image app construite, worker natif, MCP via `docker compose exec`).
- Écrit mais non construit ici (pas de GPU) : images `worker-gpu` et ComfyUI, mode `make up` gpu
  (configuration compose validée).
- Implémenté, à valider sur la machine cible : `voice` (Chatterbox, OmniVoice), `video --backend mac`
  (commande MuseTalk dans `config.yaml`, à ajuster à l'installation réelle), `video --backend gpu`
  (workflows ComfyUI à exporter dans `comfy_workflows/`, voir son README).
- Non implémenté : la variante tête seule (JoyVASA + LivePortrait).
