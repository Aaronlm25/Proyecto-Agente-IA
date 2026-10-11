"""
tools/configuracion.py

Genera archivos de configuración base para un proyecto.
Nunca sobrescribe archivos que ya existen (para no borrar tu .env, etc.).
"""

from tools.filesystem import ruta_segura, BASE_DIR

PLANTILLAS = {
    "python": {
        ".gitignore": "__pycache__/\n*.pyc\n.env\nvenv/\n",
        "requirements.txt": "",
        ".env": "# Variables de entorno\n",
    },
    "web": {
        ".gitignore": "node_modules/\ndist/\n.env\n",
        "index.html": "<!DOCTYPE html>\n<html><head><title>Proyecto</title></head><body></body></html>\n",
    },
}


def generar_config(proyecto: str, tipo: str = "python") -> str:
    """Genera archivos de configuración para un proyecto según su tipo (python o web)."""
    tipo = (tipo or "python").lower().strip()
    if tipo not in PLANTILLAS:
        return f"Tipo desconocido '{tipo}'. Disponibles: {', '.join(PLANTILLAS)}"

    base = ruta_segura(proyecto)
    base.mkdir(parents=True, exist_ok=True)

    creados, omitidos = [], []
    for nombre, contenido in PLANTILLAS[tipo].items():
        destino = ruta_segura(base.relative_to(BASE_DIR) / nombre)
        if destino.exists():
            omitidos.append(nombre)
            continue
        destino.write_text(contenido, encoding="utf-8")
        creados.append(nombre)

    msg = f"Configuración '{tipo}' en '{base.relative_to(BASE_DIR)}'."
    if creados:
        msg += f" Creados: {', '.join(creados)}."
    if omitidos:
        msg += f" Ya existían (no se tocaron): {', '.join(omitidos)}."
    return msg
