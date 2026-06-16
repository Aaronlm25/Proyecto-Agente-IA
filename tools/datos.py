"""Herramientas para leer tablas (CSV/Excel), analizarlas y graficarlas.

La idea sigue el mismo patrón que el resto de tools: cada función recibe
argumentos simples y devuelve un texto que el agente le muestra al usuario.

Para analizar o graficar, el propio modelo escribe el código pandas/matplotlib
en una sub-llamada enfocada y aquí lo ejecutamos de forma controlada.
"""

import os
import io
import re
import datetime
import contextlib

import pandas as pd
import matplotlib
matplotlib.use("Agg")  # sin ventana: solo genera la imagen en disco
import matplotlib.pyplot as plt


# Reutilizamos el workspace definido en filesystem.py (una sola fuente de verdad).
# Si por algún motivo no se puede importar, caemos a la ruta por defecto.
try:
    from tools.filesystem import BASE_DIR as WORKSPACE
except Exception:
    from pathlib import Path
    WORKSPACE = Path(__file__).resolve().parent.parent / "workspace"

CARPETA_GRAFICAS = os.path.join(str(WORKSPACE), "graficas")
os.makedirs(CARPETA_GRAFICAS, exist_ok=True)


# Patrones peligrosos que NO permitimos en el código generado por el modelo.
# El código generado solo debe tocar 'df', 'pd' y 'plt', nada del sistema.
PROHIBIDO = re.compile(
    r"(\bimport\s+os\b|\bimport\s+sys\b|\bimport\s+subprocess\b|\bimport\s+shutil\b"
    r"|\bopen\s*\(|\bexec\s*\(|\beval\s*\(|__import__|\bos\.|\bsys\.|subprocess"
    r"|shutil|\.remove\(|rmtree|unlink|popen|system\s*\()",
    re.IGNORECASE,
)


def _cargar(ruta):
    """Carga un CSV, TSV o Excel en un DataFrame."""
    ext = os.path.splitext(ruta)[1].lower()
    if ext in (".csv", ".tsv"):
        return pd.read_csv(ruta, sep="\t" if ext == ".tsv" else ",")
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(ruta)
    raise ValueError(f"Formato no soportado: {ext}. Usa csv, tsv, xlsx o xls.")


def _resumen(df):
    """Descripción compacta de la tabla para que el modelo la entienda."""
    return (
        f"Columnas y tipos: {dict(df.dtypes.astype(str))}\n"
        f"Número de filas: {len(df)}\n"
        f"Primeras filas:\n{df.head().to_string()}"
    )


def _limpiar(codigo):
    """Quita los ```python ... ``` que a veces añade el modelo."""
    codigo = re.sub(r"```[a-zA-Z]*", "", codigo).replace("```", "")
    return codigo.strip()


def _generar_codigo(resumen, instruccion, grafica=False):
    """Pide al modelo SOLO el código (pandas o matplotlib)."""
    import ollama
    # Importación perezosa para evitar import circular con agente.py
    try:
        import agente
        modelo = agente.MODELO
    except Exception:
        modelo = "qwen2.5:7b"

    if grafica:
        sistema = (
            "Eres un generador de código matplotlib. Responde ÚNICAMENTE con código "
            "Python, sin explicaciones ni markdown. Ya existen estas variables: 'df' "
            "(un DataFrame de pandas), 'pd' y 'plt'. Dibuja sobre la figura actual. "
            "NO llames a plt.show() ni a plt.savefig(); del guardado nos encargamos "
            "nosotros. Añade título y etiquetas a los ejes."
        )
    else:
        sistema = (
            "Eres un generador de código pandas. Responde ÚNICAMENTE con código "
            "Python, sin explicaciones ni markdown. Ya existe un DataFrame llamado "
            "'df' y el módulo 'pd'. Guarda el resultado final en una variable llamada "
            "'resultado'."
        )

    resp = ollama.chat(
        model=modelo,
        messages=[
            {"role": "system", "content": sistema},
            {"role": "user", "content": f"Estructura de la tabla:\n{resumen}\n\nTarea: {instruccion}"},
        ],
        options={"temperature": 0.1},
    )
    return _limpiar(resp.message.content or "")


def _ejecutar(codigo, df):
    """Ejecuta el código generado en un entorno acotado y devuelve el entorno."""
    if PROHIBIDO.search(codigo):
        raise ValueError("El código generado contenía operaciones no permitidas.")
    entorno = {"df": df, "pd": pd, "plt": plt}
    with contextlib.redirect_stdout(io.StringIO()) as salida:
        exec(codigo, {"__builtins__": __builtins__}, entorno)  # noqa: S102
    return entorno, salida.getvalue()


def analizar_tabla(ruta, pregunta):
    """Responde una pregunta en lenguaje natural sobre un CSV o Excel."""
    try:
        df = _cargar(ruta)
    except Exception as e:
        return f"No pude abrir la tabla: {e}"
    try:
        codigo = _generar_codigo(_resumen(df), pregunta, grafica=False)
        entorno, impreso = _ejecutar(codigo, df)
    except Exception as e:
        return f"Error al analizar la tabla: {e}"
    resultado = entorno.get("resultado")
    if resultado is None:
        return impreso.strip() or "El análisis no produjo ningún resultado."
    return str(resultado)


def graficar_tabla(ruta, peticion):
    """Crea una gráfica a partir de un CSV o Excel y la guarda como PNG."""
    try:
        df = _cargar(ruta)
    except Exception as e:
        return f"No pude abrir la tabla: {e}"
    try:
        codigo = _generar_codigo(_resumen(df), peticion, grafica=True)
        plt.figure(figsize=(8, 5))
        _ejecutar(codigo, df)
        nombre = "grafica_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".png"
        destino = os.path.join(CARPETA_GRAFICAS, nombre)
        plt.savefig(destino, bbox_inches="tight", dpi=120)
        plt.close("all")
    except Exception as e:
        plt.close("all")
        return f"Error al generar la gráfica: {e}"
    return f"Gráfica creada correctamente en: {destino}"
