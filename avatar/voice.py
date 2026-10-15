from collections.abc import Callable
from pathlib import Path

from avatar.config import Config
from avatar.segment import load

# (texte, chemin de sortie) -> écrit un .wav
Synth = Callable[[str, Path], None]


def chatterbox(ref_wav: Path, language: str, device: str) -> Synth:
    import torchaudio
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    model = ChatterboxMultilingualTTS.from_pretrained(device=device)

    def synth(text: str, out: Path) -> None:
        wav = model.generate(text, language_id=language, audio_prompt_path=str(ref_wav))
        torchaudio.save(str(out), wav, model.sr)

    return synth


def omnivoice(ref_wav: Path, language: str, device: str) -> Synth:
    # API d'après le README de k2-fsa/OmniVoice, à vérifier à l'installation.
    # OmniVoice conseille 3 à 10 s de référence : raccourcir ref.wav si le clonage dérive.
    import torch
    import torchaudio
    from omnivoice import OmniVoice

    model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map=device)

    def synth(text: str, out: Path) -> None:
        audio = model.generate(text=text, ref_audio=str(ref_wav))
        if isinstance(audio, list):
            audio = audio[0]
        audio = torch.as_tensor(audio).float()
        torchaudio.save(str(out), audio.reshape(1, -1).cpu(), 24000)

    return synth


ENGINES = {"chatterbox": chatterbox, "omnivoice": omnivoice}


def load_engine(cfg: Config) -> Synth:
    v = cfg["voice"]
    return ENGINES[v["engine"]](cfg.path("ref_wav"), cfg["language"], v["device"])


def voice(cfg: Config, video_id: str, synth: Synth | None = None) -> None:
    work = cfg.work_dir(video_id)
    synth = synth or load_engine(cfg)
    for s in load(work / "segments.json"):
        synth(s.text, work / f"seg_{s.id}.wav")
