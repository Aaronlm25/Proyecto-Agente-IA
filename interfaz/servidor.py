"""
interfaz/servidor.py

Servidor local de la interfaz. Sirve la página (HTML/CSS/JS de interfaz/static)
y una pequeña API que conecta la página con el sistema multiagente.

    Página  ──POST /api/...──►  servidor  ──►  agentes.root.procesar()
    Página  ◄──GET /api/eventos (SSE)──  tokens, actividad, confirmaciones, fin

Seguridad:
  - Solo escucha en 127.0.0.1 (nadie de tu red puede entrar).
  - Cada sesión tiene un token secreto; la API lo exige en la cabecera X-Token.
    Así una página web cualquiera abierta en tu navegador no puede mandarle
    órdenes al agente.
  - Se valida la cabecera Host (protege contra "DNS rebinding").
"""

import os
import json
import queue
import secrets
import threading
import uuid

from flask import Flask, Response, abort, jsonify, request, send_from_directory

import agente
import lectura
import registro
from agentes import config, root
from agentes.especialistas import ESPECIALISTAS
from tools import memoria
from tools.filesystem import ruta_segura, nombre_archivo_seguro, BASE_DIR

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESTATICOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
RUTA_AJUSTES = config.RUTA_AJUSTES   # un solo archivo de ajustes para todo

EXT_DATOS = (".csv", ".tsv", ".xlsx", ".xls")
EXT_IMAGEN = (".png", ".jpg", ".jpeg", ".webp")
MAX_ADJUNTO = 25 * 1024 * 1024  # 25 MB

AJUSTES_POR_DEFECTO = {
    "modelo": config.MODELO,
    "modelo_vision": config.MODELO_VISION,
    "pensar": bool(config.PENSAR),
    "tema": "system",
    "confirmaciones": True,
    "altavoz": False,
    "modo_plan": False,
}


# ======================= Bus de eventos (SSE) =======================

class Bus:
    """Reparte eventos a todas las pestañas/ventanas conectadas."""

    def __init__(self):
        self._colas = []
        self._lock = threading.Lock()

    def suscribir(self):
        cola = queue.Queue(maxsize=5000)
        with self._lock:
            self._colas.append(cola)
        return cola

    def desuscribir(self, cola):
        with self._lock:
            if cola in self._colas:
                self._colas.remove(cola)

    def publicar(self, tipo, **datos):
        evento = {"tipo": tipo, **datos}
        with self._lock:
            for cola in list(self._colas):
                try:
                    cola.put_nowait(evento)
                except queue.Full:
                    pass


# ======================= Estado de la aplicación =======================

class Estado:
    def __init__(self):
        self.lock = threading.Lock()
        self.ajustes = cargar_ajustes()
        config.MODELO = self.ajustes["modelo"]
        config.MODELO_VISION = self.ajustes["modelo_vision"]
        config.PENSAR = self.ajustes["pensar"]
        self.generando = False
        self.cancelar = threading.Event()
        self.pendientes = {}          # id -> {"evento", "respuesta", "datos"}
        self.modo_conversacion = False
        self.grabadora = None
        chats = agente.listar_chats()
        self.chat_actual = chats[0]["id"] if chats else agente.crear_chat()
        self.mensajes = agente.cargar_chat(self.chat_actual)


def cargar_ajustes():
    ajustes = dict(AJUSTES_POR_DEFECTO)
    try:
        with open(RUTA_AJUSTES, encoding="utf-8") as f:
            ajustes.update({k: v for k, v in json.load(f).items() if k in ajustes})
    except (OSError, ValueError):
        pass
    if ajustes["tema"] not in ("light", "dark", "system"):
        ajustes["tema"] = "system"
    return ajustes


def guardar_ajustes(ajustes):
    try:
        with open(RUTA_AJUSTES, "w", encoding="utf-8") as f:
            json.dump(ajustes, f, ensure_ascii=False, indent=2)
    except OSError as e:
        registro.error(f"No se pudieron guardar los ajustes: {e}")


def turnos_para_mostrar(mensajes):
    """Turnos de texto listos para la página (sin el contenido de los adjuntos)."""
    turnos = []
    for m in mensajes:
        rol = m.get("role") if isinstance(m, dict) else getattr(m, "role", None)
        texto = m.get("content") if isinstance(m, dict) else getattr(m, "content", None)
        if rol not in ("user", "assistant") or not texto:
            continue
        turno = {"rol": rol, "texto": texto}
        if rol == "user" and agente.MARCA_PETICION in texto:
            cabecera, peticion = texto.split(agente.MARCA_PETICION, 1)
            turno["texto"] = peticion.strip()
            if "'" in cabecera:
                turno["adjunto"] = cabecera.split("'")[1]
        turnos.append(turno)
    return turnos


def nombre_usuario():
    try:
        datos = memoria._cargar()
        return datos.get("nombre") or datos.get("mi nombre") or ""
    except Exception:
        return ""


def construir_peticion(texto, adjunto):
    """Une el texto del usuario con el archivo adjunto (si lo hay)."""
    if not adjunto:
        return texto
    nombre, ruta, tipo = adjunto.get("nombre", ""), adjunto.get("ruta", ""), adjunto.get("tipo")
    try:
        ruta_real = ruta_segura(ruta)
    except ValueError:
        return texto
    if tipo in ("datos", "imagen"):
        herramienta = ("analizar_tabla o graficar_tabla (especialista datos)" if tipo == "datos"
                       else "leer_imagen (especialista datos)")
        return (f"El usuario adjuntó el archivo '{nombre}' en la ruta: {ruta_real}\n"
                f"Para trabajar con él usa {herramienta} y pásale esa ruta.\n\n"
                f"{agente.MARCA_PETICION} {texto}")
    contenido = lectura.leer_archivo(str(ruta_real))[:6000]
    return (f"Contenido del archivo adjunto '{nombre}':\n{contenido}\n\n"
            f"{agente.MARCA_PETICION} {texto}")


# ======================= Aplicación Flask =======================

def crear_app(token=None, hosts_permitidos=None):
    """Crea la app. Devuelve (app, estado, bus)."""
    token = token or secrets.token_urlsafe(24)
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_ADJUNTO
    estado = Estado()
    bus = Bus()

    # ---------- seguridad ----------

    @app.before_request
    def proteger():
        host = (request.host or "").split(":")[0]
        if hosts_permitidos is not None and host not in hosts_permitidos:
            abort(403)
        if request.path.startswith("/api/"):
            recibido = request.headers.get("X-Token") or request.args.get("token")
            if not recibido or not secrets.compare_digest(recibido, token):
                abort(403)

    @app.after_request
    def cabeceras(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        if request.path == "/":
            resp.headers["Content-Security-Policy"] = (
                "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                "script-src 'self'; connect-src 'self'; font-src 'self'; object-src 'none'; "
                "base-uri 'none'; frame-ancestors 'none'"
            )
            resp.headers["Cache-Control"] = "no-store"
        return resp

    # ---------- página ----------

    @app.get("/")
    def inicio():
        with open(os.path.join(ESTATICOS, "index.html"), encoding="utf-8") as f:
            html = f.read()
        return Response(html.replace("{{TOKEN}}", token), mimetype="text/html")

    @app.get("/static/<path:archivo>")
    def estaticos(archivo):
        return send_from_directory(ESTATICOS, archivo, max_age=0)

    @app.get("/favicon.ico")
    def favicon():
        return send_from_directory(os.path.join(RAIZ, "assets"), "icono.svg",
                                   mimetype="image/svg+xml")

    # ---------- utilidades internas ----------

    def publicar_chats():
        bus.publicar("chats", chats=agente.listar_chats(), actual=estado.chat_actual)

    def esperar_respuesta(tipo, datos):
        """Publica una pregunta (confirmar/plan) y espera a que la página responda."""
        ident = uuid.uuid4().hex
        evento = threading.Event()
        estado.pendientes[ident] = {"evento": evento, "respuesta": None,
                                    "datos": {"tipo": tipo, "id": ident, **datos}}
        bus.publicar(tipo, id=ident, **datos)
        try:
            while not evento.wait(0.25):
                if estado.cancelar.is_set():
                    return False
            return bool(estado.pendientes[ident]["respuesta"])
        finally:
            estado.pendientes.pop(ident, None)
            bus.publicar("pregunta_cerrada", id=ident)

    def confirmador(nombre, argumentos):
        if not estado.ajustes["confirmaciones"]:
            return True
        return esperar_respuesta("confirmar", {
            "herramienta": nombre,
            "argumentos": {k: str(v) for k, v in dict(argumentos).items()},
        })

    def planificador(plan):
        return esperar_respuesta("plan", {"plan": plan})

    def hablar(texto):
        def _hablar():
            try:
                from tools import habla
                habla.decir(texto)
            except Exception as e:
                bus.publicar("aviso", nivel="error", texto=f"No se pudo leer en voz alta: {e}")
        threading.Thread(target=_hablar, daemon=True).start()

    def ejecutar_peticion(peticion, texto_visible, adjunto_nombre=None, hablar_al_final=None):
        """Corre el sistema multiagente (en un hilo de trabajo)."""
        estado.cancelar.clear()
        bus.publicar("inicio", texto=texto_visible, adjunto=adjunto_nombre, chat=estado.chat_actual)
        try:
            respuesta, _ = root.procesar(
                peticion, estado.mensajes,
                confirmador=confirmador,
                on_token=lambda t: bus.publicar("token", texto=t),
                on_evento=lambda ev: bus.publicar("actividad", actividad=ev),
                cancelado=estado.cancelar.is_set,
                planificador=planificador if estado.ajustes["modo_plan"] else None,
            )
        except Exception as e:
            registro.error(f"Error procesando la petición: {e}")
            respuesta = f"Ocurrió un error inesperado: {e}"
        agente.guardar_chat(estado.chat_actual, estado.mensajes)
        estado.generando = False  # antes de "fin", para poder enviar enseguida otro mensaje
        bus.publicar("fin", texto=respuesta, cancelado=estado.cancelar.is_set())
        publicar_chats()
        debe_hablar = estado.ajustes["altavoz"] if hablar_al_final is None else hablar_al_final
        if debe_hablar and respuesta and not estado.cancelar.is_set():
            hablar(respuesta)
        return respuesta

    def trabajar(peticion, texto_visible, adjunto_nombre):
        try:
            ejecutar_peticion(peticion, texto_visible, adjunto_nombre)
        finally:
            estado.generando = False

    # ---------- API: estado y chats ----------

    @app.get("/api/estado")
    def api_estado():
        return jsonify({
            "ajustes": estado.ajustes,
            "chat_actual": estado.chat_actual,
            "chats": agente.listar_chats(),
            "turnos": turnos_para_mostrar(estado.mensajes),
            "generando": estado.generando,
            "modo_conversacion": estado.modo_conversacion,
            "nombre": nombre_usuario(),
            "especialistas": [{"nombre": a.nombre, "descripcion": a.descripcion}
                              for a in ESPECIALISTAS.values()],
            "pendientes": [p["datos"] for p in estado.pendientes.values()],
        })

    def ocupado():
        return estado.generando or estado.modo_conversacion

    @app.post("/api/chats")
    def api_nuevo_chat():
        with estado.lock:
            if ocupado():
                return jsonify(error="Espera a que el agente termine."), 409
            estado.chat_actual = agente.crear_chat()
            estado.mensajes = agente.cargar_chat(estado.chat_actual)
        publicar_chats()
        return jsonify(id=estado.chat_actual, turnos=[])

    @app.get("/api/chats/<chat_id>")
    def api_abrir_chat(chat_id):
        with estado.lock:
            if chat_id != estado.chat_actual:
                if ocupado():
                    return jsonify(error="Espera a que el agente termine."), 409
                if chat_id not in {c["id"] for c in agente.listar_chats()}:
                    return jsonify(error="Ese chat no existe."), 404
                estado.chat_actual = chat_id
                estado.mensajes = agente.cargar_chat(chat_id)
        return jsonify(id=chat_id, turnos=turnos_para_mostrar(estado.mensajes))

    @app.delete("/api/chats/<chat_id>")
    def api_borrar_chat(chat_id):
        with estado.lock:
            if ocupado() and chat_id == estado.chat_actual:
                return jsonify(error="No se puede borrar el chat mientras el agente trabaja."), 409
            agente.borrar_chat(chat_id)
            if chat_id == estado.chat_actual:
                chats = agente.listar_chats()
                estado.chat_actual = chats[0]["id"] if chats else agente.crear_chat()
                estado.mensajes = agente.cargar_chat(estado.chat_actual)
        publicar_chats()
        return jsonify(actual=estado.chat_actual, turnos=turnos_para_mostrar(estado.mensajes))

    # ---------- API: conversación ----------

    @app.post("/api/enviar")
    def api_enviar():
        datos = request.get_json(silent=True) or {}
        texto = (datos.get("texto") or "").strip()
        adjunto = datos.get("adjunto")
        if not texto:
            return jsonify(error="Escribe un mensaje."), 400
        with estado.lock:
            if ocupado():
                return jsonify(error="El agente ya está trabajando."), 409
            estado.generando = True
        peticion = construir_peticion(texto, adjunto)
        nombre_adj = adjunto.get("nombre") if adjunto else None
        threading.Thread(target=trabajar, args=(peticion, texto, nombre_adj), daemon=True).start()
        return jsonify(ok=True)

    @app.post("/api/detener")
    def api_detener():
        estado.cancelar.set()
        return jsonify(ok=True)

    @app.post("/api/responder")
    def api_responder():
        datos = request.get_json(silent=True) or {}
        pendiente = estado.pendientes.get(datos.get("id"))
        if not pendiente:
            return jsonify(error="Esa pregunta ya no está activa."), 404
        pendiente["respuesta"] = bool(datos.get("valor"))
        pendiente["evento"].set()
        return jsonify(ok=True)

    @app.post("/api/adjuntar")
    def api_adjuntar():
        archivo = request.files.get("archivo")
        if not archivo or not archivo.filename:
            return jsonify(error="No llegó ningún archivo."), 400
        base, ext = os.path.splitext(archivo.filename)
        ext = ext.lower()
        nombre = nombre_archivo_seguro(base) + ext
        destino = ruta_segura(os.path.join("adjuntos", nombre))
        destino.parent.mkdir(parents=True, exist_ok=True)
        archivo.save(str(destino))
        tipo = "datos" if ext in EXT_DATOS else "imagen" if ext in EXT_IMAGEN else "texto"
        if tipo == "texto" and ext not in lectura.EXTENSIONES_TEXTO + (".pdf",):
            destino.unlink(missing_ok=True)
            return jsonify(error=f"No sé leer archivos {ext or 'sin extensión'}. "
                                 "Usa PDF, texto, CSV, Excel o imágenes."), 415
        return jsonify(nombre=archivo.filename, ruta=str(destino.relative_to(BASE_DIR)), tipo=tipo)

    # ---------- API: ajustes ----------

    @app.get("/api/modelos")
    def api_modelos():
        modelos = agente.modelos_disponibles()
        for actual in (config.MODELO_VISION, config.MODELO):
            if actual not in modelos:
                modelos = [actual] + modelos
        return jsonify(modelos=modelos, actual=config.MODELO, vision=config.MODELO_VISION)

    @app.post("/api/ajustes")
    def api_ajustes():
        datos = request.get_json(silent=True) or {}
        nuevos = dict(estado.ajustes)
        for clave, defecto in AJUSTES_POR_DEFECTO.items():
            if clave in datos:
                valor = datos[clave]
                nuevos[clave] = bool(valor) if isinstance(defecto, bool) else str(valor)
        if nuevos["tema"] not in ("light", "dark", "system"):
            nuevos["tema"] = "system"
        estado.ajustes = nuevos
        config.MODELO = nuevos["modelo"]
        config.MODELO_VISION = nuevos["modelo_vision"]
        config.PENSAR = nuevos["pensar"]
        guardar_ajustes(nuevos)
        bus.publicar("ajustes", ajustes=nuevos)
        return jsonify(ajustes=nuevos)

    # ---------- API: voz ----------

    @app.post("/api/voz/iniciar")
    def api_voz_iniciar():
        if estado.grabadora is not None:
            return jsonify(ok=True)
        try:
            from tools import voz
            grabadora = voz.Grabadora()
            grabadora.iniciar()
            estado.grabadora = grabadora
        except Exception as e:
            return jsonify(error=f"No se pudo usar el micrófono: {e}"), 500
        return jsonify(ok=True)

    @app.post("/api/voz/detener")
    def api_voz_detener():
        grabadora, estado.grabadora = estado.grabadora, None
        if grabadora is None:
            return jsonify(texto="")
        try:
            return jsonify(texto=grabadora.detener())
        except Exception as e:
            return jsonify(error=f"No se pudo transcribir: {e}"), 500

    def bucle_conversacion():
        from tools import escucha, habla
        bus.publicar("conversacion", activo=True, escuchando=True)
        while estado.modo_conversacion:
            try:
                texto = escucha.escuchar_una_frase(parar=lambda: not estado.modo_conversacion)
            except Exception as e:
                bus.publicar("aviso", nivel="error", texto=f"No se pudo escuchar: {e}")
                break
            if not estado.modo_conversacion:
                break
            if not texto:
                continue
            if texto.lower().strip() in ("salir", "detente", "adiós", "adios", "para", "para ya"):
                break
            bus.publicar("conversacion", activo=True, escuchando=False)
            estado.generando = True
            try:
                respuesta = ejecutar_peticion(texto, texto, hablar_al_final=False)
            finally:
                estado.generando = False
            if respuesta and estado.modo_conversacion:
                try:
                    habla.decir(respuesta)
                except Exception as e:
                    bus.publicar("aviso", nivel="error", texto=f"No se pudo hablar: {e}")
            bus.publicar("conversacion", activo=True, escuchando=True)
        estado.modo_conversacion = False
        bus.publicar("conversacion", activo=False, escuchando=False)

    @app.post("/api/conversacion")
    def api_conversacion():
        activo = bool((request.get_json(silent=True) or {}).get("activo"))
        with estado.lock:
            if activo and not estado.modo_conversacion:
                if estado.generando:
                    return jsonify(error="Espera a que el agente termine."), 409
                estado.modo_conversacion = True
                threading.Thread(target=bucle_conversacion, daemon=True).start()
            elif not activo:
                estado.modo_conversacion = False
                estado.cancelar.set()
        return jsonify(activo=estado.modo_conversacion)

    # ---------- eventos en vivo ----------

    @app.get("/api/eventos")
    def api_eventos():
        cola = bus.suscribir()

        def generar():
            try:
                yield "retry: 1500\n\n"
                while True:
                    try:
                        evento = cola.get(timeout=15)
                    except queue.Empty:
                        yield ": sigo aquí\n\n"
                        continue
                    yield f"data: {json.dumps(evento, ensure_ascii=False, default=str)}\n\n"
            finally:
                bus.desuscribir(cola)

        return Response(generar(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return app, estado, bus
