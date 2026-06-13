# 🤖 Agente de IA Local

Asistente de inteligencia artificial que corre **100% en local** (sin internet ni APIs de pago) y automatiza tareas del día a día mediante lenguaje natural: crear proyectos, carpetas, notas, eventos de calendario y archivos de configuración.

Le hablas en español como a un asistente normal y él decide qué acción ejecutar usando *function calling*.

## ✨ Características

- **Privado y offline**: el modelo corre en tu propia máquina, ningún dato sale de tu computadora.
- **Lenguaje natural**: no memorizas comandos, solo pides lo que necesitas.
- **Crea proyectos** con estructura estándar (`src`, `docs`, `tests`) y README automático.
- **Genera notas** en Markdown.
- **Agenda eventos** en formato `.ics` (compatible con Google Calendar, Outlook, Apple Calendar).
- **Configura proyectos** con plantillas (`python`, `web`).
- **Seguro por diseño**: el agente solo puede escribir dentro de una carpeta `workspace/`, nunca fuera.

## 🛠️ Tecnologías

- [Ollama](https://ollama.com) — ejecución de modelos de IA en local
- [Qwen 2.5 7B](https://ollama.com/library/qwen2.5) — modelo de lenguaje con soporte de herramientas
- **Python 3.11**
- *Function calling* / arquitectura de agente

## 📐 Cómo funciona

```
Usuario (lenguaje natural)
        │
        ▼
   Modelo local (Qwen 2.5)  ──►  decide qué herramienta usar
        │
        ▼
  Herramientas en Python  ──►  ejecutan la acción real
        │
        ▼
     workspace/  (carpetas, notas, eventos, configs)
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
```

## 📁 Estructura del proyecto

```
mi-agente-ia/
├── main.py                  # Agente: conecta el modelo con las herramientas
├── tools/
│   ├── filesystem.py        # Crear carpetas, proyectos y notas
│   ├── calendario.py        # Crear eventos .ics
│   └── configuracion.py     # Generar archivos de configuración
├── environment.yml          # Entorno de conda
└── README.md
```

## 🔮 Mejoras futuras

- [ ] Más tipos de plantilla de configuración
- [ ] Integración directa con Google Calendar
- [ ] Interfaz web ligera
- [ ] Historial de conversación persistente

---

Desarrollado por Aaron como proyecto de portafolio.
