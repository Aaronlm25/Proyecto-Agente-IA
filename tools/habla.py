import os
import wave
import subprocess
import tempfile

RUTA_VOZ = os.path.join(
    os.path.dirname(__file__), "..", "voces", "es_MX-claude-high.onnx"
)


def decir(texto):
    """Convierte texto a voz con Piper y lo reproduce."""
    if not texto or not texto.strip():
        return
    if not os.path.exists(RUTA_VOZ):
        raise FileNotFoundError("No se encontró la voz en " + RUTA_VOZ)

    # Genera un archivo WAV temporal con la voz
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        ruta_wav = tmp.name

    try:
        subprocess.run(
            ["piper", "--model", RUTA_VOZ, "--output_file", ruta_wav],
            input=texto.encode("utf-8"),
            check=True,
            capture_output=True,
        )
        _reproducir(ruta_wav)
    finally:
        if os.path.exists(ruta_wav):
            os.remove(ruta_wav)


def _reproducir(ruta_wav):
    """Reproduce un archivo WAV usando el reproductor disponible en el sistema."""
    for reproductor in (["aplay", ruta_wav], ["paplay", ruta_wav]):
        try:
            subprocess.run(reproductor, check=True, capture_output=True)
            return
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    raise RuntimeError("No se encontró un reproductor de audio (aplay/paplay)")
