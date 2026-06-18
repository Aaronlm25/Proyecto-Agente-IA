# 🤖 Agente de IA Local

Asistente de inteligencia artificial que corre **100% en local** (sin internet
ni APIs de pago) y automatiza tareas del día a día mediante lenguaje natural.
Le hablas en español —por texto o por voz— y él decide qué acción ejecutar
usando *function calling*, con una interfaz web tipo chat.

> Proyecto personal. Todo el procesamiento ocurre en tu máquina: ningún dato
> sale de tu computadora.

## ✨ Características

- **Privado y offline:** el modelo corre en tu propia máquina; ningún dato sale de tu equipo.
- **Lenguaje natural:** no memorizas comandos, solo pides lo que necesitas.
- **Interfaz de chat:** interfaz web para conversar con el agente de forma visual.
- **Entrada y salida por voz:** reconocimiento de voz (Vosk) y síntesis de voz en español.
- **Visión:** capacidad de procesar imágenes.
- **Memoria:** mantiene contexto de la conversación.
- **Gestión de proyectos:** crea proyectos con estructura estándar (`src`, `docs`, `tests`) y README automático.
- **Notas en Markdown** y **eventos de calendario** en formato `.ics` (Google Calendar, Outlook, Apple Calendar).
- **Análisis de datos:** procesa archivos y genera gráficas.
- **Seguro por diseño:** el agente solo puede escribir dentro de la carpeta `workspace/`, nunca fuera.

## 🛠️ Tecnologías

- [Ollama](https://ollama.com/) — ejecución de modelos de IA en local
- [Qwen 2.5 7B](https://ollama.com/library/qwen2.5) — modelo de lenguaje con soporte de herramientas
- [Vosk](https://alphacephei.com/vosk/) — reconocimiento de voz offline (español)
- Modelo de voz `es_MX` — síntesis de voz en español
- Python 3.11 · conda
- Function calling / arquitectura de agente

<!-- Si probaste varios modelos (Llama, Mistral, Gemma), menciónalo aquí, por
     ejemplo: "Compatible con distintos modelos de Ollama; probado con Qwen 2.5,
     Llama y Mistral." -->

## 📐 Cómo funciona

```
Usuario (texto o voz, en español)
        │
        ▼
   Modelo local (Qwen 2.5)  ──►  decide qué herramienta usar
        │
        ▼
  Herramientas en Python  ──►  ejecutan la acción real
        │
        ▼
     workspace/  (proyectos, notas, eventos, gráficas, configs)
```

## 🚀 Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/Aaronlm25/mi-agente-ia.git
cd mi-agente-ia

# 2. Crear el entorno con conda
conda env create -f environment.yml
conda activate mi-agente-ia

# 3. Instalar Ollama y descargar el modelo
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b
```

## 💻 Uso

```bash
python main.py
```

Ejemplos de lo que puedes pedirle:

```
Tú: Créame un proyecto llamado tienda-online y genérale configuración web
Tú: Agéndame una reunión llamada revisión de portafolio el 2026-06-25 a las 10:00
Tú: Crea una nota titulada ideas con el contenido: aprender sobre agentes de IA
Tú: Analiza el archivo ventas.csv y hazme una gráfica
```

## 📁 Estructura del proyecto

```
.
├── main.py              # Punto de entrada
├── agente.py            # Lógica del agente (conecta modelo y herramientas)
├── app.py               # Interfaz web tipo chat
├── lectura.py           # Lectura / procesamiento de entradas
├── registro.py          # Registro y logging
├── ajustes.json         # Configuración
├── environment.yml      # Entorno de conda
├── requeriments.txt     # Dependencias
├── tools/               # Herramientas que el agente puede ejecutar
│   ├── filesystem.py    #   crear carpetas, proyectos y notas
│   ├── calendario.py    #   eventos .ics
│   ├── configuracion.py #   archivos de configuración
│   ├── datos.py         #   análisis de datos
│   ├── vision.py        #   procesamiento de imágenes
│   ├── voz.py / habla.py / escucha.py   # voz (entrada y salida)
│   ├── memoria.py       #   memoria de conversación
│   ├── terminal.py      #   ejecución en terminal
│   └── web.py           #   interfaz / utilidades web
├── modelos/             # Modelos de voz (Vosk)
├── voces/               # Voces para síntesis (es_MX)
└── workspace/           # Salida del agente (NO se sube al repo)
```

## 🔒 Seguridad

El agente está limitado a operar únicamente dentro de la carpeta `workspace/`,
evitando que pueda modificar archivos fuera de ella.
