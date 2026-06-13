import ollama
from tools import filesystem, calendario, configuracion

MODELO = "qwen2.5:7b"

MENSAJE_SISTEMA = {
    "role": "system",
    "content": (
        "Eres un asistente que automatiza tareas en la computadora del usuario "
        "usando las herramientas disponibles. Cuando el usuario pida crear algo, "
        "usa la herramienta adecuada. Las fechas van en formato AAAA-MM-DD y las "
        "horas en formato HH:MM de 24 horas. Responde siempre en español."
    ),
}

FUNCIONES = {
    "crear_carpeta": filesystem.crear_carpeta,
    "crear_proyecto": filesystem.crear_proyecto,
    "crear_nota": filesystem.crear_nota,
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
    """Procesa una petición del usuario.
    'mensajes' es la lista de conversación (se va modificando para tener memoria).
    Devuelve (texto_de_respuesta, lista_de_acciones_ejecutadas)."""
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
