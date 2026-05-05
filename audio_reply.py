import os
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg


TTS_SPEED = os.getenv("TTS_SPEED", "1.5")


def criar_audio_resposta(texto: str) -> str:
    texto_limpo = texto.replace("\n", " ").strip()
    if len(texto_limpo) > 900:
        texto_limpo = texto_limpo[:900]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as mp3_file:
        caminho_mp3 = mp3_file.name

    caminho_final = caminho_mp3.replace(".mp3", "_final.mp3")
    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()

    subprocess.run(
        ["gtts-cli", "--lang", "pt", "--tld", "com.br", "--output", caminho_mp3, texto_limpo],
        check=True,
    )

    subprocess.run(
        [ffmpeg_bin, "-y", "-i", caminho_mp3, "-filter:a", f"atempo={TTS_SPEED}", "-vn", caminho_final],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    Path(caminho_mp3).unlink(missing_ok=True)
    return caminho_final
