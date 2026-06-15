"""
tools/web.py

Busqueda web y lectura de paginas, sin API de pago.

Dependencias:
    pip install ddgs requests

Devuelve STRINGS para encajar con agente.py.
"""

import re
import html

import requests

CABECERAS = {"User-Agent": "Mozilla/5.0 (agente-local)"}


def buscar(consulta, n=5):
    """Busca en la web y devuelve los primeros resultados (titulo, snippet, url)."""
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # nombre antiguo del paquete
        except ImportError:
            return "Falta la libreria de busqueda. Instala con: pip install ddgs"

    try:
        with DDGS() as ddgs:
            resultados = list(ddgs.text(consulta, max_results=n))
    except Exception as e:
        return f"Error en la busqueda: {e}"

    if not resultados:
        return f"Sin resultados para '{consulta}'."

    lineas = []
    for i, r in enumerate(resultados, 1):
        titulo = r.get("title", "(sin titulo)")
        cuerpo = r.get("body", "")
        url = r.get("href", "")
        lineas.append(f"{i}. {titulo}\n   {cuerpo}\n   {url}")
    return "\n".join(lineas)


def leer_pagina(url, max_caracteres=3000):
    """Descarga una pagina y devuelve su texto legible (sin etiquetas HTML)."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        resp = requests.get(url, headers=CABECERAS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return f"No se pudo abrir la pagina: {e}"

    htmltexto = resp.text
    # Quita script/style y luego todas las etiquetas
    htmltexto = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", htmltexto, flags=re.S | re.I)
    texto = re.sub(r"<[^>]+>", " ", htmltexto)
    texto = html.unescape(texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    if not texto:
        return "La pagina no tiene texto legible."
    if len(texto) > max_caracteres:
        texto = texto[:max_caracteres] + " ... (recortado)"
    return texto
