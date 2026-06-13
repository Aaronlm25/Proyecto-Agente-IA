from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent / "workspace"

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
    if tipo not in PLANTILLAS:
        return f"Tipo desconocido '{tipo}'. Disponibles: {', '.join(PLANTILLAS)}"

    base = (BASE_DIR / proyecto).resolve()
    base.mkdir(parents=True, exist_ok=True)

    creados = []
    for nombre, contenido in PLANTILLAS[tipo].items():
        (base / nombre).write_text(contenido)
        creados.append(nombre)

    return f"Configuración '{tipo}' generada en '{proyecto}': {', '.join(creados)}"
