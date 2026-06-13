import agente


def main():
    print("Agente de IA local. Escribe lo que quieres hacer (o 'salir').\n")
    mensajes = [agente.MENSAJE_SISTEMA]
    while True:
        peticion = input("Tú: ").strip()
        if peticion.lower() in ("salir", "exit", "quit"):
            break
        if not peticion:
            continue
        respuesta, acciones = agente.procesar(peticion, mensajes)
        for a in acciones:
            print(f"  ⚙️  {a}")
        print("\n🤖", respuesta)


if __name__ == "__main__":
    main()
