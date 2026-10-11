"""Herramienta de visión: leer imágenes, gráficas y diagramas.

Usa un modelo de visión de Ollama (distinto al de texto, porque qwen2.5:7b
no "ve" imágenes). Antes de usarla, instala uno:

    ollama pull qwen2.5vl:7b        # muy bueno leyendo gráficas y tablas
    ollama pull llama3.2-vision     # alternativa equilibrada
    ollama pull moondream           # ligero, para equipos modestos

El modelo se configura en agentes/config.py (MODELO_VISION).
"""

import os
import ollama

from tools.filesystem import BASE_DIR

EXTENSIONES = (".png", ".jpg", ".jpeg", ".webp")


def leer_imagen(ruta, pregunta="Describe con detalle lo que muestra esta imagen."):
    """Analiza una imagen (foto, gráfica, diagrama) y responde sobre ella."""
    from agentes import config

    if not os.path.exists(ruta):
        candidato = os.path.join(str(BASE_DIR), ruta)  # ruta relativa al workspace
        if os.path.exists(candidato):
            ruta = candidato
        else:
            return f"No encontré la imagen en la ruta: {ruta}"
    if not ruta.lower().endswith(EXTENSIONES):
        return f"Formato de imagen no soportado. Usa: {', '.join(EXTENSIONES)}"
    try:
        resp = ollama.chat(
            model=config.MODELO_VISION,
            messages=[{"role": "user", "content": pregunta or "Describe la imagen.", "images": [ruta]}],
        )
        return resp.message.content or "(el modelo no devolvió respuesta)"
    except Exception as e:
        return (
            f"Error al leer la imagen: {e}. "
            f"Comprueba que tienes un modelo de visión instalado: "
            f"ollama pull {config.MODELO_VISION}"
        )
