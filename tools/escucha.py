import os
import json
import queue
import audioop

RUTA_MODELO = os.path.join(
    os.path.dirname(__file__), "..", "modelos", "vosk-model-small-es-0.42"
)

# --- Valores a calibrar según tu micrófono y tu cuarto ---
UMBRAL_SILENCIO = 8000      # volumen por debajo del cual se considera "silencio"
SEGUNDOS_SILENCIO = 2.5    # cuánto silencio esperar antes de cortar
SEGUNDOS_MAX = 15          # límite de seguridad por si nunca hay silencio
# ----------------------------------------------------------

SAMPLERATE = 16000
BLOQUE = 4000  # muestras por bloque (~0.25 s)

_modelo = None


def _cargar_modelo():
    from vosk import Model
    global _modelo
    if _modelo is None:
        if not os.path.isdir(RUTA_MODELO):
            raise FileNotFoundError("No se encontró el modelo de voz en " + RUTA_MODELO)
        _modelo = Model(RUTA_MODELO)
    return _modelo


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
            volumen = audioop.rms(datos, 2)
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
