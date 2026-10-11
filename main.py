"""
main.py

Versión de terminal del agente multiagente.
(La interfaz gráfica se abre con: python app.py)
"""

import agente
from agentes import root


def confirmar(nombre, argumentos):
    """Pide permiso en la terminal antes de ejecutar acciones sensibles."""
    print(f"\n  ⚠️  El agente quiere ejecutar: {nombre} {argumentos}")
    return input("  ¿Permitir? (s/n): ").strip().lower() in ("s", "si", "sí", "y", "yes")


def main():
    print("Agente de IA local (multiagente). Escribe lo que quieres hacer (o 'salir').\n")
    chat_id = agente.crear_chat()
    mensajes = agente.cargar_chat(chat_id)  # incluye el prompt del root con tus recuerdos
    while True:
        try:
            peticion = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if peticion.lower() in ("salir", "exit", "quit"):
            break
        if not peticion:
            continue

        hubo_texto = []

        def on_token(t):
            if not hubo_texto:
                print("🤖 ", end="")
            hubo_texto.append(t)
            print(t, end="", flush=True)

        def on_accion(linea):
            print(f"\n  ⚙️  {linea}")
            hubo_texto.clear()  # el siguiente texto del root empieza en línea nueva

        respuesta, _ = root.procesar(peticion, mensajes, confirmador=confirmar,
                                     on_accion=on_accion, on_token=on_token)
        if not hubo_texto and respuesta:
            print(f"🤖 {respuesta}", end="")
        print("\n")
        agente.guardar_chat(chat_id, mensajes)


if __name__ == "__main__":
    main()
