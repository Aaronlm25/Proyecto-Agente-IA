#!/usr/bin/env python3
"""
scripts/probar_con_ollama.py

Prueba el sistema multiagente con tu Ollama REAL (no con el modelo simulado
de tests/). Corre una batería de peticiones típicas, comprueba de verdad lo
que pasó (archivos creados, fechas, a qué especialista se delegó...) y deja
un reporte en pruebas_reales/<fecha>/reporte.md.

Uso:
    python scripts/probar_con_ollama.py                     # todas las pruebas
    python scripts/probar_con_ollama.py --modelo qwen2.5:14b
    python scripts/probar_con_ollama.py --solo 4,8,13       # solo algunas
    python scripts/probar_con_ollama.py --sin-web           # sin internet
    python scripts/probar_con_ollama.py --repetir 3         # mide qué tan constante es
    python scripts/probar_con_ollama.py --ver               # muestra la actividad en vivo
    python scripts/probar_con_ollama.py --lista             # lista las pruebas y sale

No toca tu workspace/ ni tus recuerdos: todo se hace en pruebas_reales/<fecha>/.
"""

import os
import re
import sys
import json
import time
import argparse
import datetime
import unicodedata
from pathlib import Path
from dataclasses import dataclass, field

RAIZ = Path(__file__).resolve().parent.parent
CARPETA = RAIZ / "pruebas_reales" / datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
WS = CARPETA / "workspace"

# Debe definirse ANTES de importar las herramientas del agente.
os.environ["AGENTE_WORKSPACE"] = str(WS)
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)


# ============================ Comprobaciones ============================

def _normal(texto):
    """Minúsculas y sin acentos, para comparar textos con tolerancia."""
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def delega_a(*agentes):
    def comprobar(r):
        faltan = [a for a in agentes if a not in r.delegaciones]
        return True if not faltan else f"no delegó a: {', '.join(faltan)} (delegó a: {r.delegaciones or 'nadie'})"
    return (f"delega a {' y '.join(agentes)}", comprobar)


def no_delega():
    return ("responde sin delegar",
            lambda r: True if not r.delegaciones else f"delegó sin necesidad a: {r.delegaciones}")


def usa(herramienta):
    return (f"usa {herramienta}",
            lambda r: True if any(h["herramienta"] == herramienta for h in r.herramientas)
            else f"no usó {herramienta} (usó: {[h['herramienta'] for h in r.herramientas] or 'ninguna'})")


def existe(patron, descripcion=None):
    def comprobar(r):
        encontrados = list(WS.glob(patron))
        return True if encontrados else f"no existe {patron}"
    return (descripcion or f"crea {patron}", comprobar)


def no_existe(patron, descripcion):
    return (descripcion, lambda r: True if not list(WS.glob(patron)) else f"existe {patron} y no debería")


def menciona(*palabras, alguna=False):
    def comprobar(r):
        t = _normal(r.texto)
        presentes = [p for p in palabras if _normal(p) in t]
        ok = presentes if alguna else len(presentes) == len(palabras)
        return True if ok else f"la respuesta no menciona {' / '.join(palabras)}"
    return (f"la respuesta menciona {' o '.join(palabras) if alguna else ', '.join(palabras)}", comprobar)


def pidio_confirmacion():
    return ("pide permiso antes de usar la terminal",
            lambda r: True if r.confirmaciones else "no pidió confirmación")


def evento_ics(fecha, hora):
    def comprobar(r):
        archivos = list(WS.glob("calendario/*.ics"))
        if not archivos:
            return "no se creó ningún .ics"
        esperado = f"DTSTART:{fecha.replace('-', '')}T{hora.replace(':', '')}00"
        for a in archivos:
            if esperado in a.read_text(encoding="utf-8", errors="ignore"):
                return True
        inicios = [ln for a in archivos for ln in a.read_text(errors="ignore").splitlines()
                   if ln.startswith("DTSTART")]
        return f"se esperaba {esperado}, se encontró {inicios}"
    return (f"evento el {fecha} a las {hora}", comprobar)


def nota_con_contenido(patron, minimo=60):
    def comprobar(r):
        notas = list(WS.glob(patron))
        if not notas:
            return f"no existe {patron}"
        largo = max(len(n.read_text(encoding="utf-8", errors="ignore")) for n in notas)
        return True if largo >= minimo else f"la nota es muy corta ({largo} caracteres)"
    return (f"nota {patron} con contenido", comprobar)


def memoria_contiene(palabra):
    def comprobar(r):
        from tools import memoria
        return True if _normal(palabra) in _normal(memoria.listar_recuerdos()) else \
            f"la memoria no contiene '{palabra}': {memoria.listar_recuerdos()}"
    return (f"guarda '{palabra}' en la memoria", comprobar)


def nada_fuera_del_workspace():
    def comprobar(r):
        fuera = [p for p in CARPETA.rglob("*fuera*") if WS not in p.parents]
        fuera += list(RAIZ.glob("fuera*")) + list(RAIZ.parent.glob("fuera*"))
        return True if not fuera else f"se escribió fuera del workspace: {fuera}"
    return ("no escribe fuera del workspace", comprobar)


# ============================ Escenarios ============================

@dataclass
class Escenario:
    id: int
    nombre: str
    peticion: str
    comprobaciones: list
    preparar: object = None          # función opcional que prepara archivos
    confirmar: bool = True           # qué responder si pide permiso
    necesita: set = field(default_factory=set)   # {"web", "vision"}


def preparar_ventas():
    (WS / "ventas.csv").write_text(
        "mes,producto,unidades\n"
        "enero,Teclado,120\nenero,Mouse,80\nenero,Monitor,30\n"
        "febrero,Teclado,90\nfebrero,Mouse,110\nfebrero,Monitor,45\n"
        "marzo,Teclado,150\nmarzo,Mouse,70\nmarzo,Monitor,60\n",
        encoding="utf-8")


def preparar_archivos():
    for ruta in ("docs/manual.pdf", "docs/notas.txt", "fotos/playa.jpg", "informe-final.pdf"):
        (WS / ruta).parent.mkdir(parents=True, exist_ok=True)
        (WS / ruta).write_bytes(b"x")


def preparar_memoria():
    from tools import memoria
    memoria._guardar({})   # empieza limpia para que no haya datos contradictorios
    memoria.recordar("lenguaje favorito", "Python")


def preparar_repo():
    (WS / "tienda-online").mkdir(exist_ok=True)


def preparar_imagen():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(6, 3))
    fig.text(0.5, 0.5, "VENTAS TOTALES 2026: 4,750", ha="center", va="center", fontsize=22)
    fig.savefig(WS / "cartel.png", dpi=100)
    plt.close(fig)


def escenarios():
    manana = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    return [
        Escenario(1, "Charla sin herramientas", "Hola, ¿qué cosas puedes hacer por mí?",
                  [no_delega()]),
        Escenario(2, "Guardar un dato personal",
                  "Me llamo Aaron y mi lenguaje de programación favorito es Rust. Recuérdalo.",
                  [usa("recordar"), memoria_contiene("rust")]),
        Escenario(3, "Usar la memoria", "¿Cuál es mi lenguaje de programación favorito?",
                  [no_delega(), menciona("python")], preparar=preparar_memoria),
        Escenario(4, "Evento con fecha relativa",
                  "Agéndame una reunión con Luis mañana a las 5 de la tarde",
                  [delega_a("organizador"), usa("crear_evento"), evento_ics(manana, "17:00")]),
        Escenario(5, "Nota con contenido",
                  "Crea una nota llamada ideas con tres ideas para un blog de programación",
                  [delega_a("organizador"), nota_con_contenido("notas/ideas*.md")]),
        Escenario(6, "Proyecto con configuración",
                  "Crea un proyecto llamado tienda-online y genérale configuración web",
                  [delega_a("archivos"), existe("tienda-online/src"), existe("tienda-online/index.html")]),
        Escenario(7, "Buscar archivos", "¿Qué archivos PDF tengo en mi workspace?",
                  [delega_a("archivos"), usa("buscar_archivos"), menciona("manual", "informe")],
                  preparar=preparar_archivos),
        Escenario(8, "Analizar un CSV",
                  "Revisa el archivo ventas.csv: ¿qué producto vendió más unidades en total y cuántas?",
                  [delega_a("datos"), usa("analizar_tabla"), menciona("teclado", "360")],
                  preparar=preparar_ventas),
        Escenario(9, "Gráfica de un CSV",
                  "Haz una gráfica de barras con el total de unidades por producto usando ventas.csv",
                  [delega_a("datos"), usa("graficar_tabla"), existe("graficas/*.png", "crea la gráfica PNG")],
                  preparar=preparar_ventas),
        Escenario(10, "Terminal con permiso",
                  "Usa la terminal para decirme qué versión de Python está instalada",
                  [delega_a("sistema"), pidio_confirmacion(), menciona("3.")], confirmar=True),
        Escenario(11, "Terminal rechazada",
                  "Inicializa un repositorio git en la carpeta tienda-online",
                  [delega_a("sistema"), pidio_confirmacion(),
                   no_existe("tienda-online/.git", "no crea el repositorio si lo rechazo"),
                   menciona("cancel", "autoriz", "permiso", "rechaz", alguna=True)],
                  preparar=preparar_repo, confirmar=False),
        Escenario(12, "Búsqueda en internet",
                  "Busca en internet cuál es la versión estable más reciente de Python y dame la fuente",
                  [delega_a("web"), usa("buscar_web"), menciona("http", "python.org", alguna=True)],
                  necesita={"web"}),
        Escenario(13, "Varios agentes: web + nota",
                  "Busca qué es Ollama y guarda un resumen corto en una nota llamada ollama",
                  [delega_a("web", "organizador"), nota_con_contenido("notas/ollama*.md", 40)],
                  necesita={"web"}),
        Escenario(14, "Varios agentes: proyecto + nota",
                  "Crea un proyecto llamado blog y una nota llamada pendientes-blog con 3 tareas para empezarlo",
                  [delega_a("archivos", "organizador"), existe("blog/README.md"),
                   nota_con_contenido("notas/pendientes*.md", 40)]),
        Escenario(15, "Seguridad: ruta tramposa",
                  "Crea una nota con el título ../../fuera que diga hola",
                  [nada_fuera_del_workspace()]),
        Escenario(16, "Leer una imagen",
                  "Lee el texto que aparece en la imagen cartel.png de mi workspace",
                  [delega_a("datos"), usa("leer_imagen"), menciona("4,750", "4750", "4.750", alguna=True)],
                  preparar=preparar_imagen, necesita={"vision"}),
    ]


# ============================ Ejecución ============================

class Resultado:
    def __init__(self):
        self.texto = ""
        self.eventos = []
        self.confirmaciones = []
        self.segundos = 0.0
        self.error = None
        self.avisos = []         # errores internos registrados (respuestas vacías, etc.)

    @property
    def delegaciones(self):
        return [e["agente"] for e in self.eventos if e.get("tipo") == "delegacion"]

    @property
    def herramientas(self):
        return [e for e in self.eventos if e.get("tipo") == "herramienta"]

    @property
    def tareas(self):
        return [(e["agente"], e.get("tarea", "")) for e in self.eventos if e.get("tipo") == "delegacion"]


def tiene_caracteres_raros(texto):
    """qwen a veces mezcla chino o cirílico: lo detectamos."""
    return bool(re.search(r"[぀-ヿ㐀-鿿가-힯Ѐ-ӿ]", texto or ""))


def correr(esc, args):
    from agentes import root
    r = Resultado()
    limite = time.time() + args.limite

    def confirmador(nombre, argumentos):
        r.confirmaciones.append(nombre)
        if args.ver:
            print(f"      ¿{nombre}? -> {'permitido' if esc.confirmar else 'rechazado'}")
        return esc.confirmar

    def on_evento(ev):
        r.eventos.append(ev)
        if args.ver:
            print(f"      {ev['linea'][:150]}")

    import logging

    class Recolector(logging.Handler):
        def emit(self, record):
            r.avisos.append(record.getMessage()[:300])

    recolector = Recolector(level=logging.ERROR)
    logging.getLogger("agente").addHandler(recolector)

    if esc.preparar:
        esc.preparar()
    inicio = time.time()
    try:
        r.texto, _ = root.procesar(esc.peticion, [], confirmador=confirmador,
                                   on_evento=on_evento,
                                   cancelado=lambda: time.time() > limite)
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    finally:
        logging.getLogger("agente").removeHandler(recolector)
    r.segundos = time.time() - inicio
    if time.time() > limite:
        r.error = f"superó el límite de {args.limite} s"

    comprobaciones = []
    for descripcion, funcion in esc.comprobaciones:
        try:
            salida = funcion(r)
        except Exception as e:  # noqa: BLE001
            salida = f"error al comprobar: {e}"
        comprobaciones.append((descripcion, salida is True, "" if salida is True else str(salida)))
    if r.error:
        comprobaciones.append(("termina sin errores", False, r.error))
    comprobaciones.append(("responde en español",
                           bool(r.texto.strip()) and not tiene_caracteres_raros(r.texto),
                           "" if r.texto.strip() and not tiene_caracteres_raros(r.texto)
                           else "respuesta vacía o con caracteres de otros alfabetos"))
    return r, comprobaciones


def verificar_ollama(modelo, necesita_vision):
    """Comprueba que Ollama responde y que los modelos están instalados."""
    import ollama
    from agentes import config
    try:
        lista = ollama.list()
    except Exception as e:  # noqa: BLE001
        print(f"✗ No pude conectar con Ollama: {e}\n  Ábrelo con:  ollama serve")
        sys.exit(1)
    nombres = [(m.get("model") or m.get("name")) for m in lista.get("models", [])]
    if modelo not in nombres and f"{modelo}:latest" not in nombres:
        print(f"✗ El modelo '{modelo}' no está instalado. Instálalo con:  ollama pull {modelo}")
        print(f"  Modelos instalados: {', '.join(nombres) or 'ninguno'}")
        sys.exit(1)
    vision = config.MODELO_VISION in nombres or f"{config.MODELO_VISION}:latest" in nombres
    if necesita_vision and not vision:
        print(f"• Sin modelo de visión ({config.MODELO_VISION}): se salta la prueba de imágenes.")
    print(f"✓ Ollama responde. Modelo: {modelo}")
    print("  Cargando el modelo (la primera vez tarda)…", end="", flush=True)
    t = time.time()
    try:
        ollama.chat(model=modelo, messages=[{"role": "user", "content": "Responde solo: ok"}],
                    options={"num_ctx": config.NUM_CTX})
    except Exception as e:  # noqa: BLE001
        print(f"\n✗ El modelo no respondió: {e}")
        sys.exit(1)
    print(f" listo en {time.time() - t:.0f} s\n")
    return vision


def hay_internet():
    import socket
    try:
        socket.create_connection(("duckduckgo.com", 443), timeout=4).close()
        return True
    except OSError:
        return False


def escribir_reporte(filas, args, modelo, total_seg):
    from agentes import config
    aprobadas = sum(1 for f in filas if f["ok"])
    lineas = [
        "# Reporte de pruebas reales",
        "",
        f"- Fecha: {datetime.datetime.now():%Y-%m-%d %H:%M}",
        f"- Modelo: `{modelo}` · contexto: {config.NUM_CTX} tokens",
        f"- Resultado: **{aprobadas} de {len(filas)}** ejecuciones correctas",
        f"- Tiempo total: {total_seg / 60:.1f} min",
        f"- Sistema: {sys.platform}, Python {sys.version.split()[0]}",
        "",
        "| # | Prueba | Resultado | Tiempo | Delegó a |",
        "|---|---|---|---|---|",
    ]
    for f in filas:
        estado = "✅" if f["ok"] else "❌"
        lineas.append(f"| {f['id']} | {f['nombre']}{f['vuelta']} | {estado} {f['aciertos']} | "
                      f"{f['segundos']:.0f} s | {', '.join(f['delegaciones']) or '—'} |")
    lineas += ["", "## Detalle de las que fallaron", ""]
    fallidas = [f for f in filas if not f["ok"]]
    if not fallidas:
        lineas.append("Ninguna. 🎉")
    for f in fallidas:
        lineas += [
            f"### {f['id']}. {f['nombre']}{f['vuelta']}",
            "",
            f"**Petición:** {f['peticion']}",
            "",
            "**Comprobaciones:**",
        ]
        lineas += [f"- {'✅' if ok else '❌'} {d}{f' — {m}' if m else ''}" for d, ok, m in f["comprobaciones"]]
        lineas += ["", "**Delegaciones:**"]
        lineas += [f"- {a}: {t}" for a, t in f["tareas"]] or ["- ninguna"]
        lineas += ["", "**Herramientas:**"]
        lineas += [f"- [{h['agente']}] {h['herramienta']}({h.get('argumentos', '')}) → "
                   f"{h.get('resultado', '')[:200].replace(chr(10), ' ')}" for h in f["herramientas"]] or ["- ninguna"]
        if f.get("avisos"):
            lineas += ["", "**Avisos internos:**"] + [f"- {a}" for a in f["avisos"]]
        lineas += ["", "**Respuesta del agente:**", "", "> " + (f["texto"][:1200] or "(vacía)").replace("\n", "\n> "), ""]
    (CARPETA / "reporte.md").write_text("\n".join(lineas), encoding="utf-8")
    (CARPETA / "reporte.json").write_text(json.dumps(filas, ensure_ascii=False, indent=2, default=str),
                                          encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Pruebas del agente con Ollama real")
    parser.add_argument("--modelo", help="modelo de Ollama (por defecto, el de ajustes.json)")
    parser.add_argument("--solo", help="números de prueba separados por comas, ej: 4,8,13")
    parser.add_argument("--sin-web", action="store_true", help="saltar las pruebas que usan internet")
    parser.add_argument("--repetir", type=int, default=1, help="veces que se repite cada prueba")
    parser.add_argument("--limite", type=int, default=600, help="segundos máximos por prueba")
    parser.add_argument("--ver", action="store_true", help="mostrar la actividad de los agentes")
    parser.add_argument("--lista", action="store_true", help="listar las pruebas y salir")
    args = parser.parse_args()

    todos = escenarios()
    if args.lista:
        for e in todos:
            extra = f"  (necesita {', '.join(sorted(e.necesita))})" if e.necesita else ""
            print(f"{e.id:>2}. {e.nombre}: «{e.peticion}»{extra}")
        return

    WS.mkdir(parents=True, exist_ok=True)

    from agentes import config
    from tools import memoria
    memoria.RUTA = str(CARPETA / "recuerdos.json")   # no tocar tus recuerdos reales

    modelo = args.modelo
    if not modelo:
        try:
            modelo = json.loads((RAIZ / "ajustes.json").read_text(encoding="utf-8")).get("modelo")
        except (OSError, ValueError):
            pass
    config.MODELO = modelo or config.MODELO

    elegidos = todos
    if args.solo:
        numeros = {int(n) for n in args.solo.split(",") if n.strip().isdigit()}
        elegidos = [e for e in todos if e.id in numeros]

    vision = verificar_ollama(config.MODELO, any("vision" in e.necesita for e in elegidos))
    internet = not args.sin_web and hay_internet()
    if not args.sin_web and not internet:
        print("• Sin conexión a internet: se saltan las pruebas web.\n")

    filas = []
    inicio_total = time.time()
    total = len(elegidos) * args.repetir
    en_vivo = sys.stdout.isatty() and not args.ver   # sobrescribe la línea de progreso
    try:
        ejecutar_todos(elegidos, args, internet, vision, filas, total, en_vivo)
    except KeyboardInterrupt:
        print("\n\nInterrumpido: guardo el reporte con lo que alcanzó a correr.")

    total_seg = time.time() - inicio_total
    if not filas:
        print("No se ejecutó ninguna prueba.")
        return
    escribir_reporte(filas, args, config.MODELO, total_seg)
    aprobadas = sum(1 for f in filas if f["ok"])
    print(f"\nResultado: {aprobadas} de {len(filas)} correctas en {total_seg / 60:.1f} min")
    print(f"Reporte:   {CARPETA / 'reporte.md'}")
    print("Si algo falló, pega el contenido de reporte.md en el chat para ajustar los prompts.")


def ejecutar_todos(elegidos, args, internet, vision, filas, total, en_vivo):
    n = 0
    for esc in elegidos:
        if "web" in esc.necesita and not internet:
            continue
        if "vision" in esc.necesita and not vision:
            continue
        for vuelta in range(args.repetir):
            n += 1
            etiqueta = f"[{n:>2}/{total}] {esc.id:>2}. {esc.nombre}"
            print(f"{etiqueta} …", end="" if en_vivo else "\n", flush=True)
            r, comprobaciones = correr(esc, args)
            aciertos = sum(1 for _, ok, _ in comprobaciones if ok)
            ok = aciertos == len(comprobaciones)
            print(f"{chr(13) + etiqueta if en_vivo else '   '} {'✅' if ok else '❌'} "
                  f"{aciertos}/{len(comprobaciones)}  ({r.segundos:.0f} s)")
            for d, bien, m in comprobaciones:
                if not bien:
                    print(f"      ✗ {d}: {m}")
            filas.append({
                "id": esc.id, "nombre": esc.nombre,
                "vuelta": f" (vuelta {vuelta + 1})" if args.repetir > 1 else "",
                "peticion": esc.peticion, "ok": ok, "aciertos": f"{aciertos}/{len(comprobaciones)}",
                "segundos": r.segundos, "delegaciones": r.delegaciones, "tareas": r.tareas,
                "herramientas": r.herramientas, "texto": r.texto, "avisos": r.avisos,
                "comprobaciones": comprobaciones,
            })


if __name__ == "__main__":
    main()
