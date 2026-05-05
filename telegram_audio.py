import os
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
from faster_whisper import WhisperModel
from gtts import gTTS

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "tiny")
TTS_SPEED = os.getenv("TTS_SPEED", "1.5")
_whisper_model = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _whisper_model


def transcrever_audio(caminho_audio: str) -> str:
    model = get_whisper_model()
    segments, _ = model.transcribe(
        caminho_audio,
        language="pt",
        beam_size=1,
        vad_filter=True,
    )
    texto = " ".join(segment.text.strip() for segment in segments).strip()
    if not texto:
        raise RuntimeError("Nao consegui entender o audio.")
    return texto


def gerar_audio_resposta(texto: str) -> str:
    texto_limpo = texto.replace("\n", " ").strip()
    if len(texto_limpo) > 700:
        texto_limpo = texto_limpo[:700]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as mp3_file:
        caminho_mp3 = mp3_file.name

    caminho_ogg = caminho_mp3.replace(".mp3", ".ogg")

    tts = gTTS(text=texto_limpo, lang="pt", slow=False, tld="com.br")
    tts.save(caminho_mp3)

    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-i",
            caminho_mp3,
            "-filter:a",
            f"atempo={TTS_SPEED}",
            "-c:a",
            "libopus",
            caminho_ogg,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    Path(caminho_mp3).unlink(missing_ok=True)
    return caminho_ogg
