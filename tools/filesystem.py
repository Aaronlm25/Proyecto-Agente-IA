from pathlib import Path

# Carpeta raíz donde el agente puede trabajar. NUNCA escribe fuera de aquí.
BASE_DIR = Path(__file__).resolve().parent.parent / "workspace"


def _ruta_segura(nombre: str) -> Path:
    """Evita que el agente escriba fuera de BASE_DIR (seguridad)."""
    destino = (BASE_DIR / nombre).resolve()
    if not str(destino).startswith(str(BASE_DIR.resolve())):
        raise ValueError("Ruta no permitida fuera del workspace")
    return destino


def crear_carpeta(nombre: str) -> str:
    ruta = _ruta_segura(nombre)
    ruta.mkdir(parents=True, exist_ok=True)
    return f"Carpeta creada: {ruta}"


def crear_proyecto(nombre: str, subcarpetas: list | None = None) -> str:
    if subcarpetas is None:
        subcarpetas = ["src", "docs", "tests"]
    base = _ruta_segura(nombre)
    base.mkdir(parents=True, exist_ok=True)
    for sub in subcarpetas:
        (base / sub).mkdir(parents=True, exist_ok=True)
    (base / "README.md").write_text(f"# {nombre}\n\nProyecto creado por el agente de IA.\n")
    return f"Proyecto '{nombre}' creado con subcarpetas: {', '.join(subcarpetas)}"


def crear_nota(titulo: str, contenido: str = "") -> str:
    notas = _ruta_segura("notas")
    notas.mkdir(parents=True, exist_ok=True)
    archivo = notas / f"{titulo}.md"
    archivo.write_text(f"# {titulo}\n\n{contenido}\n")
    return f"Nota creada: {archivo}"


def buscar_archivos(patron: str = "", extension: str = "") -> str:
    """Busca archivos dentro del workspace.
    patron: texto que debe contener el nombre (ej: 'vacaciones').
    extension: filtra por extensión (ej: 'pdf'). Vacío = todas."""
    if not BASE_DIR.exists():
        return "El workspace está vacío (aún no se ha creado nada)."
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
    return "Archivos encontrados:\n" + "\n".join(f"- {a}" for a in encontrados)
