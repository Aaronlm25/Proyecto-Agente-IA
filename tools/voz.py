import os
import json
import queue

RUTA_MODELO = os.path.join(
    os.path.dirname(__file__), "..", "modelos", "vosk-model-small-es-0.42"
)

_modelo = None


def _cargar_modelo():
    from vosk import Model
    global _modelo
    if _modelo is None:
        if not os.path.isdir(RUTA_MODELO):
            raise FileNotFoundError("No se encontró el modelo de voz en " + RUTA_MODELO)
        _modelo = Model(RUTA_MODELO)
    return _modelo


class Grabadora:
    def __init__(self, samplerate=16000):
        self.samplerate = samplerate
        self.cola = queue.Queue()
        self.stream = None
        self.recognizer = None

    def _callback(self, indata, frames, tiempo, status):
        self.cola.put(bytes(indata))

    def iniciar(self):
        import sounddevice as sd
        from vosk import KaldiRecognizer
        modelo = _cargar_modelo()
        self.recognizer = KaldiRecognizer(modelo, self.samplerate)
        self.cola = queue.Queue()
        self.stream = sd.RawInputStream(
            samplerate=self.samplerate, blocksize=8000,
            dtype="int16", channels=1, callback=self._callback,
        )
        self.stream.start()

    def detener(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        partes = []
        while not self.cola.empty():
            datos = self.cola.get()
            if self.recognizer.AcceptWaveform(datos):
                res = json.loads(self.recognizer.Result())
                if res.get("text"):
                    partes.append(res["text"])
        res = json.loads(self.recognizer.FinalResult())
        if res.get("text"):
            partes.append(res["text"])
        return " ".join(partes).strip()
