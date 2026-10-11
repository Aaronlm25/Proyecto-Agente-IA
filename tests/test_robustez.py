"""Arreglos para modelos pequeños, sacados de las pruebas reales con qwen2.5:7b."""

import json

from agentes import root
from agentes.base import extraer_llamadas_de_texto
from agentes.especialistas import ESPECIALISTAS


def _llamada(nombre, argumentos):
    return json.dumps({"name": nombre, "arguments": argumentos}, ensure_ascii=False)


# ----------------- llamadas escritas como texto -----------------

def test_extrae_llamada_con_etiqueta():
    llamadas, resto = extraer_llamadas_de_texto(
        f"<tool_call>\n{_llamada('delegar', {'agente': 'web', 'tarea': 'x'})}\n</tool_call>",
        {"delegar": None})
    assert [l.function.name for l in llamadas] == ["delegar"]
    assert llamadas[0].function.arguments == {"agente": "web", "tarea": "x"}
    assert resto == ""


def test_extrae_json_suelto_y_conserva_el_texto():
    llamadas, resto = extraer_llamadas_de_texto(
        f"Voy a crear la nota: {_llamada('crear_nota', {'titulo': 'a'})}", {"crear_nota": None})
    assert llamadas[0].function.name == "crear_nota"
    assert resto == "Voy a crear la nota:"


def test_ignora_json_que_no_es_llamada_o_herramienta_desconocida():
    assert extraer_llamadas_de_texto('El dato es {"a": 1}', {"x": None})[0] == []
    assert extraer_llamadas_de_texto(_llamada("borrar_todo", {}), {"x": None})[0] == []


def test_root_ejecuta_llamada_escrita_como_texto(workspace, modelo):
    falso = modelo({
        "root": [("texto", "<tool_call>\n" + _llamada("delegar", {"agente": "archivos", "tarea": "Crea la carpeta demo"}) + "\n</tool_call>"),
                 ("texto", "Listo.")],
        "archivos": [("tool", "crear_carpeta", {"nombre": "demo"}), ("texto", "creada")],
    })
    texto, _ = root.procesar("crea demo", [root.mensaje_sistema()])
    assert texto == "Listo."
    assert (workspace / "demo").is_dir()
    assert "archivos" in falso.agentes_llamados()


# ----------------- respuestas vacías -----------------

def test_respuesta_vacia_se_reintenta_con_pista(workspace, modelo):
    falso = modelo({
        "root": [("vacio",),
                 ("tool", "delegar", {"agente": "archivos", "tarea": "Crea la carpeta demo"}),
                 ("texto", "Hecho.")],
        "archivos": [("tool", "crear_carpeta", {"nombre": "demo"}), ("texto", "ok")],
    })
    mensajes = [root.mensaje_sistema()]
    texto, _ = root.procesar("crea demo", mensajes)
    assert texto == "Hecho." and (workspace / "demo").is_dir()
    # El reintento llevaba la pista, pero la pista no se queda en el historial
    _, msgs_reintento = falso.llamadas[1]
    assert "llegó vacía" in msgs_reintento[-1]["content"]
    assert not any("llegó vacía" in str(m.get("content", "")) for m in mensajes if isinstance(m, dict))


def test_especialista_vacio_no_dice_hecho(workspace, modelo):
    modelo({
        "root": [("tool", "delegar", {"agente": "datos", "tarea": "analiza x.csv"}), ("texto", "fin")],
        "datos": [("vacio",), ("vacio",)],
    })
    _, acciones = root.procesar("x", [root.mensaje_sistema()])
    resultado = next(a for a in acciones if a.startswith("[datos] terminó"))
    assert "No completé la tarea" in resultado


# ----------------- el root intenta usar herramientas de otro -----------------

def test_root_llama_herramienta_de_especialista_y_se_redirige(workspace, modelo):
    falso = modelo({
        "root": [("tool", "crear_nota", {"titulo": "ideas", "contenido": "- uno\n- dos"}),
                 ("texto", "Nota creada.")],
        "organizador": [("tool", "crear_nota", {"titulo": "ideas", "contenido": "- uno\n- dos"}),
                        ("texto", "Nota creada en notas/ideas.md")],
    })
    root.procesar("crea una nota ideas", [root.mensaje_sistema()])
    assert (workspace / "notas" / "ideas.md").exists()
    assert "organizador" in falso.agentes_llamados()


def test_herramienta_sensible_redirigida_sigue_pidiendo_permiso(workspace, modelo):
    modelo({
        "root": [("tool", "ejecutar_comando", {"comando": "echo hola"}), ("texto", "fin")],
        "sistema": [("tool", "ejecutar_comando", {"comando": "echo hola"}), ("texto", "ok")],
    })
    pedidas = []
    root.procesar("x", [root.mensaje_sistema()], confirmador=lambda n, a: pedidas.append(n) or False)
    assert pedidas == ["ejecutar_comando"]


# ----------------- el root sabe qué se hizo de verdad -----------------

def test_resultado_de_delegacion_dice_que_herramientas_se_usaron(workspace, modelo):
    modelo({
        "root": [("tool", "delegar", {"agente": "web", "tarea": "busca y guarda una nota"}),
                 ("texto", "fin")],
        "web": [("texto", "Guardé la nota ollama.md")],   # mentira: web no puede guardar notas
    })
    mensajes = [root.mensaje_sistema()]
    root.procesar("x", mensajes)
    resultado = next(m["content"] for m in mensajes if isinstance(m, dict) and m.get("role") == "tool")
    assert "[Herramientas que usó web: ninguna]" in resultado


def test_prompts_explican_herramientas_y_varias_partes():
    p = root.prompt_root()
    assert "TUS ÚNICAS HERRAMIENTAS" in p and "VARIAS PARTES" in p
    assert "crear_nota" in p   # el root ve qué herramientas tiene cada especialista
    for especialista in ESPECIALISTAS.values():
        assert "Tus herramientas:" in especialista.prompt
        assert "NO hagas preguntas" in especialista.prompt
    assert "herramienta git" in ESPECIALISTAS["sistema"].prompt
