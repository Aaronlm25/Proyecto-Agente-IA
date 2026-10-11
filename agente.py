"""
agente.py

Gestión de chats (crear, listar, cargar, guardar, borrar) y utilidades de Ollama.

La lógica de los agentes ahora vive en la carpeta agentes/:
    agentes/root.py          -> el coordinador (procesar)
    agentes/especialistas.py -> los especialistas
    agentes/base.py          -> la clase Agente y el Contexto
    agentes/config.py        -> modelo, límites y tamaño de contexto

Se re-exporta `procesar` para que el código que hacía `agente.procesar(...)`
siga funcionando.
"""

import json
import os
import datetime

import ollama

import registro
from agentes import config
from agentes.root import procesar, mensaje_sistema  # noqa: F401  (re-exportados)

# Carpeta donde se guarda cada conversación por separado.
CARPETA_CHATS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chats")
os.makedirs(CARPETA_CHATS, exist_ok=True)
MAX_TURNOS = 40

MARCA_PETICION = "Petición del usuario:"


def _turno_serializable(m):
    """Convierte un mensaje (dict u objeto de ollama) a un turno guardable."""
    if isinstance(m, dict):
        role, contenido = m.get("role"), m.get("content")
    else:
        role, contenido = getattr(m, "role", None), getattr(m, "content", None)
    if role in ("user", "assistant") and contenido:
        return {"role": role, "content": contenido}
    return None


# ----------------- GESTIÓN DE CHATS -----------------

def _ruta_chat(chat_id):
    # El id viene de nosotros, pero lo limpiamos por si acaso.
    seguro = "".join(c for c in chat_id if c.isalnum() or c in "_-")
    return os.path.join(CARPETA_CHATS, f"{seguro}.json")


def crear_chat():
    """Crea un chat nuevo vacío y devuelve su id."""
    # Con microsegundos: dos chats creados en el mismo segundo ya no se pisan.
    chat_id = "chat_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
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
    """Devuelve los mensajes de un chat: sistema del root + turnos guardados."""
    mensajes = [mensaje_sistema()]
    ruta = _ruta_chat(chat_id)
    if os.path.exists(ruta):
        try:
            with open(ruta, encoding="utf-8") as f:
                datos = json.load(f)
            mensajes.extend(datos.get("turnos", [])[-MAX_TURNOS:])
        except Exception as e:
            registro.error(f"No se pudo cargar el chat {chat_id}: {e}")
    return mensajes


def _titulo_de(texto):
    # Si el mensaje trae un adjunto, el título es la petición, no el contenido del archivo.
    if MARCA_PETICION in texto:
        texto = texto.split(MARCA_PETICION, 1)[1]
    return texto.strip().replace("\n", " ")[:40].strip() or "Nuevo chat"


def guardar_chat(chat_id, mensajes):
    """Guarda los turnos de texto del chat y actualiza título y fecha."""
    turnos = [t for t in (_turno_serializable(m) for m in mensajes) if t]

    titulo = "Nuevo chat"
    for t in turnos:
        if t["role"] == "user":
            titulo = _titulo_de(t["content"])
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
        return nombres or [config.MODELO]
    except Exception as e:
        registro.error(f"No se pudieron listar los modelos de Ollama: {e}")
        return [config.MODELO]
