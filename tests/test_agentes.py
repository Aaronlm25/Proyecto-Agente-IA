"""Pruebas del sistema multiagente con un modelo falso (no necesita Ollama)."""

from datetime import date

import agente
from agentes import root, config
from agentes.especialistas import ESPECIALISTAS


def test_root_delega_a_varios_especialistas(workspace, modelo):
    falso = modelo({
        "root": [
            ("tool", "delegar", {"agente": "web", "tarea": "Busca la fecha de PyCon México"}),
            ("tool", "delegar", {"agente": "organizador",
                                 "tarea": "Crea una nota 'pycon' con el texto: es el 2026-11-19"}),
            ("texto", "Listo: busqué la fecha y creé la nota."),
        ],
        "web": [("texto", "PyCon México es el 2026-11-19 (https://ejemplo.com)")],
        "organizador": [
            ("tool", "crear_nota", {"titulo": "pycon", "contenido": "es el 2026-11-19"}),
            ("texto", "Nota creada en notas/pycon.md"),
        ],
    })
    mensajes = [root.mensaje_sistema()]
    texto, acciones = root.procesar("busca pycon y hazme una nota", mensajes)

    assert texto == "Listo: busqué la fecha y creé la nota."
    assert (workspace / "notas" / "pycon.md").exists()
    assert falso.agentes_llamados() == ["root", "web", "root", "organizador", "organizador", "root"]
    assert any(a.startswith("[root] → web") for a in acciones)
    assert any(a.startswith("[organizador] crear_nota") for a in acciones)
    # El resultado del especialista vuelve al root como mensaje 'tool' con tool_name
    tools = [m for m in mensajes if isinstance(m, dict) and m.get("role") == "tool"]
    assert tools[0]["tool_name"] == "delegar" and "2026-11-19" in tools[0]["content"]


def test_especialista_no_ve_la_conversacion(workspace, modelo):
    falso = modelo({
        "root": [("tool", "delegar", {"agente": "archivos", "tarea": "Crea la carpeta demo"}),
                 ("texto", "ok")],
        "archivos": [("tool", "crear_carpeta", {"nombre": "demo"}), ("texto", "creada")],
    })
    mensajes = [root.mensaje_sistema(), {"role": "user", "content": "SECRETO del chat"},
                {"role": "assistant", "content": "vale"}]
    root.procesar("crea demo", mensajes)
    _, msgs_archivos = next(c for c in falso.llamadas if c[0] == "archivos")
    assert len(msgs_archivos) == 2  # solo su prompt + la tarea
    assert "SECRETO" not in str(msgs_archivos)
    assert (workspace / "demo").is_dir()


def test_herramienta_sensible_sin_confirmador_se_rechaza(workspace, modelo):
    modelo({
        "root": [("tool", "delegar", {"agente": "sistema", "tarea": "ejecuta echo hola"}),
                 ("texto", "fin")],
        "sistema": [("tool", "ejecutar_comando", {"comando": "echo hola"}), ("texto", "x")],
    })
    _, acciones = root.procesar("x", [root.mensaje_sistema()])  # sin confirmador
    assert any("no la autorizó" in a for a in acciones)


def test_herramienta_sensible_con_confirmacion(workspace, modelo):
    pedidas = []
    modelo({
        "root": [("tool", "delegar", {"agente": "sistema", "tarea": "ejecuta echo hola"}),
                 ("texto", "fin")],
        "sistema": [("tool", "ejecutar_comando", {"comando": "echo hola"}), ("texto", "x")],
    })
    _, acciones = root.procesar("x", [root.mensaje_sistema()],
                                confirmador=lambda n, a: pedidas.append(n) or True)
    assert pedidas == ["ejecutar_comando"]
    assert any("hola" in a and "[código 0]" in a for a in acciones)


def test_limite_de_delegaciones(workspace, modelo):
    delegar = ("tool", "delegar", {"agente": "web", "tarea": "busca algo"})
    falso = modelo({"root": [delegar] * 20, "web": [("texto", "r")] * 20})
    root.procesar("x", [root.mensaje_sistema()])
    assert falso.agentes_llamados().count("web") == config.MAX_DELEGACIONES
    assert falso.agentes_llamados().count("root") == config.MAX_PASOS_ROOT


def test_especialista_con_limite_de_pasos(workspace, modelo):
    falso = modelo({
        "root": [("tool", "delegar", {"agente": "archivos", "tarea": "busca"}), ("texto", "fin")],
        "archivos": [("tool", "buscar_archivos", {})] * 50,
    })
    _, acciones = root.procesar("x", [root.mensaje_sistema()])
    assert falso.agentes_llamados().count("archivos") == config.MAX_PASOS_ESPECIALISTA
    assert any("límite" in a for a in acciones)


def test_cancelar_detiene_todo(workspace, modelo):
    falso = modelo({"root": [("tool", "delegar", {"agente": "web", "tarea": "x"})] * 5})
    texto, _ = root.procesar("x", [root.mensaje_sistema()], cancelado=lambda: True)
    assert "detenida" in texto
    assert "web" not in falso.agentes_llamados()


def test_especialista_inexistente(workspace, modelo):
    modelo({"root": [("tool", "delegar", {"agente": "pirata", "tarea": "x"}), ("texto", "fin")]})
    _, acciones = root.procesar("x", [root.mensaje_sistema()])
    assert any("No existe el especialista" in a for a in acciones)


def test_argumentos_mal_tipados_se_corrigen(workspace, modelo):
    modelo({
        "root": [("tool", "delegar", {"agente": "organizador", "tarea": "evento"}), ("texto", "f")],
        "organizador": [
            ("tool", "crear_evento", {"titulo": "reunión", "fecha": "2026-11-02", "hora": "10:00",
                                      "duracion_horas": "2", "inventado": "x"}),
            ("texto", "ok"),
        ],
    })
    _, acciones = root.procesar("x", [root.mensaje_sistema()])
    assert any("12:00" in a for a in acciones), acciones


def test_modo_plan_rechazado_no_ejecuta_nada(workspace, modelo):
    falso = modelo({"plan": [("texto", "1. delegar a web")]})
    texto, acciones = root.procesar("x", [root.mensaje_sistema()], planificador=lambda p: False)
    assert texto == "1. delegar a web" and acciones == []
    assert falso.agentes_llamados() == ["plan"]


def test_modo_plan_aprobado_ejecuta(workspace, modelo):
    falso = modelo({"plan": [("texto", "1. responder")], "root": [("texto", "hecho")]})
    texto, _ = root.procesar("x", [root.mensaje_sistema()], planificador=lambda p: True)
    assert texto == "hecho"
    assert falso.agentes_llamados() == ["plan", "root"]


def test_prompt_root_tiene_fecha_especialistas_y_recuerdos(workspace):
    from tools import memoria
    memoria.recordar("nombre", "Aaron")
    p = root.prompt_root()
    assert date.today().isoformat() in p
    assert all(nombre in p for nombre in ESPECIALISTAS)
    assert "Aaron" in p


def test_root_recuerda_datos(workspace, modelo):
    from tools import memoria
    modelo({"root": [("tool", "recordar", {"clave": "lenguaje", "valor": "Python"}),
                     ("texto", "anotado")]})
    root.procesar("me gusta python", [root.mensaje_sistema()])
    assert "Python" in memoria.recuperar("lenguaje")


def test_guardar_y_cargar_chat(workspace, modelo):
    modelo({"root": [("texto", "hola!")]})
    chat = agente.crear_chat()
    mensajes = agente.cargar_chat(chat)
    root.procesar("Contenido del archivo adjunto 'a.txt':\nbla bla\n\n"
                  "Petición del usuario: resume esto", mensajes)
    agente.guardar_chat(chat, mensajes)
    assert agente.listar_chats()[0]["titulo"] == "resume esto"
    recargado = agente.cargar_chat(chat)
    assert recargado[0]["role"] == "system"
    assert recargado[-1] == {"role": "assistant", "content": "hola!"}


def test_dos_chats_seguidos_no_se_pisan():
    assert agente.crear_chat() != agente.crear_chat()
