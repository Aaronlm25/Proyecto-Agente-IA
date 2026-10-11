"""
agentes/config.py

Configuración compartida por todos los agentes. app.py la modifica en tiempo
de ejecución cuando cambias el modelo en Ajustes.
"""

# Modelo de texto que usan el root y los especialistas.
MODELO = "qwen2.5:7b"

# Modelo de visión (para leer imágenes). Instálalo con: ollama pull qwen2.5vl:7b
MODELO_VISION = "qwen2.5vl:7b"

# Tamaño de contexto en tokens. Si es muy pequeño, Ollama recorta los mensajes
# más viejos SIN avisar (incluido el prompt del sistema). Súbelo si tu equipo
# tiene memoria; bájalo (p. ej. 4096) si se queda sin RAM/VRAM.
NUM_CTX = 8192

# Límites para que ningún agente se quede en un bucle infinito.
MAX_PASOS_ROOT = 10           # rondas de herramientas del root por petición
MAX_DELEGACIONES = 6          # delegaciones a especialistas por petición
MAX_PASOS_ESPECIALISTA = 8    # rondas de herramientas de cada especialista por subtarea
MAX_RESULTADO = 2000          # caracteres máximos que un especialista devuelve al root
