"""
agentes/modelo.py

Punto único para hablar con Ollama. Añade a cada llamada la opción de
"razonamiento" (think) según ajustes.json:

    "pensar": false  -> respuestas mucho más rápidas (recomendado sin GPU)
    "pensar": true   -> el modelo razona antes de responder (más lento)

Modelos como qwen3 razonan por defecto; otros (qwen2.5, llama3.1...) no
admiten la opción. Si un modelo la rechaza, se vuelve a llamar sin ella y
se recuerda para no intentarlo de nuevo.
"""

import ollama

import registro
from agentes import config

_SIN_THINK = set()   # modelos que no aceptan la opción think


def _encadenar(primero, resto):
    yield primero
    yield from resto


def chat(**kwargs):
    """Igual que ollama.chat(...), pero aplicando el ajuste de razonamiento."""
    modelo = kwargs.get("model")
    pensar = config.PENSAR
    if pensar is None or modelo in _SIN_THINK:
        return ollama.chat(**kwargs)
    try:
        if kwargs.get("stream"):
            # En streaming el error llega al pedir el primer fragmento.
            generador = iter(ollama.chat(**kwargs, think=pensar))
            try:
                primero = next(generador)
            except StopIteration:
                return iter([])
            return _encadenar(primero, generador)
        return ollama.chat(**kwargs, think=pensar)
    except Exception as e:
        if "think" not in str(e).lower():
            raise
        _SIN_THINK.add(modelo)
        registro.info(f"El modelo {modelo} no admite la opción 'pensar'; se usa sin ella.")
        return ollama.chat(**kwargs)
