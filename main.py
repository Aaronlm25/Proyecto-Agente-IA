import ollama

def main():
    respuesta = ollama.chat(
        model="qwen2.5:7b",
        messages=[{"role": "user", "content": "Dame un saludo corto confirmando que funcionas."}],
    )
    print(respuesta["message"]["content"])

if __name__ == "__main__":
    main()
