"""
Configuración común de las pruebas.

- Usa un workspace temporal (no toca tu carpeta workspace/ real).
- Sustituye ollama.chat por un MODELO FALSO con guion: no hace falta tener
  Ollama encendido para correr las pruebas.

Ejecuta las pruebas con:   pytest -q
"""

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# Debe definirse ANTES de importar tools.* (filesystem lee la variable al importarse).
_WS = tempfile.mkdtemp(prefix="agente_ws_")
os.environ["AGENTE_WORKSPACE"] = _WS


@pytest.fixture
def workspace():
    """Workspace temporal vacío para cada prueba."""
    import shutil
    from tools import filesystem
    for hijo in filesystem.BASE_DIR.iterdir():
        shutil.rmtree(hijo) if hijo.is_dir() else hijo.unlink()
    return filesystem.BASE_DIR


@pytest.fixture(autouse=True)
def memoria_temporal(tmp_path, monkeypatch):
    """Los recuerdos y los chats de las pruebas van a una carpeta temporal."""
    from tools import memoria
    import agente
    monkeypatch.setattr(memoria, "RUTA", str(tmp_path / "recuerdos.json"))
    monkeypatch.setattr(agente, "CARPETA_CHATS", str(tmp_path / "chats"))
    os.makedirs(tmp_path / "chats", exist_ok=True)


def _quien_llama(mensajes, tools):
    """Identifica qué agente está llamando al modelo según su prompt de sistema."""
    sistema = mensajes[0]["content"] if mensajes and isinstance(mensajes[0], dict) else ""
    if sistema.startswith("Eres el agente coordinador"):
        return "root" if tools else "plan"
    if sistema.startswith("Eres un generador de código"):
        return "codigo"
    for nombre in ("archivos", "organización", "terminal", "investigación", "datos"):
        if f"especialista en {nombre}" in sistema:
            return {"organización": "organizador", "terminal": "sistema",
                    "investigación": "web"}.get(nombre, nombre)
    return "desconocido"


class ModeloFalso:
    """Devuelve respuestas guionizadas para cada agente.

    guion = {
        "root": [("tool", "delegar", {...}), ("texto", "listo")],
        "web":  [("tool", "buscar_web", {...}), ("texto", "resumen")],
    }
    Si a un agente se le acaba el guion, responde ("texto", "fin").
    """

    def __init__(self, guion):
        self.guion = {k: list(v) for k, v in guion.items()}
        self.llamadas = []   # (agente, mensajes) de cada llamada

    def chat(self, model=None, messages=None, tools=None, stream=False, options=None, **kw):
        agente = _quien_llama(messages, tools)
        self.llamadas.append((agente, [dict(m) if isinstance(m, dict) else m for m in messages]))
        cola = self.guion.get(agente) or []
        paso = cola.pop(0) if cola else ("texto", "fin")

        if paso[0] == "tool":
            llamadas = [NS(function=NS(name=paso[1], arguments=paso[2]))]
            msg = NS(role="assistant", content="", tool_calls=llamadas)
        elif paso[0] == "tools":   # varias herramientas a la vez
            llamadas = [NS(function=NS(name=n, arguments=a)) for n, a in paso[1]]
            msg = NS(role="assistant", content="", tool_calls=llamadas)
        else:
            msg = NS(role="assistant", content=paso[1], tool_calls=None)

        if stream:
            return iter([NS(message=msg)])
        return NS(message=msg)

    def agentes_llamados(self):
        return [a for a, _ in self.llamadas]


@pytest.fixture
def modelo(monkeypatch):
    """Uso: falso = modelo({...guion...})"""
    import ollama

    def crear(guion):
        falso = ModeloFalso(guion)
        monkeypatch.setattr(ollama, "chat", falso.chat)
        return falso

    return crear
