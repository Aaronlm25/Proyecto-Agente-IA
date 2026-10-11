# 🤖 Agente de IA Local — Multiagente

Asistente de inteligencia artificial que corre **en local** con Ollama y automatiza
tareas del día a día mediante lenguaje natural. Le hablas en español —por texto o
por voz— y un **agente coordinador (root)** reparte el trabajo entre **agentes
especialistas**, cada uno con sus propias herramientas.

> El modelo de IA corre en tu máquina. Solo sale a internet cuando el agente **web**
> hace una búsqueda (DuckDuckGo) o lee una página.

## ✨ Características

- **Arquitectura multiagente:** un root que planifica y delega + 5 especialistas.
- **Modelo local:** Ollama + Qwen 2.5 (configurable desde Ajustes).
- **Interfaz moderna** (HTML/CSS) que se ve nítida en Linux, Windows y macOS, con tema claro
  y oscuro, y la actividad de cada agente en vivo. También hay versión de terminal.
- **Voz:** reconocimiento (Vosk) y síntesis (Piper) en español.
- **Visión:** lee imágenes, gráficas y tablas fotografiadas.
- **Memoria:** recuerda datos del usuario entre sesiones.
- **Proyectos, notas en Markdown y eventos `.ics`** (Google Calendar, Outlook, Apple).
- **Análisis de datos:** responde preguntas sobre CSV/Excel y genera gráficas.
- **Modo plan:** muestra los pasos antes de actuar y espera tu aprobación.

## 📐 Cómo funciona

```
                     Usuario (texto o voz)
                              │
                     ┌────────▼────────┐
                     │      ROOT       │  conversa, recuerda datos,
                     │  (coordinador)  │  divide la tarea y DELEGA
                     └────────┬────────┘
     ┌───────────┬────────────┼────────────┬───────────┐
     ▼           ▼            ▼            ▼           ▼
 archivos   organizador    sistema        web        datos
 proyectos  notas y        terminal,    búsquedas   CSV/Excel,
 config     eventos .ics   pip, git     y páginas   gráficas, imágenes
```

Ejemplo: *"Busca cuándo es la próxima PyCon México y agéndala"*
1. root → **web**: "busca la fecha de la próxima PyCon México"
2. web responde con la fecha y la URL
3. root → **organizador**: "crea un evento el 2026-11-19 llamado PyCon México"
4. root le responde al usuario con el resumen

Cada especialista recibe solo sus 2–4 herramientas (un modelo de 7B elige mucho
mejor así que con 17 a la vez) y empieza cada subtarea con un historial limpio.

## 🛠️ Tecnologías

- [Ollama](https://ollama.com/) + [Qwen 2.5 7B](https://ollama.com/library/qwen2.5)
- [Vosk](https://alphacephei.com/vosk/) (voz → texto) y [Piper](https://github.com/rhasspy/piper) (texto → voz)
- pandas + matplotlib, DuckDuckGo Search (`ddgs`)
- Interfaz: Flask + HTML/CSS/JS (marked, DOMPurify, highlight.js; fuentes Figtree,
  Source Serif 4 y JetBrains Mono incluidas, sin depender de internet)
- Ventana: pywebview (opcional) o Chrome/Edge en modo aplicación
- Python 3.11 · conda · pytest

## 🚀 Instalación (Linux)

```bash
# 1. Clonar el repositorio
git clone https://github.com/Aaronlm25/mi-agente-ia.git
cd mi-agente-ia

# 2. Librería del sistema para el micrófono (solo si usarás la voz)
sudo apt install libportaudio2

# 3. Entorno de Python (instala también requirements.txt)
conda env create -f environment.yml
conda activate mi-agente-ia
#    (sin conda:  python3.11 -m venv venv && source venv/bin/activate && pip install -r requirements.txt)

# 4. Ollama y los modelos
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b
ollama pull qwen2.5vl:7b      # opcional: para leer imágenes

# 5. (Opcional) Ventana propia en lugar de Chrome/Edge
pip install "pywebview[qt]"   # Linux
pip install pywebview         # Windows / macOS
```

Para la voz (opcional) necesitas el modelo de Vosk en
`modelos/vosk-model-small-es-0.42/` y la voz de Piper en `voces/es_MX-claude-high.onnx`.

## 💻 Uso

```bash
python app.py               # interfaz gráfica
python app.py --navegador   # forzar Chrome/Edge o el navegador
python app.py --servidor    # solo el servidor; abre la dirección que muestra
python main.py              # versión de terminal
```

`app.py` abre la interfaz en una ventana propia con pywebview si lo tienes instalado.
Si no, usa Chrome, Chromium, Edge o Brave en modo aplicación (una ventana sin pestañas),
y si tampoco hay ninguno, tu navegador predeterminado.

### La interfaz

- **Actividad de los agentes:** cada respuesta muestra qué especialista trabajó, con qué
  herramientas y qué devolvió. Haz clic en el resumen para desplegarlo.
- **Confirmaciones:** cuando el agente sistema quiere usar la terminal, aparece una ventana
  con el comando exacto para que lo permitas o lo rechaces.
- **Adjuntos:** botón del clip o arrastra el archivo a la ventana (PDF, texto, CSV, Excel,
  imágenes). Se guardan en `workspace/adjuntos/`.
- **Voz:** el micrófono dicta un mensaje; el botón de ondas activa la conversación manos
  libres; el altavoz lee las respuestas.
- **Atajos:** `Enter` envía, `Shift+Enter` hace un salto de línea, `Esc` detiene,
  `Ctrl+K` abre un chat nuevo y `↑` recupera tu último mensaje.

Ejemplos:

```
Créame un proyecto llamado tienda-online y genérale configuración web
Agéndame una reunión de portafolio mañana a las 10:00
Busca las novedades de Python 3.14 y guárdalas en una nota
Analiza ventas.csv: ¿qué mes vendió más? Hazme también una gráfica de barras
Inicializa git en tienda-online y haz un commit
```

## ⚙️ Configuración

`agentes/config.py`:

| Variable | Para qué sirve |
|---|---|
| `MODELO` | Modelo de texto (también se cambia desde Ajustes) |
| `MODELO_VISION` | Modelo para imágenes |
| `NUM_CTX` | Tamaño de contexto en tokens (súbelo si tienes memoria) |
| `MAX_DELEGACIONES` | Delegaciones máximas por petición |
| `MAX_PASOS_ROOT` / `MAX_PASOS_ESPECIALISTA` | Límite de pasos para evitar bucles |

## ➕ Cómo agregar un especialista

1. Escribe sus funciones en `tools/` (deben devolver texto).
2. Regístralas en `tools/catalogo.py` (`FUNCIONES` + `HERRAMIENTAS`).
3. Crea el agente en `agentes/especialistas.py` con `especialista(...)` y
   añádelo a `ESPECIALISTAS`. El root lo descubre solo.

## 📁 Estructura

```
.
├── app.py                  # Abre la interfaz (ventana propia, Chrome/Edge o navegador)
├── main.py                 # Versión de terminal
├── agente.py               # Gestión de chats (guardar, cargar, listar)
├── interfaz/
│   ├── servidor.py         # Servidor local: API + eventos en vivo
│   └── static/             # index.html, app.css, app.js, fuentes y librerías
├── agentes/
│   ├── config.py           # Modelo, límites, tamaño de contexto
│   ├── base.py             # Clase Agente (bucle) y Contexto (confirmaciones, cancelación)
│   ├── especialistas.py    # archivos, organizador, sistema, web, datos
│   └── root.py             # Coordinador: delegar() y procesar()
├── tools/
│   ├── catalogo.py         # Catálogo único de herramientas
│   ├── filesystem.py       # Carpetas, proyectos, notas (con ruta_segura)
│   ├── calendario.py       # Eventos .ics
│   ├── configuracion.py    # Archivos de configuración
│   ├── terminal.py         # Comandos (lista blanca, sin shell)
│   ├── web.py              # Búsqueda y lectura de páginas
│   ├── memoria.py          # Recuerdos del usuario
│   ├── datos.py            # Análisis y gráficas de tablas
│   ├── vision.py           # Imágenes
│   └── voz.py / escucha.py / habla.py
├── lectura.py              # Lee PDFs y texto adjuntos
├── registro.py             # Logs en logs/agente.log
├── tests/                  # Pruebas con modelo simulado (no necesitan Ollama)
├── modelos/  voces/        # Modelos de voz
└── workspace/              # Salida del agente (no se sube al repo)
```

## 🔒 Seguridad

- **Archivos:** todo lo que el agente escribe pasa por `ruta_segura()`; no puede
  salir de `workspace/` (ni con `../`, ni con rutas absolutas).
- **Terminal:** sin shell (`; && | >` no funcionan), solo programas de una lista
  blanca, sin rutas fuera del workspace, con timeout. **Cada comando, instalación
  o acción git pide tu confirmación** (en la interfaz y en la terminal).
- **Código de análisis de datos:** se revisa con `ast` antes de ejecutarse (sin
  imports, sin `open`, sin leer/escribir archivos).
- **Web:** el agente web tiene instrucciones de ignorar órdenes escritas dentro de
  las páginas.
- **Interfaz:** el servidor solo escucha en `127.0.0.1` y cada sesión usa un token
  secreto, así que ninguna otra página de tu navegador puede darle órdenes al agente.

⚠️ Esto reduce mucho el riesgo, pero no es una sandbox completa: por ejemplo,
`python script.py` ejecuta lo que diga ese script. No desactives las
confirmaciones y, si quieres aislamiento total, ejecuta el agente en un contenedor.

## 🧪 Pruebas

```bash
pytest -q
```

Usan un modelo simulado, así que no necesitan Ollama encendido.
