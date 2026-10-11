"""
tools/filesystem.py

Crear carpetas, proyectos y notas, y buscar archivos.
TODO lo que se escribe pasa por ruta_segura(): nada puede salir de workspace/.
"""

import os
import re
from pathlib import Path

# Carpeta raíz donde el agente puede trabajar. NUNCA escribe fuera de aquí.
# Se puede cambiar con la variable de entorno AGENTE_WORKSPACE (las pruebas la usan).
_POR_DEFECTO = Path(__file__).resolve().parent.parent / "workspace"
BASE_DIR = Path(os.environ.get("AGENTE_WORKSPACE", _POR_DEFECTO)).resolve()
BASE_DIR.mkdir(parents=True, exist_ok=True)


def ruta_segura(nombre) -> Path:
    """Devuelve una ruta dentro de BASE_DIR o lanza ValueError si intenta salir.

    Usa is_relative_to (no startswith), así '../workspace_otro' también se bloquea.
    """
    destino = (BASE_DIR / str(nombre)).resolve()
    if destino != BASE_DIR and not destino.is_relative_to(BASE_DIR):
        raise ValueError(f"Ruta no permitida fuera del workspace: {nombre}")
    return destino


# Alias para no romper código que use el nombre anterior.
_ruta_segura = ruta_segura


def nombre_archivo_seguro(texto: str, maximo: int = 80) -> str:
    """Convierte un título en un nombre de archivo válido (sin / \\ : * ? etc.)."""
    limpio = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", str(texto)).strip().strip(".")
    limpio = re.sub(r"\s+", "_", limpio)
    return (limpio[:maximo] or "sin_titulo")


def crear_carpeta(nombre: str) -> str:
    ruta = ruta_segura(nombre)
    ruta.mkdir(parents=True, exist_ok=True)
    return f"Carpeta creada: {ruta.relative_to(BASE_DIR)}"


def crear_proyecto(nombre: str, subcarpetas: list | None = None) -> str:
    if not subcarpetas:
        subcarpetas = ["src", "docs", "tests"]
    base = ruta_segura(nombre)
    # Validamos TODAS las subcarpetas antes de crear nada.
    rutas = [ruta_segura(Path(nombre) / sub) for sub in subcarpetas]
    base.mkdir(parents=True, exist_ok=True)
    for r in rutas:
        r.mkdir(parents=True, exist_ok=True)
    readme = base / "README.md"
    if not readme.exists():
        readme.write_text(f"# {nombre}\n\nProyecto creado por el agente de IA.\n", encoding="utf-8")
    return (f"Proyecto '{nombre}' creado en {base.relative_to(BASE_DIR)} "
            f"con subcarpetas: {', '.join(subcarpetas)}")


def crear_nota(titulo: str, contenido: str = "") -> str:
    archivo = ruta_segura(Path("notas") / f"{nombre_archivo_seguro(titulo)}.md")
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(f"# {titulo}\n\n{contenido}\n", encoding="utf-8")
    return f"Nota creada: {archivo.relative_to(BASE_DIR)}"


def buscar_archivos(patron: str = "", extension: str = "") -> str:
    """Busca archivos dentro del workspace.
    patron: texto que debe contener el nombre (ej: 'vacaciones').
    extension: filtra por extensión (ej: 'pdf'). Vacío = todas."""
    encontrados = []
    for ruta in BASE_DIR.rglob("*"):
        if ruta.is_file():
            nombre = ruta.name
            ok_patron = not patron or patron.lower() in nombre.lower()
            ok_ext = not extension or nombre.lower().endswith("." + extension.lower().lstrip("."))
            if ok_patron and ok_ext:
                encontrados.append(str(ruta.relative_to(BASE_DIR)))
    if not encontrados:
        return "No se encontraron archivos que coincidan."
    encontrados.sort()
    extra = f"\n... y {len(encontrados) - 50} más" if len(encontrados) > 50 else ""
    return "Archivos encontrados:\n" + "\n".join(f"- {a}" for a in encontrados[:50]) + extra
