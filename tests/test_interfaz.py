"""Pruebas del servidor de la interfaz (API + eventos), con el modelo falso."""

import io
import time
import queue

import pytest

TOKEN = "token-de-prueba"


@pytest.fixture
def servidor(tmp_path, monkeypatch, workspace):
    from interfaz import servidor as mod
    monkeypatch.setattr(mod, "RUTA_AJUSTES", str(tmp_path / "ajustes.json"))
    app, estado, bus = mod.crear_app(TOKEN, hosts_permitidos={"localhost", "127.0.0.1"})
    app.testing = True
    cliente = app.test_client()
    cliente.environ_base["HTTP_HOST"] = "127.0.0.1"
    return cliente, estado, bus


def h():
    return {"X-Token": TOKEN}


def esperar_evento(cola, tipo, segundos=5):
    fin = time.time() + segundos
    vistos = []
    while time.time() < fin:
        try:
            ev = cola.get(timeout=0.1)
        except queue.Empty:
            continue
        vistos.append(ev)
        if ev["tipo"] == tipo:
            return ev, vistos
    raise AssertionError(f"No llegó el evento '{tipo}'. Llegaron: {[e['tipo'] for e in vistos]}")


# ----------------- seguridad -----------------

def test_api_sin_token_se_rechaza(servidor):
    cliente, _, _ = servidor
    assert cliente.get("/api/estado").status_code == 403
    assert cliente.get("/api/estado", headers={"X-Token": "otro"}).status_code == 403
    assert cliente.get("/api/estado", headers=h()).status_code == 200


def test_host_desconocido_se_rechaza(servidor):
    cliente, _, _ = servidor
    r = cliente.get("/api/estado", headers={**h(), "Host": "malicioso.com"})
    assert r.status_code == 403


def test_pagina_incluye_token_y_csp(servidor):
    cliente, _, _ = servidor
    r = cliente.get("/")
    assert r.status_code == 200
    assert TOKEN.encode() in r.data
    assert "script-src 'self'" in r.headers["Content-Security-Policy"]


# ----------------- conversación -----------------

def test_enviar_publica_tokens_actividad_y_fin(servidor, modelo, workspace):
    cliente, estado, bus = servidor
    modelo({
        "root": [("tool", "delegar", {"agente": "archivos", "tarea": "Crea la carpeta demo"}),
                 ("texto", "Carpeta lista.")],
        "archivos": [("tool", "crear_carpeta", {"nombre": "demo"}), ("texto", "creada")],
    })
    cola = bus.suscribir()
    r = cliente.post("/api/enviar", json={"texto": "crea demo"}, headers=h())
    assert r.status_code == 200
    fin, vistos = esperar_evento(cola, "fin")
    assert fin["texto"] == "Carpeta lista."
    actividades = [e["actividad"] for e in vistos if e["tipo"] == "actividad"]
    assert [a["tipo"] for a in actividades] == ["delegacion", "herramienta", "termino"]
    assert actividades[1]["agente"] == "archivos" and actividades[1]["ok"] is True
    assert (workspace / "demo").is_dir()
    assert not estado.generando


def test_no_se_puede_enviar_dos_veces_a_la_vez(servidor):
    cliente, estado, _ = servidor
    estado.generando = True
    r = cliente.post("/api/enviar", json={"texto": "hola"}, headers=h())
    assert r.status_code == 409


def test_no_se_cambia_de_chat_mientras_trabaja(servidor):
    cliente, estado, _ = servidor
    estado.generando = True
    assert cliente.post("/api/chats", headers=h()).status_code == 409


def test_confirmacion_desde_la_pagina(servidor, modelo):
    cliente, estado, bus = servidor
    modelo({
        "root": [("tool", "delegar", {"agente": "sistema", "tarea": "echo hola"}), ("texto", "fin")],
        "sistema": [("tool", "ejecutar_comando", {"comando": "echo hola"}), ("texto", "ok")],
    })
    cola = bus.suscribir()
    cliente.post("/api/enviar", json={"texto": "di hola"}, headers=h())
    pregunta, _ = esperar_evento(cola, "confirmar")
    assert pregunta["herramienta"] == "ejecutar_comando"
    assert pregunta["argumentos"]["comando"] == "echo hola"
    # La página puede recuperar la pregunta si se recarga
    assert cliente.get("/api/estado", headers=h()).json["pendientes"][0]["id"] == pregunta["id"]
    cliente.post("/api/responder", json={"id": pregunta["id"], "valor": True}, headers=h())
    _, vistos = esperar_evento(cola, "fin")
    herramienta = next(e["actividad"] for e in vistos
                       if e["tipo"] == "actividad" and e["actividad"]["tipo"] == "herramienta")
    assert "hola" in herramienta["resultado"]


def test_rechazar_confirmacion(servidor, modelo):
    cliente, _, bus = servidor
    modelo({
        "root": [("tool", "delegar", {"agente": "sistema", "tarea": "echo hola"}), ("texto", "fin")],
        "sistema": [("tool", "ejecutar_comando", {"comando": "echo hola"}), ("texto", "ok")],
    })
    cola = bus.suscribir()
    cliente.post("/api/enviar", json={"texto": "di hola"}, headers=h())
    pregunta, _ = esperar_evento(cola, "confirmar")
    cliente.post("/api/responder", json={"id": pregunta["id"], "valor": False}, headers=h())
    _, vistos = esperar_evento(cola, "fin")
    herramienta = next(e["actividad"] for e in vistos
                       if e["tipo"] == "actividad" and e["actividad"]["tipo"] == "herramienta")
    assert herramienta["ok"] is False and "no la autorizó" in herramienta["resultado"]


def test_detener_cancela_una_confirmacion_pendiente(servidor, modelo):
    cliente, estado, bus = servidor
    modelo({
        "root": [("tool", "delegar", {"agente": "sistema", "tarea": "x"})] * 3,
        "sistema": [("tool", "ejecutar_comando", {"comando": "echo hola"})],
    })
    cola = bus.suscribir()
    cliente.post("/api/enviar", json={"texto": "x"}, headers=h())
    esperar_evento(cola, "confirmar")
    cliente.post("/api/detener", headers=h())
    fin, _ = esperar_evento(cola, "fin")
    assert fin["cancelado"] is True
    assert not estado.generando


# ----------------- chats, adjuntos y ajustes -----------------

def test_chats_crear_abrir_borrar(servidor, modelo):
    cliente, estado, bus = servidor
    modelo({"root": [("texto", "hola!")]})
    cola = bus.suscribir()
    cliente.post("/api/enviar", json={"texto": "saluda"}, headers=h())
    esperar_evento(cola, "fin")
    primero = estado.chat_actual
    nuevo = cliente.post("/api/chats", headers=h()).json["id"]
    assert nuevo != primero
    turnos = cliente.get(f"/api/chats/{primero}", headers=h()).json["turnos"]
    assert turnos == [{"rol": "user", "texto": "saluda"}, {"rol": "assistant", "texto": "hola!"}]
    assert cliente.get("/api/chats/no_existe", headers=h()).status_code == 404
    cliente.delete(f"/api/chats/{primero}", headers=h())
    assert primero not in [c["id"] for c in cliente.get("/api/estado", headers=h()).json["chats"]]


def test_adjuntar_guarda_dentro_del_workspace(servidor, workspace):
    cliente, _, _ = servidor
    datos = {"archivo": (io.BytesIO(b"a,b\n1,2\n"), "../../ventas peligrosas.csv")}
    r = cliente.post("/api/adjuntar", data=datos, headers=h(), content_type="multipart/form-data")
    assert r.status_code == 200
    assert r.json["tipo"] == "datos"
    guardado = workspace / r.json["ruta"]
    assert guardado.exists() and guardado.parent.name == "adjuntos"


def test_adjuntar_tipo_no_soportado(servidor):
    cliente, _, _ = servidor
    datos = {"archivo": (io.BytesIO(b"MZ..."), "programa.exe")}
    r = cliente.post("/api/adjuntar", data=datos, headers=h(), content_type="multipart/form-data")
    assert r.status_code == 415


def test_adjunto_de_texto_llega_al_agente(servidor, modelo, workspace):
    cliente, estado, bus = servidor
    falso = modelo({"root": [("texto", "Resumido.")]})
    datos = {"archivo": (io.BytesIO("Contenido secreto del informe".encode()), "informe.txt")}
    adj = cliente.post("/api/adjuntar", data=datos, headers=h(),
                       content_type="multipart/form-data").json
    cola = bus.suscribir()
    cliente.post("/api/enviar", json={"texto": "resume", "adjunto": adj}, headers=h())
    esperar_evento(cola, "fin")
    _, mensajes = falso.llamadas[0]
    assert "Contenido secreto del informe" in mensajes[-1]["content"]
    # Al recargar el chat se muestra solo la petición, con el nombre del archivo
    turno = cliente.get("/api/estado", headers=h()).json["turnos"][0]
    assert turno == {"rol": "user", "texto": "resume", "adjunto": "informe.txt"}


def test_ajustes_se_guardan(servidor, tmp_path):
    from agentes import config
    cliente, _, _ = servidor
    r = cliente.post("/api/ajustes", json={"tema": "dark", "modelo": "otro:1b", "modo_plan": True,
                                          "tema_raro": "x"}, headers=h())
    assert r.json["ajustes"]["tema"] == "dark" and r.json["ajustes"]["modo_plan"] is True
    assert "tema_raro" not in r.json["ajustes"]
    assert config.MODELO == "otro:1b"
    assert '"dark"' in (tmp_path / "ajustes.json").read_text()
    config.MODELO = "qwen2.5:7b"
