# Workflows ComfyUI (backend GPU)

Trois workflows, exportés depuis ComfyUI avec **Workflow > Export (API)** :

| Fichier | Rôle | Marqueurs utilisés |
| --- | --- | --- |
| `infinitetalk.json` | Geste libre : image + audio + prompt -> vidéo synchronisée | `{{ref_image}}`, `{{audio}}`, `{{prompt}}`, `{{seed}}` |
| `wan_animate.json` | Geste précis : Wan2.2-Animate transfère le mouvement du driver | `{{ref_image}}`, `{{driver}}`, `{{seed}}` (+ `{{prompt}}` si utile) |
| `musetalk.json` | Lip-sync de la vidéo animée sur l'audio | `{{video}}`, `{{audio}}` |

Dans le JSON exporté, remplace la valeur de chaque entrée par son marqueur, par exemple
`"image": "{{ref_image}}"` dans le nœud LoadImage, ou `"seed": "{{seed}}"` (remplacé par un entier).
Les fichiers sont envoyés dans `input/` de ComfyUI avant chaque exécution.

Chaque workflow doit se terminer par un nœud qui écrit un `.mp4` (ex. Video Combine de
VideoHelperSuite) : le CLI télécharge la première vidéo `.mp4` produite.
