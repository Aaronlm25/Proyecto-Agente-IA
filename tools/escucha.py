import json
import queue

import numpy as np

# Reutilizamos el MISMO modelo cargado por voz.py (antes se cargaba dos veces).
from tools.voz import _cargar_modelo

# --- Valores a calibrar según tu micrófono y tu cuarto ---
UMBRAL_SILENCIO = 8000      # volumen por debajo del cual se considera "silencio"
SEGUNDOS_SILENCIO = 2.5    # cuánto silencio esperar antes de cortar
SEGUNDOS_MAX = 15          # límite de seguridad por si nunca hay silencio
# ----------------------------------------------------------

SAMPLERATE = 16000
BLOQUE = 4000  # muestras por bloque (~0.25 s)


def _volumen(datos: bytes) -> float:
    """Volumen RMS de un bloque de audio int16 (reemplaza a audioop, que ya no existe en Python 3.13)."""
    muestras = np.frombuffer(datos, dtype=np.int16).astype(np.float64)
    return float(np.sqrt(np.mean(muestras ** 2))) if muestras.size else 0.0


def escuchar_una_frase(parar):
    """Escucha hasta detectar silencio y devuelve el texto reconocido.
    'parar' es una función que devuelve True si hay que abortar (salir del modo)."""
    import sounddevice as sd
    from vosk import KaldiRecognizer

    modelo = _cargar_modelo()
    rec = KaldiRecognizer(modelo, SAMPLERATE)
    cola = queue.Queue()

    def callback(indata, frames, tiempo, status):
        cola.put(bytes(indata))

    bloques_silencio = 0
    bloques_max = int(SEGUNDOS_MAX * SAMPLERATE / BLOQUE)
    bloques_para_cortar = int(SEGUNDOS_SILENCIO * SAMPLERATE / BLOQUE)
    hubo_voz = False
    contados = 0

    with sd.RawInputStream(samplerate=SAMPLERATE, blocksize=BLOQUE,
                           dtype="int16", channels=1, callback=callback):
        while True:
            if parar():
                return None
            try:
                datos = cola.get(timeout=0.5)
            except queue.Empty:
                continue

            rec.AcceptWaveform(datos)
            contados += 1

            # Mide el volumen del bloque
            volumen = _volumen(datos)
            if volumen >= UMBRAL_SILENCIO:
                hubo_voz = True
                bloques_silencio = 0
            else:
                bloques_silencio += 1

            # Corta si ya hubo voz y luego suficiente silencio
            if hubo_voz and bloques_silencio >= bloques_para_cortar:
                break
            # Corta por límite de seguridad
            if contados >= bloques_max:
                break

    res = json.loads(rec.FinalResult())
    return res.get("text", "").strip()
