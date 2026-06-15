import json
import os
import datetime
import ollama
import registro
from tools import filesystem, calendario, configuracion, terminal, web, memoria

MODELO = "qwen2.5:7b"

# Carpeta donde se guarda cada conversación por separado.
CARPETA_CHATS = os.path.join(os.path.dirname(__file__), "chats")
os.makedirs(CARPETA_CHATS, exist_ok=True)
MAX_TURNOS = 40

# Herramientas que piden confirmación al usuario antes de ejecutarse.
REQUIEREN_CONFIRMACION = {"ejecutar_comando", "instalar_dependencia", "git"}

MENSAJE_SISTEMA = {
    "role": "system",
    "content": (
        "Eres un asistente que automatiza tareas en la computadora del usuario "
        "usando las herramientas disponibles. Cuando el usuario pida crear o buscar algo, "
        "usa la herramienta adecuada. Si necesitas información actual o reciente, usa "
        "buscar_web. Si el usuario menciona un dato personal importante (su nombre, gustos, "
        "proyectos), guárdalo con recordar. Las fechas van en formato AAAA-MM-DD y las "
        "horas en formato HH:MM de 24 horas. Responde siempre en español."
    ),
}

FUNCIONES = {
    "crear_carpeta": filesystem.crear_carpeta,
    "crear_proyecto": filesystem.crear_proyecto,
    "crear_nota": filesystem.crear_nota,
    "buscar_archivos": filesystem.buscar_archivos,
    "crear_evento": calendario.crear_evento,
    "generar_config": configuracion.generar_config,
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
    "listar_recuerdos": memoria.listar_recuerdos,
}

HERRAMIENTAS = [
    {
        "type": "function",
        "function": {
            "name": "crear_carpeta",
            "description": "Crea una carpeta dentro del workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string", "description": "Nombre o ruta de la carpeta"}
                },
                "required": ["nombre"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crear_proyecto",
            "description": "Crea un proyecto con subcarpetas estándar (src, docs, tests) y un README.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string", "description": "Nombre del proyecto"},
                    "subcarpetas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista opcional de subcarpetas",
                    },
                },
                "required": ["nombre"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crear_nota",
            "description": "Crea una nota en Markdown dentro de la carpeta 'notas'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string", "description": "Título de la nota"},
                    "contenido": {"type": "string", "description": "Contenido de la nota"},
                },
                "required": ["titulo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_archivos",
            "description": "Busca archivos dentro del workspace por nombre o extensión.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patron": {"type": "string", "description": "Texto que debe contener el nombre"},
                    "extension": {"type": "string", "description": "Extensión a filtrar, ej: pdf"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crear_evento",
            "description": "Crea un evento de calendario en formato .ics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string", "description": "Título del evento"},
                    "fecha": {"type": "string", "description": "Fecha en formato AAAA-MM-DD"},
                    "hora": {"type": "string", "description": "Hora en formato HH:MM (24h)"},
                    "duracion_horas": {"type": "integer", "description": "Duración en horas"},
                },
                "required": ["titulo", "fecha"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generar_config",
            "description": "Genera archivos de configuración para un proyecto (tipo 'python' o 'web').",
            "parameters": {
                "type": "object",
                "properties": {
                    "proyecto": {"type": "string", "description": "Nombre del proyecto"},
                    "tipo": {"type": "string", "description": "Tipo: python o web"},
                },
                "required": ["proyecto"],
            },
        },
    },
    # ----------------- TERMINAL -----------------
    {
        "type": "function",
        "function": {
            "name": "ejecutar_comando",
            "description": (
                "Ejecuta un comando de shell dentro del workspace. Úsalo para correr "
                "proyectos, listar archivos, mover cosas, etc. No se permiten comandos destructivos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "comando": {"type": "string", "description": "El comando a ejecutar"},
                    "carpeta": {"type": "string", "description": "Subcarpeta opcional donde ejecutarlo"},
                },
                "required": ["comando"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "instalar_dependencia",
            "description": "Instala un paquete con pip, npm o apt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "paquete": {"type": "string", "description": "Nombre del paquete"},
                    "gestor": {"type": "string", "description": "pip, npm o apt (por defecto pip)"},
                },
                "required": ["paquete"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git",
            "description": "Operaciones git comunes: init, status, add, commit, log.",
            "parameters": {
                "type": "object",
                "properties": {
                    "accion": {"type": "string", "description": "init, status, add, commit o log"},
                    "mensaje": {"type": "string", "description": "Mensaje de commit (solo para commit)"},
                    "carpeta": {"type": "string", "description": "Subcarpeta del repositorio (opcional)"},
                },
                "required": ["accion"],
            },
        },
    },
    # ----------------- WEB -----------------
    {
        "type": "function",
        "function": {
            "name": "buscar_web",
            "description": (
                "Busca información actual en internet. Úsalo cuando no sepas algo, "
                "sea reciente, o necesites datos del mundo real."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "consulta": {"type": "string", "description": "Qué buscar"},
                    "n": {"type": "integer", "description": "Número de resultados (por defecto 5)"},
                },
                "required": ["consulta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "leer_pagina",
            "description": "Descarga y devuelve el texto legible de una página web a partir de su URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "La URL de la página"},
                },
                "required": ["url"],
            },
        },
    },
    # ----------------- MEMORIA -----------------
    {
        "type": "function",
        "function": {
            "name": "recordar",
            "description": (
                "Guarda un dato del usuario para recordarlo siempre entre sesiones "
                "(nombre, gustos, proyecto en el que trabaja, etc.)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "clave": {"type": "string", "description": "Qué dato es, ej: 'lenguaje favorito'"},
                    "valor": {"type": "string", "description": "El valor del dato"},
                },
                "required": ["clave", "valor"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recuperar",
            "description": "Recupera un dato guardado del usuario por su clave.",
            "parameters": {
                "type": "object",
                "properties": {
                    "clave": {"type": "string", "description": "Qué dato recuperar"},
                },
                "required": ["clave"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listar_recuerdos",
            "description": "Lista todo lo que el agente recuerda del usuario.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def _generar_plan(mensajes):
    """Pide al modelo (sin herramientas) que describa los pasos que dará."""
    nudge = {
        "role": "user",
        "content": ("Antes de hacer nada, describe en una lista numerada y breve "
                    "(máximo 6 pasos) lo que vas a hacer para cumplir mi última petición. "
                    "Solo el plan, no ejecutes ninguna herramienta todavía."),
    }
    try:
        resp = ollama.chat(model=MODELO, messages=mensajes + [nudge])
        return resp.message.content or "(sin plan)"
    except Exception as e:
        registro.error(f"Error al generar el plan: {e}")
        return f"(No se pudo generar el plan: {e})"


def procesar(peticion, mensajes, confirmador=None, on_token=None, on_accion=None,
             cancelado=None, planificador=None):
    """Procesa una petición con streaming, confirmación y registro.

    - confirmador(nombre, args) -> bool: confirma herramientas sensibles.
    - on_token(texto): fragmento de texto generado por el modelo.
    - on_accion(linea): cada vez que se ejecuta una herramienta.
    - cancelado() -> bool: si devuelve True, se detiene la generación.
    - planificador(plan) -> bool: si se pasa (modo plan), primero genera un plan;
      si el usuario no lo aprueba, devuelve el plan sin ejecutar nada.

    Devuelve (texto_respuesta, lista_de_acciones)."""
    mensajes.append({"role": "user", "content": peticion})
    acciones = []

    # Modo plan: generar y pedir aprobación antes de actuar.
    if planificador is not None:
        plan = _generar_plan(mensajes)
        if not planificador(plan):
            mensajes.append({"role": "assistant", "content": plan})
            return plan, acciones

    while True:
        contenido = ""
        tool_calls = []
        cancelado_flag = False
        try:
            for parte in ollama.chat(model=MODELO, messages=mensajes,
                                     tools=HERRAMIENTAS, stream=True):
                if cancelado and cancelado():
                    cancelado_flag = True
                    break
                msg = parte.message
                if getattr(msg, "content", None):
                    contenido += msg.content
                    if on_token:
                        on_token(msg.content)
                if getattr(msg, "tool_calls", None):
                    tool_calls.extend(msg.tool_calls)
        except Exception as e:
            registro.error(f"Error al contactar el modelo: {e}")
            return f"Error al contactar el modelo: {e}", acciones

        # Reconstruimos el mensaje del asistente para el historial.
        msg_asistente = {"role": "assistant", "content": contenido}
        if tool_calls and not cancelado_flag:
            msg_asistente["tool_calls"] = [
                {"function": {"name": t.function.name, "arguments": t.function.arguments}}
                for t in tool_calls
            ]
        mensajes.append(msg_asistente)

        if cancelado_flag:
            return contenido or "(generación detenida)", acciones

        if not tool_calls:
            return contenido, acciones

        for llamada in tool_calls:
            if cancelado and cancelado():
                return contenido or "(generación detenida)", acciones
            nombre = llamada.function.name
            argumentos = llamada.function.arguments

            # Confirmación para herramientas sensibles.
            if confirmador and nombre in REQUIEREN_CONFIRMACION:
                if not confirmador(nombre, argumentos):
                    resultado = f"Acción '{nombre}' cancelada por el usuario."
                    registro.accion(f"CANCELADA {nombre}({argumentos})")
                    linea = f"{nombre}({argumentos}) -> {resultado}"
                    acciones.append(linea)
                    if on_accion:
                        on_accion(linea)
                    mensajes.append({"role": "tool", "content": resultado})
                    continue

            funcion = FUNCIONES.get(nombre)
            if funcion is None:
                resultado = f"Error: herramienta desconocida '{nombre}'"
                registro.error(resultado)
            else:
                try:
                    resultado = funcion(**argumentos)
                except Exception as e:
                    resultado = f"Error al ejecutar {nombre}: {e}"
                    registro.error(f"{nombre}({argumentos}): {e}")
            resultado = str(resultado)
            registro.accion(f"{nombre}({argumentos}) -> {resultado[:200]}")

            linea = f"{nombre}({argumentos}) -> {resultado}"
            acciones.append(linea)
            if on_accion:
                on_accion(linea)
            mensajes.append({"role": "tool", "content": resultado})


def _turno_serializable(m):
    """Convierte un mensaje (dict u objeto de ollama) a un turno guardable."""
    if isinstance(m, dict):
        role, contenido = m.get("role"), m.get("content")
    else:
        role, contenido = getattr(m, "role", None), getattr(m, "content", None)
    if role in ("user", "assistant") and contenido:
        return {"role": role, "content": contenido}
    return None


def _mensaje_sistema():
    """Mensaje de sistema con los recuerdos del usuario inyectados."""
    sistema = dict(MENSAJE_SISTEMA)
    try:
        contexto = memoria.contexto_memoria()
        if contexto:
            sistema["content"] += " " + contexto
    except Exception:
        pass
    return sistema


# ----------------- GESTIÓN DE CHATS -----------------

def _ruta_chat(chat_id):
    return os.path.join(CARPETA_CHATS, f"{chat_id}.json")


def crear_chat():
    """Crea un chat nuevo vacío y devuelve su id."""
    chat_id = "chat_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    ahora = datetime.datetime.now().isoformat()
    datos = {"titulo": "Nuevo chat", "creado": ahora, "actualizado": ahora, "turnos": []}
    with open(_ruta_chat(chat_id), "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    return chat_id


def listar_chats():
    """Devuelve [{id, titulo, actualizado}] del más reciente al más viejo."""
    chats = []
    if not os.path.isdir(CARPETA_CHATS):
        return chats
    for nombre in os.listdir(CARPETA_CHATS):
        if not nombre.endswith(".json"):
            continue
        chat_id = nombre[:-5]
        try:
            with open(os.path.join(CARPETA_CHATS, nombre), encoding="utf-8") as f:
                datos = json.load(f)
            chats.append({
                "id": chat_id,
                "titulo": datos.get("titulo", "Chat"),
                "actualizado": datos.get("actualizado", datos.get("creado", "")),
            })
        except Exception:
            pass
    chats.sort(key=lambda c: c["actualizado"], reverse=True)
    return chats


def cargar_chat(chat_id):
    """Devuelve los mensajes de un chat: sistema (con recuerdos) + turnos."""
    mensajes = [_mensaje_sistema()]
    ruta = _ruta_chat(chat_id)
    if os.path.exists(ruta):
        try:
            with open(ruta, encoding="utf-8") as f:
                datos = json.load(f)
            mensajes.extend(datos.get("turnos", [])[-MAX_TURNOS:])
        except Exception:
            pass
    return mensajes


def guardar_chat(chat_id, mensajes):
    """Guarda los turnos de texto del chat y actualiza título y fecha."""
    turnos = [t for t in (_turno_serializable(m) for m in mensajes) if t]

    titulo = "Nuevo chat"
    for t in turnos:
        if t["role"] == "user":
            titulo = t["content"][:40].strip() or "Nuevo chat"
            break

    creado = datetime.datetime.now().isoformat()
    ruta = _ruta_chat(chat_id)
    if os.path.exists(ruta):
        try:
            with open(ruta, encoding="utf-8") as f:
                creado = json.load(f).get("creado", creado)
        except Exception:
            pass

    datos = {
        "titulo": titulo,
        "creado": creado,
        "actualizado": datetime.datetime.now().isoformat(),
        "turnos": turnos[-MAX_TURNOS:],
    }
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        registro.error(f"No se pudo guardar el chat {chat_id}: {e}")


def borrar_chat(chat_id):
    """Elimina un chat."""
    try:
        ruta = _ruta_chat(chat_id)
        if os.path.exists(ruta):
            os.remove(ruta)
    except Exception as e:
        registro.error(f"No se pudo borrar el chat {chat_id}: {e}")


def modelos_disponibles():
    """Devuelve la lista de modelos instalados en Ollama."""
    try:
        datos = ollama.list()
        nombres = []
        for m in datos.get("models", []):
            # Según la versión, el nombre viene en 'model' o 'name'.
            nombre = m.get("model") or m.get("name")
            if nombre:
                nombres.append(nombre)
        return nombres or [MODELO]
    except Exception as e:
        registro.error(f"No se pudieron listar los modelos de Ollama: {e}")
        return [MODELO]
