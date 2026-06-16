"""Herramienta de visión: leer imágenes, gráficas y diagramas.

Usa un modelo de visión de Ollama (distinto al de texto, porque qwen2.5:7b
no "ve" imágenes). Antes de usarla, instala uno:

    ollama pull qwen2.5vl:7b        # muy bueno leyendo gráficas y tablas
    ollama pull llama3.2-vision     # alternativa equilibrada
    ollama pull moondream           # ligero, para equipos modestos
"""

import os
import ollama

# Cambia esto por el modelo de visión que tengas instalado.
MODELO_VISION = "qwen2.5vl:7b"


def leer_imagen(ruta, pregunta="Describe con detalle lo que muestra esta imagen."):
    """Analiza una imagen (foto, gráfica, diagrama) y responde sobre ella.

    Sirve para describir imágenes, leer texto, interpretar gráficas o
    extraer los datos de una tabla fotografiada.
    """
    if not os.path.exists(ruta):
        return f"No encontré la imagen en la ruta: {ruta}"
    try:
        resp = ollama.chat(
            model=MODELO_VISION,
            messages=[{
                "role": "user",
                "content": pregunta,
                "images": [ruta],
            }],
        )
        return resp.message.content or "(el modelo no devolvió respuesta)"
    except Exception as e:
        return (
            f"Error al leer la imagen: {e}. "
            f"Comprueba que tienes un modelo de visión instalado: "
            f"ollama pull {MODELO_VISION}"
        )
