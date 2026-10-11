"""
agentes/base.py

Las dos piezas de cualquier agente del sistema:

  - Contexto: lo que comparte TODA una petición del usuario (confirmaciones,
    avisos a la interfaz, cancelación, contador de delegaciones y lista de
    acciones). El root y los especialistas usan el mismo contexto, así las
    confirmaciones y el botón "Detener" funcionan en todos los niveles.

  - Agente: un modelo + un prompt + un grupo de herramientas + el bucle
    "pensar -> llamar herramienta -> ver resultado -> repetir".
"""

import json
import inspect

import ollama

import registro
from agentes import config


class Contexto:
    def __init__(self, confirmador=None, on_accion=None, cancelado=None, on_evento=None):
        self.confirmador = confirmador    # (nombre, args) -> bool
        self.on_accion = on_accion        # (linea) -> None           texto para mostrar
        self.on_evento = on_evento        # (dict) -> None            datos estructurados
        self.cancelado = cancelado        # () -> bool
        self.delegaciones = 0
        self.acciones = []

    # ---------- utilidades ----------

    def esta_cancelado(self) -> bool:
        return bool(self.cancelado and self.cancelado())

    def avisar(self, linea: str, **info) -> None:
        """Registra una línea de actividad y la manda a la interfaz.

        `info` son datos estructurados (tipo, agente, herramienta...) para las
        interfaces que quieren dibujar la actividad con más detalle."""
        self.acciones.append(linea)
        for callback, dato in ((self.on_accion, linea), (self.on_evento, {**info, "linea": linea})):
            if callback:
                try:
                    callback(dato)
                except Exception as e:
                    registro.error(f"Callback de actividad falló: {e}")

    # ---------- ejecución de herramientas ----------

    def ejecutar_herramienta(self, agente, nombre, argumentos) -> str:
        """Ejecuta una herramienta de `agente` con confirmación, validación y registro."""
        args = _normalizar_argumentos(argumentos)
        funcion = agente.funciones.get(nombre)

        if funcion is None:
            resultado = (f"Error: la herramienta '{nombre}' no existe para el agente "
                         f"'{agente.nombre}'. Disponibles: {', '.join(agente.funciones)}")
            registro.error(resultado)
        elif nombre in agente.sensibles and not self._confirmar(nombre, args):
            resultado = f"Acción '{nombre}' cancelada: el usuario no la autorizó."
        else:
            args = _ajustar_a_esquema(args, agente.esquema_de(nombre), funcion)
            try:
                resultado = funcion(**args)
            except Exception as e:
                resultado = f"Error al ejecutar {nombre}: {e}"
                registro.error(f"[{agente.nombre}] {nombre}({args}): {e}")

        resultado = str(resultado)
        registro.accion(f"[{agente.nombre}] {nombre}({args}) -> {resultado[:300]}")
        if nombre == "delegar":
            self.avisar(f"[{args.get('agente', '?')}] terminó: {resultado[:300]}",
                        tipo="termino", agente=args.get("agente", "?"), resultado=resultado[:1500])
        else:
            self.avisar(f"[{agente.nombre}] {nombre}({_corto(args)}) -> {resultado[:300]}",
                        tipo="herramienta", agente=agente.nombre, herramienta=nombre,
                        argumentos=_corto(args, 300), resultado=resultado[:1500],
                        ok=not _es_fallo(resultado))
        return resultado

    def _confirmar(self, nombre, args) -> bool:
        # Sin confirmador NO se ejecutan herramientas sensibles (seguro por defecto).
        if self.confirmador is None:
            return False
        try:
            return bool(self.confirmador(nombre, args))
        except Exception as e:
            registro.error(f"El confirmador falló: {e}")
            return False


class Agente:
    def __init__(self, nombre, descripcion, prompt, esquemas, funciones,
                 sensibles=(), modelo=None, max_pasos=None, temperatura=0.2):
        self.nombre = nombre
        self.descripcion = descripcion
        self._prompt = prompt                  # str o función que devuelve str
        self.esquemas = list(esquemas)
        self.funciones = dict(funciones)
        self.sensibles = set(sensibles)
        self._modelo = modelo                  # None = usar config.MODELO
        self.max_pasos = max_pasos or config.MAX_PASOS_ESPECIALISTA
        self.temperatura = temperatura

    # ---------- propiedades dinámicas ----------

    @property
    def prompt(self) -> str:
        return self._prompt() if callable(self._prompt) else self._prompt

    @property
    def modelo(self) -> str:
        return self._modelo or config.MODELO

    def esquema_de(self, nombre):
        for e in self.esquemas:
            if e["function"]["name"] == nombre:
                return e
        return None

    # ---------- bucle principal ----------

    def bucle(self, mensajes, ctx, on_token=None, max_pasos=None) -> str:
        """Bucle del agente sobre `mensajes` (se modifica en el sitio).

        Devuelve el texto final del modelo. Corta si se cancela o si llega al
        límite de pasos (así nunca se queda en un bucle infinito)."""
        max_pasos = max_pasos or self.max_pasos
        for _ in range(max_pasos):
            contenido, tool_calls = "", []
            try:
                respuesta = ollama.chat(
                    model=self.modelo, messages=mensajes,
                    tools=self.esquemas or None, stream=True,
                    options={"num_ctx": config.NUM_CTX, "temperature": self.temperatura},
                )
                for parte in respuesta:
                    if ctx.esta_cancelado():
                        mensajes.append({"role": "assistant", "content": contenido})
                        return contenido or "(generación detenida)"
                    msg = parte.message
                    if getattr(msg, "content", None):
                        contenido += msg.content
                        if on_token:
                            on_token(msg.content)
                    if getattr(msg, "tool_calls", None):
                        tool_calls.extend(msg.tool_calls)
            except Exception as e:
                registro.error(f"[{self.nombre}] Error al contactar el modelo: {e}")
                return f"Error al contactar el modelo ({self.modelo}): {e}"

            asistente = {"role": "assistant", "content": contenido}
            if tool_calls:
                asistente["tool_calls"] = [
                    {"function": {"name": t.function.name, "arguments": t.function.arguments}}
                    for t in tool_calls
                ]
            mensajes.append(asistente)

            if not tool_calls:
                return contenido

            for t in tool_calls:
                if ctx.esta_cancelado():
                    return contenido or "(generación detenida)"
                resultado = ctx.ejecutar_herramienta(self, t.function.name, t.function.arguments)
                mensajes.append({"role": "tool", "tool_name": t.function.name, "content": resultado})

        registro.error(f"[{self.nombre}] Llegó al límite de {max_pasos} pasos.")
        return (f"[{self.nombre}] Llegué al límite de {max_pasos} pasos sin terminar. "
                f"Último resultado: {_ultimo_resultado(mensajes)}")

    def ejecutar(self, tarea, ctx) -> str:
        """Resuelve UNA subtarea con un historial nuevo (el especialista no ve el chat)."""
        mensajes = [{"role": "system", "content": self.prompt},
                    {"role": "user", "content": tarea}]
        texto = self.bucle(mensajes, ctx).strip()
        if not texto:
            # Algunos modelos no escriben resumen final: devolvemos lo último que pasó.
            texto = f"Hecho. Último resultado: {_ultimo_resultado(mensajes)}"
        return texto


# ---------- funciones auxiliares ----------

def _normalizar_argumentos(argumentos) -> dict:
    """Los argumentos llegan como dict, pero algunos modelos los mandan como texto JSON."""
    if isinstance(argumentos, str):
        try:
            argumentos = json.loads(argumentos)
        except json.JSONDecodeError:
            return {}
    return dict(argumentos or {})


def _ajustar_a_esquema(args, esquema, funcion) -> dict:
    """Corrige errores típicos de modelos pequeños:
    - números enviados como texto ("2" -> 2)
    - listas enviadas como texto ("a, b" -> ["a", "b"])
    - argumentos inventados que la función no acepta (se descartan)."""
    propiedades = (esquema or {}).get("function", {}).get("parameters", {}).get("properties", {})
    ajustados = {}
    for clave, valor in args.items():
        tipo = propiedades.get(clave, {}).get("type")
        try:
            if tipo == "integer" and isinstance(valor, (str, float)):
                valor = int(float(valor))
            elif tipo == "number" and isinstance(valor, str):
                valor = float(valor)
            elif tipo == "array" and isinstance(valor, str):
                try:
                    valor = json.loads(valor)
                except json.JSONDecodeError:
                    valor = [v.strip() for v in valor.split(",") if v.strip()]
        except (ValueError, TypeError):
            pass  # se deja como vino; la función devolverá un error claro
        ajustados[clave] = valor

    try:
        parametros = inspect.signature(funcion).parameters
        if not any(p.kind == p.VAR_KEYWORD for p in parametros.values()):
            ajustados = {k: v for k, v in ajustados.items() if k in parametros}
    except (TypeError, ValueError):
        pass
    return ajustados


def _ultimo_resultado(mensajes) -> str:
    for m in reversed(mensajes):
        rol = m.get("role") if isinstance(m, dict) else getattr(m, "role", None)
        if rol == "tool":
            contenido = m.get("content") if isinstance(m, dict) else m.content
            return str(contenido)[:500]
    return "(ninguno)"


def _es_fallo(resultado: str) -> bool:
    inicio = resultado[:40].lower()
    return inicio.startswith(("error", "rechazado", "acción '", "no se pudo", "no pude",
                              "no encontré", "no existe", "formato inválido"))


def _corto(args, maximo=150) -> str:
    texto = ", ".join(f"{k}={v!r}" for k, v in args.items())
    return texto if len(texto) <= maximo else texto[:maximo] + "…"
