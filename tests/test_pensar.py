"""Opción de razonamiento (think) y protección contra marcadores sin rellenar."""

import json
from types import SimpleNamespace as NS

import pytest

from agentes import config, modelo, root


@pytest.fixture
def ollama_espia(monkeypatch):
    """Sustituye ollama.chat y guarda los argumentos de cada llamada."""
    import ollama
    llamadas = []

    def chat(**kw):
        llamadas.append(kw)
        if kw.get("think") is not None and kw["model"] == "sin-think":
            raise RuntimeError('"sin-think" does not support thinking')
        msg = NS(message=NS(role="assistant", content="ok", tool_calls=None))
        return iter([msg]) if kw.get("stream") else msg

    monkeypatch.setattr(ollama, "chat", chat)
    modelo._SIN_THINK.clear()
    return llamadas


def test_pensar_false_se_envia_a_ollama(ollama_espia, monkeypatch):
    monkeypatch.setattr(config, "PENSAR", False)
    modelo.chat(model="qwen3:8b", messages=[])
    assert ollama_espia[-1]["think"] is False


def test_pensar_none_no_envia_la_opcion(ollama_espia, monkeypatch):
    monkeypatch.setattr(config, "PENSAR", None)
    modelo.chat(model="qwen3:8b", messages=[])
    assert "think" not in ollama_espia[-1]


@pytest.mark.parametrize("stream", [False, True])
def test_modelo_sin_think_reintenta_sin_la_opcion(ollama_espia, monkeypatch, stream):
    monkeypatch.setattr(config, "PENSAR", False)
    r = modelo.chat(model="sin-think", messages=[], stream=stream)
    if stream:
        r = list(r)[0]
    assert r.message.content == "ok"
    assert "think" not in ollama_espia[-1]
    # La segunda vez ya no lo intenta con think
    modelo.chat(model="sin-think", messages=[])
    assert "think" not in ollama_espia[-1]


def test_config_lee_pensar(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PENSAR", False)
    ruta = tmp_path / "ajustes.json"
    ruta.write_text(json.dumps({"pensar": True}))
    config.cargar_ajustes(str(ruta))
    assert config.PENSAR is True


# ----------------- marcadores sin rellenar -----------------

def test_marcador_sin_rellenar_se_devuelve_al_root(workspace, monkeypatch):
    import ollama
    from conftest import ModeloFalso
    falso = ModeloFalso({
        "root": [
            ("tool", "delegar", {"agente": "organizador",
                                 "tarea": "Crea una nota llamada ollama con: <el resumen que devolvió web>"}),
            ("tool", "delegar", {"agente": "organizador",
                                 "tarea": "Crea una nota llamada ollama con: Ollama ejecuta modelos en local."}),
            ("texto", "Nota creada."),
        ],
        "organizador": [("tool", "crear_nota", {"titulo": "ollama", "contenido": "Ollama ejecuta modelos en local."}),
                        ("texto", "ok")],
    })
    monkeypatch.setattr(ollama, "chat", falso.chat)
    mensajes = [root.mensaje_sistema()]
    root.procesar("x", mensajes)
    resultados = [m["content"] for m in mensajes if isinstance(m, dict) and m.get("role") == "tool"]
    assert "marcador sin rellenar" in resultados[0]
    assert falso.agentes_llamados().count("organizador") == 2   # solo la segunda delegación
    nota = (workspace / "notas" / "ollama.md").read_text()
    assert "<el resumen" not in nota and "en local" in nota


def test_prompt_root_sin_marcadores_copiables():
    p = root.prompt_root()
    assert "<el resumen" not in p
    assert "Haz SOLO lo que el usuario pidió" in p
