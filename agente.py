import json
import os
import ollama
from tools import filesystem, calendario, configuracion

MODELO = "qwen2.5:7b"

RUTA_MEMORIA = os.path.join(os.path.dirname(__file__), "memoria.json")
MAX_TURNOS = 40

MENSAJE_SISTEMA = {
    "role": "system",
    "content": (
        "Eres un asistente que automatiza tareas en la computadora del usuario "
        "usando las herramientas disponibles. Cuando el usuario pida crear o buscar algo, "
        "usa la herramienta adecuada. Las fechas van en formato AAAA-MM-DD y las "
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
]


def procesar(peticion, mensajes):
    """Procesa una petición. 'mensajes' es la lista de conversación (memoria).
    Devuelve (texto_respuesta, lista_de_acciones)."""
    mensajes.append({"role": "user", "content": peticion})
    acciones = []

    while True:
        respuesta = ollama.chat(model=MODELO, messages=mensajes, tools=HERRAMIENTAS)
        mensaje = respuesta.message
        mensajes.append(mensaje)

        if not mensaje.tool_calls:
            return mensaje.content, acciones

        for llamada in mensaje.tool_calls:
            nombre = llamada.function.name
            argumentos = llamada.function.arguments
            funcion = FUNCIONES.get(nombre)
            if funcion is None:
                resultado = f"Error: herramienta desconocida '{nombre}'"
            else:
                try:
                    resultado = funcion(**argumentos)
                except Exception as e:
                    resultado = f"Error al ejecutar {nombre}: {e}"
            acciones.append(f"{nombre}({argumentos}) -> {resultado}")
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


def cargar_memoria():
    """Devuelve la lista de mensajes inicial: sistema + historial guardado."""
    mensajes = [MENSAJE_SISTEMA]
    if os.path.exists(RUTA_MEMORIA):
        try:
            with open(RUTA_MEMORIA, encoding="utf-8") as f:
                turnos = json.load(f)
            mensajes.extend(turnos[-MAX_TURNOS:])
        except Exception:
            pass
    return mensajes


def guardar_memoria(mensajes):
    """Guarda solo los turnos de texto en memoria.json."""
    turnos = [t for t in (_turno_serializable(m) for m in mensajes) if t]
    try:
        with open(RUTA_MEMORIA, "w", encoding="utf-8") as f:
            json.dump(turnos[-MAX_TURNOS:], f, ensure_ascii=False, indent=2)
    except Exception:
        pass
