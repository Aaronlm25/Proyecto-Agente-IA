"""
agentes/root.py

El agente ROOT (coordinador). Es el único que:
  - habla con el usuario y conserva el historial del chat,
  - guarda y consulta los recuerdos del usuario,
  - DELEGA subtareas a los especialistas con la herramienta `delegar`.

Los especialistas nunca pueden delegar (no tienen esa herramienta), así que
no hay riesgo de que se llamen entre ellos en bucle.

Uso:
    from agentes import root
    texto, acciones = root.procesar("crea un proyecto web llamado tienda", mensajes)
"""

import ollama

import registro
from agentes import config
from agentes.base import Agente, Contexto
from agentes.especialistas import ESPECIALISTAS, hoy
from tools import memoria
from tools.catalogo import herramientas_de

HERRAMIENTAS_MEMORIA = ("recordar", "recuperar", "olvidar", "listar_recuerdos")


def _tool_delegar():
    return {
        "type": "function",
        "function": {
            "name": "delegar",
            "description": "Encarga UNA subtarea a un agente especialista y devuelve su resultado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agente": {
                        "type": "string",
                        "enum": list(ESPECIALISTAS),
                        "description": "Nombre del especialista que hará la subtarea.",
                    },
                    "tarea": {
                        "type": "string",
                        "description": (
                            "Instrucción COMPLETA y autocontenida. El especialista NO ve la "
                            "conversación: incluye nombres, rutas, fechas (AAAA-MM-DD), horas "
                            "(HH:MM), URLs y cualquier texto que necesite."
                        ),
                    },
                },
                "required": ["agente", "tarea"],
            },
        },
    }


def prompt_root() -> str:
    lista = "\n".join(f"- {a.nombre}: {a.descripcion}" for a in ESPECIALISTAS.values())
    texto = (
        "Eres el agente coordinador (root) de un sistema multiagente que automatiza tareas "
        f"en la computadora del usuario. Hoy es {hoy()}.\n\n"
        "Cómo trabajas:\n"
        "1. Si es una charla o una pregunta que puedes responder tú mismo, responde "
        "directamente sin delegar.\n"
        "2. Si hay que hacer algo, divide la petición en subtareas y usa `delegar` con el "
        "especialista adecuado, UNA subtarea por llamada.\n"
        "3. Los especialistas NO ven la conversación: en `tarea` incluye todos los datos "
        "necesarios (nombres, rutas, fechas AAAA-MM-DD, horas HH:MM, URLs, textos).\n"
        "4. Usa el resultado de cada especialista para preparar la siguiente subtarea. "
        "Si uno falla, intenta otra forma o explícale el problema al usuario.\n"
        "5. Si el usuario menciona un dato personal importante (nombre, gustos, proyectos), "
        "guárdalo con `recordar`.\n"
        "6. Al terminar, responde al usuario en español con un resumen claro de lo hecho "
        "(rutas de archivos, resultados, enlaces). Nunca inventes resultados: informa solo "
        "lo que devolvieron los especialistas.\n\n"
        f"Especialistas disponibles:\n{lista}"
    )
    try:
        recuerdos = memoria.contexto_memoria()
        if recuerdos:
            texto += "\n\n" + recuerdos
    except Exception as e:
        registro.error(f"No se pudo leer la memoria: {e}")
    return texto


def mensaje_sistema() -> dict:
    return {"role": "system", "content": prompt_root()}


def _crear_root(ctx: Contexto) -> Agente:
    """Crea el root para UNA petición (la función delegar necesita el contexto)."""

    def delegar(agente: str, tarea: str) -> str:
        especialista = ESPECIALISTAS.get(agente)
        if especialista is None:
            return f"No existe el especialista '{agente}'. Opciones: {', '.join(ESPECIALISTAS)}."
        if ctx.delegaciones >= config.MAX_DELEGACIONES:
            return ("Se alcanzó el límite de delegaciones para esta petición. "
                    "Responde al usuario con lo que ya tienes.")
        if not (tarea or "").strip():
            return "La tarea está vacía: describe qué debe hacer el especialista."
        ctx.delegaciones += 1
        ctx.avisar(f"[root] → {agente}: {tarea}")
        resultado = especialista.ejecutar(tarea, ctx)
        if len(resultado) > config.MAX_RESULTADO:
            resultado = resultado[:config.MAX_RESULTADO] + " … (recortado)"
        return resultado

    esquemas_mem, funciones_mem = herramientas_de(*HERRAMIENTAS_MEMORIA)
    return Agente(
        nombre="root",
        descripcion="Coordinador",
        prompt=prompt_root,
        esquemas=[_tool_delegar()] + esquemas_mem,
        funciones={"delegar": delegar, **funciones_mem},
        max_pasos=config.MAX_PASOS_ROOT,
        temperatura=0.3,
    )


def _generar_plan(mensajes) -> str:
    """Pide al root (sin herramientas) los pasos que dará y a qué especialistas delegará."""
    nudge = {
        "role": "user",
        "content": (
            "Antes de hacer nada, escribe una lista numerada y breve (máximo 6 pasos) de lo "
            "que vas a hacer para cumplir mi última petición, indicando en cada paso a qué "
            "especialista delegarás. Escribe ÚNICAMENTE en español, sin caracteres de otros "
            "alfabetos. Sin saludos ni explicaciones. No ejecutes ninguna herramienta."
        ),
    }
    try:
        resp = ollama.chat(model=config.MODELO, messages=mensajes + [nudge],
                           options={"temperature": 0.3, "num_ctx": config.NUM_CTX})
        return resp.message.content or "(sin plan)"
    except Exception as e:
        registro.error(f"Error al generar el plan: {e}")
        return f"(No se pudo generar el plan: {e})"


def procesar(peticion, mensajes, confirmador=None, on_token=None, on_accion=None,
             cancelado=None, planificador=None):
    """Procesa una petición del usuario con el sistema multiagente.

    - mensajes: historial del chat (se modifica en el sitio).
    - confirmador(nombre, args) -> bool: autoriza herramientas sensibles.
      Si es None, las herramientas sensibles se RECHAZAN (seguro por defecto).
    - on_token(texto): fragmentos de la respuesta del root (streaming).
    - on_accion(linea): actividad de los agentes ("[web] buscar_web(...) -> ...").
    - cancelado() -> bool: si devuelve True, todo se detiene.
    - planificador(plan) -> bool: modo plan; si devuelve False no se ejecuta nada.

    Devuelve (texto_respuesta, lista_de_acciones)."""
    # El prompt del sistema se regenera en cada petición (fecha, recuerdos, especialistas).
    sistema = mensaje_sistema()
    if mensajes and isinstance(mensajes[0], dict) and mensajes[0].get("role") == "system":
        mensajes[0] = sistema
    else:
        mensajes.insert(0, sistema)

    mensajes.append({"role": "user", "content": peticion})
    ctx = Contexto(confirmador=confirmador, on_accion=on_accion, cancelado=cancelado)

    if planificador is not None:
        plan = _generar_plan(mensajes)
        if not planificador(plan):
            mensajes.append({"role": "assistant", "content": plan})
            return plan, ctx.acciones
        mensajes.append({"role": "assistant", "content": f"Plan:\n{plan}"})
        mensajes.append({"role": "user", "content": "Aprobado. Ejecuta el plan."})

    root = _crear_root(ctx)
    texto = root.bucle(mensajes, ctx, on_token=on_token)
    return texto, ctx.acciones
