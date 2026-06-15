"""
lectura.py

Lee archivos de texto para adjuntarlos al chat como contexto.
Soporta PDF (con pypdf) y texto plano.

Dependencia para PDF:  pip install pypdf
"""

import os

EXTENSIONES_TEXTO = (".txt", ".md", ".py", ".json", ".csv", ".html", ".js", ".css", ".log")


def leer_archivo(ruta):
    """Devuelve el texto legible de un archivo, o un mensaje de error."""
    ext = os.path.splitext(ruta)[1].lower()

    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            return "(Falta la librería pypdf. Instala con: pip install pypdf)"
        try:
            lector = PdfReader(ruta)
            paginas = [(p.extract_text() or "") for p in lector.pages]
            texto = "\n".join(paginas).strip()
            return texto or "(El PDF no tiene texto extraíble)"
        except Exception as e:
            return f"(No se pudo leer el PDF: {e})"

    if ext in EXTENSIONES_TEXTO:
        try:
            with open(ruta, encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            return f"(No se pudo leer el archivo: {e})"

    return f"(Tipo de archivo no soportado: {ext})"
