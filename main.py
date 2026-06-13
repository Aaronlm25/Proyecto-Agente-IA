import ollama
from tools import filesystem, calendario, configuracion

MODELO = "qwen2.5:7b"

# Conecta el nombre que ve el modelo con la función real de Python
FUNCIONES = {
    "crear_carpeta": filesystem.crear_carpeta,
    "crear_proyecto": filesystem.crear_proyecto,
    "crear_nota": filesystem.crear_nota,
    "crear_evento": calendario.crear_evento,
    "generar_config": configuracion.generar_config,
}

# Descripción de las herramientas para que el modelo sepa cuándo usarlas
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


def ejecutar(peticion: str):
    mensajes = [
        {
            "role": "system",
            "content": (
                "Eres un asistente que automatiza tareas en la computadora del usuario "
                "usando las herramientas disponibles. Cuando el usuario pida crear algo, "
                "usa la herramienta adecuada. Responde siempre en español."
            ),
        },
        {"role": "user", "content": peticion},
    ]

    while True:
        respuesta = ollama.chat(model=MODELO, messages=mensajes, tools=HERRAMIENTAS)
        mensaje = respuesta.message
        mensajes.append(mensaje)

        if not mensaje.tool_calls:
            # El modelo no pidió más herramientas: ya es su respuesta final
            print("\n🤖", mensaje.content)
            break

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
            print(f"  ⚙️  {nombre}({argumentos}) -> {resultado}")
            mensajes.append({"role": "tool", "content": resultado})


def main():
    print("Agente de IA local. Escribe lo que quieres hacer (o 'salir').\n")
    while True:
        peticion = input("Tú: ").strip()
        if peticion.lower() in ("salir", "exit", "quit"):
            break
        if peticion:
            ejecutar(peticion)


if __name__ == "__main__":
    main()
