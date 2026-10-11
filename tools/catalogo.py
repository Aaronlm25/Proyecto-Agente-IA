"""
tools/catalogo.py

Catálogo ÚNICO de herramientas: aquí se define cada herramienta una sola vez
(su esquema para el modelo + la función de Python que la ejecuta).

Los agentes no reciben todas: cada especialista pide solo las suyas con
herramientas_de("nombre1", "nombre2", ...).
"""

from tools import filesystem, calendario, configuracion, terminal, web, memoria, datos, vision


def _tool(nombre, descripcion, propiedades=None, requeridos=None):
    """Atajo para escribir el esquema JSON de una herramienta."""
    return {
        "type": "function",
        "function": {
            "name": nombre,
            "description": descripcion,
            "parameters": {
                "type": "object",
                "properties": propiedades or {},
                "required": requeridos or [],
            },
        },
    }


def _p(tipo, descripcion, **extra):
    return {"type": tipo, "description": descripcion, **extra}


FUNCIONES = {
    # --- archivos ---
    "crear_carpeta": filesystem.crear_carpeta,
    "crear_proyecto": filesystem.crear_proyecto,
    "buscar_archivos": filesystem.buscar_archivos,
    "generar_config": configuracion.generar_config,
    # --- organizador ---
    "crear_nota": filesystem.crear_nota,
    "crear_evento": calendario.crear_evento,
    # --- terminal ---
    "ejecutar_comando": terminal.ejecutar,
    "instalar_dependencia": terminal.instalar_dependencia,
    "git": terminal.git,
    # --- web ---
    "buscar_web": web.buscar,
    "leer_pagina": web.leer_pagina,
    # --- memoria ---
    "recordar": memoria.recordar,
    "recuperar": memoria.recuperar,
    "olvidar": memoria.olvidar,
    "listar_recuerdos": memoria.listar_recuerdos,
    # --- datos (csv/excel) ---
    "analizar_tabla": datos.analizar_tabla,
    "graficar_tabla": datos.graficar_tabla,
    # --- visión ---
    "leer_imagen": vision.leer_imagen,
}

HERRAMIENTAS = [
    # ----------------- ARCHIVOS -----------------
    _tool("crear_carpeta", "Crea una carpeta dentro del workspace.",
          {"nombre": _p("string", "Nombre o ruta relativa de la carpeta")}, ["nombre"]),
    _tool("crear_proyecto",
          "Crea un proyecto con subcarpetas (por defecto src, docs, tests) y un README.",
          {"nombre": _p("string", "Nombre del proyecto"),
           "subcarpetas": _p("array", "Lista opcional de subcarpetas", items={"type": "string"})},
          ["nombre"]),
    _tool("buscar_archivos", "Busca archivos dentro del workspace por nombre o extensión.",
          {"patron": _p("string", "Texto que debe contener el nombre"),
           "extension": _p("string", "Extensión a filtrar, ej: pdf")}),
    _tool("generar_config",
          "Genera archivos de configuración (.gitignore, .env, etc.) para un proyecto. "
          "No sobrescribe archivos existentes.",
          {"proyecto": _p("string", "Nombre del proyecto"),
           "tipo": _p("string", "Tipo de proyecto", enum=["python", "web"])},
          ["proyecto"]),
    # ----------------- ORGANIZADOR -----------------
    _tool("crear_nota", "Crea una nota en Markdown dentro de la carpeta 'notas'.",
          {"titulo": _p("string", "Título de la nota"),
           "contenido": _p("string", "Contenido de la nota en Markdown")},
          ["titulo"]),
    _tool("crear_evento", "Crea un evento de calendario en formato .ics.",
          {"titulo": _p("string", "Título del evento"),
           "fecha": _p("string", "Fecha en formato AAAA-MM-DD"),
           "hora": _p("string", "Hora de inicio en formato HH:MM (24h)"),
           "duracion_horas": _p("number", "Duración en horas (por defecto 1)")},
          ["titulo", "fecha"]),
    # ----------------- TERMINAL -----------------
    _tool("ejecutar_comando",
          "Ejecuta UN comando dentro del workspace (sin ; && | ni redirecciones). "
          "Programas permitidos: " + ", ".join(sorted(terminal.PERMITIDOS)) + ". "
          "No se permiten rutas absolutas ni '..'.",
          {"comando": _p("string", "El comando a ejecutar, ej: 'python main.py'"),
           "carpeta": _p("string", "Subcarpeta del workspace donde ejecutarlo (opcional)")},
          ["comando"]),
    _tool("instalar_dependencia", "Instala un paquete con pip o npm.",
          {"paquete": _p("string", "Nombre del paquete"),
           "gestor": _p("string", "Gestor de paquetes", enum=["pip", "npm"])},
          ["paquete"]),
    _tool("git", "Operaciones git comunes dentro de una carpeta del workspace.",
          {"accion": _p("string", "Acción git", enum=["init", "status", "add", "commit", "log"]),
           "mensaje": _p("string", "Mensaje de commit (solo para commit)"),
           "carpeta": _p("string", "Subcarpeta del repositorio (opcional)")},
          ["accion"]),
    # ----------------- WEB -----------------
    _tool("buscar_web", "Busca información actual en internet (DuckDuckGo).",
          {"consulta": _p("string", "Qué buscar"),
           "n": _p("integer", "Número de resultados (por defecto 5)")},
          ["consulta"]),
    _tool("leer_pagina", "Descarga y devuelve el texto legible de una página web.",
          {"url": _p("string", "La URL de la página")}, ["url"]),
    # ----------------- MEMORIA -----------------
    _tool("recordar",
          "Guarda un dato del usuario para recordarlo entre sesiones "
          "(nombre, gustos, proyecto en el que trabaja, etc.).",
          {"clave": _p("string", "Qué dato es, ej: 'lenguaje favorito'"),
           "valor": _p("string", "El valor del dato")},
          ["clave", "valor"]),
    _tool("recuperar", "Recupera un dato guardado del usuario por su clave.",
          {"clave": _p("string", "Qué dato recuperar")}, ["clave"]),
    _tool("olvidar", "Borra un dato guardado del usuario.",
          {"clave": _p("string", "Qué dato olvidar")}, ["clave"]),
    _tool("listar_recuerdos", "Lista todo lo que el agente recuerda del usuario."),
    # ----------------- DATOS -----------------
    _tool("analizar_tabla",
          "Responde preguntas sobre un archivo CSV o Excel "
          "(sumas, promedios, máximos, filtros, conteos, etc.).",
          {"ruta": _p("string", "Ruta del archivo csv o excel"),
           "pregunta": _p("string", "Qué se quiere saber sobre los datos")},
          ["ruta", "pregunta"]),
    _tool("graficar_tabla",
          "Crea una gráfica (barras, líneas, dispersión, etc.) a partir de un CSV o Excel "
          "y la guarda como PNG.",
          {"ruta": _p("string", "Ruta del archivo csv o excel"),
           "peticion": _p("string", "Qué gráfica se quiere, ej: 'barras de ventas por mes'")},
          ["ruta", "peticion"]),
    # ----------------- VISIÓN -----------------
    _tool("leer_imagen",
          "Analiza una imagen, gráfica o diagrama: la describe, lee su texto o extrae datos.",
          {"ruta": _p("string", "Ruta de la imagen (png, jpg, webp)"),
           "pregunta": _p("string", "Qué se quiere saber sobre la imagen")},
          ["ruta"]),
]

ESQUEMAS = {h["function"]["name"]: h for h in HERRAMIENTAS}

# Comprobación al importar: cada esquema tiene su función y viceversa.
assert set(ESQUEMAS) == set(FUNCIONES), set(ESQUEMAS) ^ set(FUNCIONES)


def herramientas_de(*nombres):
    """Devuelve (esquemas, funciones) solo con las herramientas pedidas."""
    desconocidas = [n for n in nombres if n not in FUNCIONES]
    if desconocidas:
        raise KeyError(f"Herramientas desconocidas: {desconocidas}")
    return [ESQUEMAS[n] for n in nombres], {n: FUNCIONES[n] for n in nombres}
