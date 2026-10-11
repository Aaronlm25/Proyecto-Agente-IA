"""
agentes/config.py

Configuración compartida por todos los agentes.

LOS MODELOS SE ELIGEN EN UN SOLO LUGAR: ajustes.json (en la raíz del proyecto).
    {
      "modelo": "qwen3:8b",            <- modelo de texto (root y especialistas)
      "modelo_vision": "qwen2.5vl:7b", <- modelo para leer imágenes
      "pensar": false,                 <- razonar antes de responder (más lento)
      ...
    }
Lo leen igual la interfaz (python app.py), la terminal (python main.py) y el
script de pruebas. También se cambian desde la ventana de Ajustes de la app.

Los valores de abajo son solo los de respaldo, por si ajustes.json no existe
o le falta alguna clave.
"""

import os
import json

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_AJUSTES = os.path.join(RAIZ, "ajustes.json")

# ---------- Valores de respaldo ----------

# Modelo de texto que usan el root y los especialistas.
MODELO = "qwen2.5:7b"

# Modelo de visión (para leer imágenes). Instálalo con: ollama pull qwen2.5vl:7b
MODELO_VISION = "qwen2.5vl:7b"

# Razonar antes de responder (modelos como qwen3). False = mucho más rápido,
# sobre todo sin tarjeta gráfica. None = lo que haga el modelo por defecto.
PENSAR = False

# Tamaño de contexto en tokens. Si es muy pequeño, Ollama recorta los mensajes
# más viejos SIN avisar (incluido el prompt del sistema). Súbelo si tu equipo
# tiene memoria; bájalo (p. ej. 4096) si se queda sin RAM/VRAM.
NUM_CTX = 8192

# Límites para que ningún agente se quede en un bucle infinito.
MAX_PASOS_ROOT = 10           # rondas de herramientas del root por petición
MAX_DELEGACIONES = 6          # delegaciones a especialistas por petición
MAX_PASOS_ESPECIALISTA = 8    # rondas de herramientas de cada especialista por subtarea
MAX_RESULTADO = 2000          # caracteres máximos que un especialista devuelve al root


def cargar_ajustes(ruta=None):
    """Aplica los modelos de ajustes.json sobre los valores de respaldo."""
    global MODELO, MODELO_VISION, PENSAR
    try:
        with open(ruta or RUTA_AJUSTES, encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError):
        return
    if isinstance(datos.get("modelo"), str) and datos["modelo"].strip():
        MODELO = datos["modelo"].strip()
    if isinstance(datos.get("modelo_vision"), str) and datos["modelo_vision"].strip():
        MODELO_VISION = datos["modelo_vision"].strip()
    if isinstance(datos.get("pensar"), bool):
        PENSAR = datos["pensar"]


cargar_ajustes()
