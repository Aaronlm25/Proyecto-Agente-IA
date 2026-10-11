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
    lista = "\n".join(
        f"- {a.nombre}: {a.descripcion} (sus herramientas: {', '.join(a.funciones)})"
        for a in ESPECIALISTAS.values()
    )
    texto = (
        "Eres el agente coordinador (root) de un sistema multiagente que automatiza tareas "
        f"en la computadora del usuario. Hoy es {hoy()}.\n\n"
        "TUS ÚNICAS HERRAMIENTAS son `delegar` y las de memoria (`recordar`, `recuperar`, "
        "`olvidar`, `listar_recuerdos`). Tú NO puedes crear notas, eventos, carpetas, "
        "analizar tablas, leer imágenes, buscar en internet ni usar la terminal: para todo "
        "eso llama a `delegar` con el especialista adecuado.\n\n"
        "Cómo trabajas:\n"
        "1. Si es una charla o una pregunta que puedes responder tú mismo, responde "
        "directamente sin delegar.\n"
        "2. Si la petición tiene VARIAS PARTES (por ejemplo «busca X y guárdalo en una "
        "nota», o «crea un proyecto y una nota»), haz UNA delegación POR CADA PARTE, en "
        "orden, cada una al especialista que sabe hacerla. Un especialista solo puede "
        "hacer lo que permiten sus herramientas.\n"
        "3. Los especialistas NO ven la conversación: en `tarea` incluye todos los datos "
        "(nombres, rutas, fechas AAAA-MM-DD, horas HH:MM, URLs y el texto completo que haya "
        "que guardar).\n"
        "4. Cada resultado te dice qué herramientas usó el especialista. Si una parte de "
        "la petición no se hizo (por ejemplo, no aparece crear_nota), delégala ahora al "
        "especialista correcto.\n"
        "5. Si el usuario rechazó o canceló una acción, díselo claramente y no la repitas.\n"
        "6. Si el usuario menciona un dato personal importante (nombre, gustos, proyectos), "
        "guárdalo con `recordar`.\n"
        "7. Al terminar, responde en español con un resumen claro de lo hecho (rutas de "
        "archivos, resultados, enlaces). Nunca digas que algo se hizo si ningún "
        "especialista lo hizo.\n\n"
        "Ejemplo: «Busca qué es Python y guarda un resumen en una nota llamada python»\n"
        "  1) delegar(agente=\"web\", tarea=\"Busca qué es Python y resume lo principal con la fuente\")\n"
        "  2) delegar(agente=\"organizador\", tarea=\"Crea una nota llamada python con este "
        "contenido: <el resumen que devolvió web>\")\n"
        "  3) Responder al usuario con lo hecho.\n\n"
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
        ctx.avisar(f"[root] → {agente}: {tarea}", tipo="delegacion", agente=agente, tarea=tarea)
        antes = len(ctx.usadas)
        resultado = especialista.ejecutar(tarea, ctx)
        if len(resultado) > config.MAX_RESULTADO:
            resultado = resultado[:config.MAX_RESULTADO] + " … (recortado)"
        # Le decimos al root qué herramientas se usaron DE VERDAD, para que no se
        # crea un "ya guardé la nota" de un especialista que no puede guardar notas.
        usadas = [f"{h}{'' if ok else ' (falló)'}" for a, h, ok in ctx.usadas[antes:] if a == agente]
        return f"{resultado}\n\n[Herramientas que usó {agente}: {', '.join(usadas) or 'ninguna'}]"

    def redirigir(nombre_herramienta, dueno):
        """Si el root llama directo a una herramienta de un especialista (cosa que los
        modelos pequeños hacen), se la pasamos al especialista que sí la tiene."""
        def funcion(**argumentos):
            detalle = ", ".join(f"{k}={v!r}" for k, v in argumentos.items())
            return delegar(dueno, f"Usa la herramienta {nombre_herramienta} con: {detalle}")
        return funcion

    redirecciones = {
        herramienta: redirigir(herramienta, nombre)
        for nombre, especialista in ESPECIALISTAS.items()
        for herramienta in especialista.funciones
    }

    esquemas_mem, funciones_mem = herramientas_de(*HERRAMIENTAS_MEMORIA)
    return Agente(
        nombre="root",
        descripcion="Coordinador",
        prompt=prompt_root,
        esquemas=[_tool_delegar()] + esquemas_mem,
        # Las redirecciones no se le ofrecen al modelo (no están en `esquemas`);
        # solo atrapan las llamadas directas que haga por error.
        funciones={**redirecciones, "delegar": delegar, **funciones_mem},
        max_pasos=config.MAX_PASOS_ROOT,
        temperatura=0.3,
        pista_vacia=("Tu respuesta anterior llegó vacía. Recuerda: tus únicas herramientas son "
                     "delegar y las de memoria. Llama a delegar con un JSON válido "
                     "{\"agente\": ..., \"tarea\": ...} o responde con texto al usuario."),
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
             cancelado=None, planificador=None, on_evento=None):
    """Procesa una petición del usuario con el sistema multiagente.

    - mensajes: historial del chat (se modifica en el sitio).
    - confirmador(nombre, args) -> bool: autoriza herramientas sensibles.
      Si es None, las herramientas sensibles se RECHAZAN (seguro por defecto).
    - on_token(texto): fragmentos de la respuesta del root (streaming).
    - on_accion(linea): actividad de los agentes ("[web] buscar_web(...) -> ...").
    - on_evento(dict): la misma actividad en datos estructurados (para la interfaz web).
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
    ctx = Contexto(confirmador=confirmador, on_accion=on_accion, cancelado=cancelado,
                   on_evento=on_evento)

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
