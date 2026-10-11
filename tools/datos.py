"""Herramientas para leer tablas (CSV/Excel), analizarlas y graficarlas.

El modelo escribe código pandas/matplotlib en una sub-llamada enfocada y aquí
lo ejecutamos de forma controlada:
  - Se analiza el código con `ast` ANTES de ejecutarlo (no con una regex).
  - Prohibido: import, nombres con doble guion bajo, open/exec/eval/getattr...,
    y los métodos de pandas que leen o escriben archivos (read_*, to_csv, ...).
  - Se ejecuta con una lista mínima de funciones integradas (sin open, sin __import__).

No es una sandbox perfecta, pero cierra los caminos obvios para tocar el sistema.
"""

import os
import io
import re
import ast
import datetime
import contextlib

import pandas as pd
import matplotlib
matplotlib.use("Agg")  # sin ventana: solo genera la imagen en disco
import matplotlib.pyplot as plt

from tools.filesystem import BASE_DIR as WORKSPACE

CARPETA_GRAFICAS = os.path.join(str(WORKSPACE), "graficas")
os.makedirs(CARPETA_GRAFICAS, exist_ok=True)

# Funciones integradas que SÍ puede usar el código generado.
BUILTINS_SEGUROS = {
    n: __builtins__[n] if isinstance(__builtins__, dict) else getattr(__builtins__, n)
    for n in (
        "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float", "int",
        "isinstance", "len", "list", "map", "max", "min", "print", "range", "round",
        "set", "sorted", "str", "sum", "tuple", "zip", "True", "False", "None",
    )
}

NOMBRES_PROHIBIDOS = {
    "open", "exec", "eval", "compile", "getattr", "setattr", "delattr", "globals",
    "locals", "vars", "input", "breakpoint", "help", "dir", "type", "object",
    "memoryview", "__import__",
}

# Métodos/atributos que leen o escriben archivos o ejecutan código.
ATRIBUTOS_PROHIBIDOS = re.compile(
    r"^(read_\w+|to_(?!string$|dict$|list$|numpy$|frame$|period$|timestamp$|datetime$|numeric$|timedelta$)\w+"
    r"|savefig|save|eval|query|pipe|system|popen|remove|unlink|rmtree|write\w*|load\w*)$"
)


def _validar_codigo(codigo: str) -> None:
    """Lanza ValueError si el código usa algo no permitido."""
    try:
        arbol = ast.parse(codigo)
    except SyntaxError as e:
        raise ValueError(f"El código generado no es Python válido: {e}")
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Import, ast.ImportFrom)):
            raise ValueError("El código generado intentó importar módulos (no permitido).")
        if isinstance(nodo, (ast.Global, ast.Nonlocal)):
            raise ValueError("Uso de global/nonlocal no permitido.")
        if isinstance(nodo, ast.Name) and (nodo.id in NOMBRES_PROHIBIDOS or nodo.id.startswith("__")):
            raise ValueError(f"Uso no permitido de '{nodo.id}'.")
        if isinstance(nodo, ast.Attribute):
            if nodo.attr.startswith("_") or ATRIBUTOS_PROHIBIDOS.match(nodo.attr):
                raise ValueError(f"Uso no permitido de '.{nodo.attr}'.")
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and "__" in nodo.value:
            raise ValueError("Cadenas con '__' no permitidas.")


def _cargar(ruta):
    """Carga un CSV, TSV o Excel en un DataFrame."""
    if not os.path.exists(ruta):
        # Permitimos rutas relativas al workspace (ej: 'ventas.csv').
        candidato = os.path.join(str(WORKSPACE), ruta)
        if os.path.exists(candidato):
            ruta = candidato
        else:
            raise FileNotFoundError(f"No existe el archivo: {ruta}")
    ext = os.path.splitext(ruta)[1].lower()
    if ext in (".csv", ".tsv"):
        return pd.read_csv(ruta, sep="\t" if ext == ".tsv" else None, engine="python")
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
    bloque = re.search(r"```(?:[a-zA-Z]*)\n(.*?)```", codigo, re.S)
    if bloque:
        codigo = bloque.group(1)
    return codigo.replace("```", "").strip()


def _generar_codigo(resumen, instruccion, grafica=False):
    """Pide al modelo SOLO el código (pandas o matplotlib)."""
    from agentes import config, modelo

    if grafica:
        sistema = (
            "Eres un generador de código matplotlib. Responde ÚNICAMENTE con código "
            "Python, sin explicaciones ni markdown. Ya existen estas variables: 'df' "
            "(un DataFrame de pandas), 'pd' y 'plt'. NO uses import. Dibuja sobre la "
            "figura actual. NO uses df.query ni df.eval. NO llames a plt.show() ni a plt.savefig(). "
            "Añade título y etiquetas a los ejes."
        )
    else:
        sistema = (
            "Eres un generador de código pandas. Responde ÚNICAMENTE con código "
            "Python, sin explicaciones ni markdown. Ya existe un DataFrame llamado "
            "'df' y el módulo 'pd'. NO uses import, ni df.query ni df.eval (usa filtros con corchetes). Guarda el resultado final en una "
            "variable llamada 'resultado'."
        )

    resp = modelo.chat(
        model=config.MODELO,
        messages=[
            {"role": "system", "content": sistema},
            {"role": "user", "content": f"Estructura de la tabla:\n{resumen}\n\nTarea: {instruccion}"},
        ],
        options={"temperature": 0.1, "num_ctx": config.NUM_CTX},
    )
    return _limpiar(resp.message.content or "")


def _ejecutar(codigo, df):
    """Valida y ejecuta el código generado. Devuelve (entorno, texto_impreso)."""
    _validar_codigo(codigo)
    entorno = {"df": df, "pd": pd, "plt": plt}
    with contextlib.redirect_stdout(io.StringIO()) as salida:
        exec(codigo, {"__builtins__": BUILTINS_SEGUROS}, entorno)  # noqa: S102
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
    texto = resultado.to_string() if hasattr(resultado, "to_string") else str(resultado)
    return texto[:3000]


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
        nombre = "grafica_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".png"
        destino = os.path.join(CARPETA_GRAFICAS, nombre)
        os.makedirs(CARPETA_GRAFICAS, exist_ok=True)  # por si la borraron
        plt.savefig(destino, bbox_inches="tight", dpi=120)
    except Exception as e:
        return f"Error al generar la gráfica: {e}"
    finally:
        plt.close("all")
    return f"Gráfica creada correctamente en: {destino}"
