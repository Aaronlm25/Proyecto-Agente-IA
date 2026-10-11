/* =====================================================================
   Agente de IA Local — lógica de la interfaz
   Habla con interfaz/servidor.py:  POST /api/...  y  eventos en vivo (SSE)
   ===================================================================== */
"use strict";

const TOKEN = document.querySelector('meta[name="token"]').content;
const $ = (selector, raiz = document) => raiz.querySelector(selector);

const ui = {
  app: $("#app"),
  principal: $(".principal"),
  conversacion: $("#conversacion"),
  hilo: $("#hilo"),
  bienvenida: $("#bienvenida"),
  saludo: $("#saludo"),
  titulo: $("#tituloChat"),
  conexion: $("#estadoConexion"),
  lista: $("#listaChats"),
  buscar: $("#buscar"),
  entrada: $("#entrada"),
  form: $("#compositor"),
  enviar: $("#botonEnviar"),
  adjuntar: $("#botonAdjuntar"),
  archivo: $("#archivo"),
  adjunto: $("#adjunto"),
  adjuntoNombre: $("#adjuntoNombre"),
  dictar: $("#botonDictar"),
  conversar: $("#botonConversacion"),
  altavoz: $("#botonAltavoz"),
  sugerencias: $("#sugerencias"),
  avisos: $("#avisos"),
  dConfirmar: $("#dialogoConfirmar"),
  dPlan: $("#dialogoPlan"),
  dAjustes: $("#dialogoAjustes"),
};

const estado = {
  ajustes: {},
  chats: [],
  chatActual: null,
  generando: false,
  nombre: "",
  adjunto: null,          // {nombre, ruta, tipo}
  mensaje: null,          // mensaje del agente que se está escribiendo
  esperandoInicio: false, // ya dibujamos el mensaje del usuario localmente
  ultimoEnviado: "",
  grabando: false,
  conversacion: false,
  preguntas: [],          // confirmaciones / planes pendientes
  preguntaVisible: null,
};

const NOMBRES_AGENTE = {
  root: "coordinador", archivos: "archivos", organizador: "organizador",
  sistema: "sistema", web: "web", datos: "datos",
};

const SUGERENCIAS = [
  { agente: "organizador", texto: "Agenda una reunión mañana a las 10:00" },
  { agente: "archivos", texto: "Crea un proyecto web llamado portafolio" },
  { agente: "web", texto: "Busca las novedades de Python y resúmelas" },
  { agente: "datos", texto: "Analiza un CSV y hazme una gráfica", archivo: true },
];

/* ============================ Utilidades ============================ */

async function api(ruta, { metodo = "GET", datos, form } = {}) {
  const opciones = { method: metodo, headers: { "X-Token": TOKEN } };
  if (form) opciones.body = form;
  else if (datos !== undefined) {
    opciones.headers["Content-Type"] = "application/json";
    opciones.body = JSON.stringify(datos);
  }
  const resp = await fetch(ruta, opciones);
  let json = {};
  try { json = await resp.json(); } catch { /* respuesta sin cuerpo */ }
  if (!resp.ok) throw new Error(json.error || `Error ${resp.status}`);
  return json;
}

function crear(etiqueta, clase, texto) {
  const el = document.createElement(etiqueta);
  if (clase) el.className = clase;
  if (texto !== undefined) el.textContent = texto;
  return el;
}

function icono(nombre, clase = "ico") {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("class", clase);
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(ns, "use");
  use.setAttribute("href", `#i-${nombre}`);
  svg.appendChild(use);
  return svg;
}

function cambiarIcono(boton, nombre) {
  boton.querySelector("use").setAttribute("href", `#i-${nombre}`);
}

function avisar(texto, nivel = "info") {
  const toast = crear("div", `aviso-toast ${nivel}`);
  toast.append(icono(nivel === "error" ? "alert" : "check"), crear("span", "", texto));
  ui.avisos.append(toast);
  setTimeout(() => toast.remove(), nivel === "error" ? 6000 : 3000);
}

function unirLista(items) {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} y ${items.at(-1)}`;
}

function cercaDelFinal() {
  const c = ui.conversacion;
  return c.scrollHeight - c.scrollTop - c.clientHeight < 140;
}

function bajar(forzar = false) {
  if (forzar || cercaDelFinal()) {
    requestAnimationFrame(() => { ui.conversacion.scrollTop = ui.conversacion.scrollHeight; });
  }
}

/* ============================ Markdown ============================ */

marked.setOptions({ gfm: true, breaks: false });

function pintarMarkdown(el, texto, final = false) {
  el.innerHTML = DOMPurify.sanitize(marked.parse(texto || ""), { ADD_ATTR: ["target"] });
  el.querySelectorAll("a[href]").forEach((a) => { a.target = "_blank"; a.rel = "noopener noreferrer"; });
  el.querySelectorAll("pre > code").forEach((code) => {
    const pre = code.parentElement;
    const lenguaje = (code.className.match(/language-([\w+#-]+)/) || [])[1] || "texto";
    const marco = crear("div", "bloque-codigo");
    const barra = crear("div", "barra");
    barra.append(crear("span", "", lenguaje));
    const copiar = crear("button", "icono-boton mini");
    copiar.type = "button";
    copiar.setAttribute("aria-label", "Copiar código");
    copiar.title = "Copiar código";
    copiar.append(icono("copy"));
    copiar.addEventListener("click", () => copiarTexto(code.textContent, copiar));
    barra.append(copiar);
    pre.replaceWith(marco);
    marco.append(barra, pre);
    if (final && window.hljs && lenguaje !== "texto") {
      try { hljs.highlightElement(code); } catch { /* lenguaje desconocido */ }
    }
  });
}

async function copiarTexto(texto, boton) {
  try {
    await navigator.clipboard.writeText(texto);
  } catch {
    const area = crear("textarea");
    area.value = texto;
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
  if (boton) {
    cambiarIcono(boton, "check");
    setTimeout(() => cambiarIcono(boton, "copy"), 1400);
  }
}

/* ============================ Mensajes ============================ */

function actualizarVacio() {
  const vacio = ui.hilo.children.length === 0;
  ui.principal.classList.toggle("vacia", vacio);
  ui.bienvenida.hidden = !vacio;
  if (vacio) ui.saludo.textContent = saludo();
}

function saludo() {
  const h = new Date().getHours();
  const base = h < 6 ? "Buenas noches" : h < 12 ? "Buenos días" : h < 20 ? "Buenas tardes" : "Buenas noches";
  return estado.nombre ? `${base}, ${estado.nombre}` : base;
}

function agregarUsuario(texto, adjunto) {
  const m = crear("div", "mensaje usuario");
  if (adjunto) {
    const et = crear("div", "etiqueta-adjunto");
    et.append(icono("file"), crear("span", "", adjunto));
    m.append(et);
  }
  m.append(crear("div", "burbuja", texto));
  ui.hilo.append(m);
  actualizarVacio();
  bajar(true);
}

class MensajeAgente {
  constructor({ pensando = true } = {}) {
    this.el = crear("div", "mensaje agente");
    this.cuerpo = crear("div", "cuerpo-mensaje");
    this.cuerpo.style.display = "contents";
    this.el.append(this.cuerpo);
    this.bloques = [];
    this.actual = null;
    this.pendiente = false;
    if (pensando) {
      this.pensando = crear("div", "pensando");
      const puntos = crear("span", "puntos");
      puntos.append(crear("i"), crear("i"), crear("i"));
      this.pensando.append(puntos, crear("span", "", "Pensando…"));
      this.cuerpo.append(this.pensando);
    }
    ui.hilo.append(this.el);
    actualizarVacio();
  }

  quitarPensando() {
    if (this.pensando) { this.pensando.remove(); this.pensando = null; }
  }

  bloqueTexto() {
    if (this.actual?.tipo !== "texto") {
      const el = crear("div", "prosa escribiendo");
      this.actual = { tipo: "texto", el, texto: "" };
      this.bloques.push(this.actual);
      this.quitarPensando();
      this.cuerpo.append(el);
    }
    return this.actual;
  }

  bloqueActividad() {
    if (this.actual?.tipo !== "actividad") {
      this.actual = new Actividad();
      this.bloques.push(this.actual);
      this.quitarPensando();
      // Los bloques de texto anteriores ya no van a crecer.
      this.bloques.filter((b) => b.tipo === "texto").forEach((b) => b.el.classList.remove("escribiendo"));
      this.cuerpo.append(this.actual.el);
    }
    return this.actual;
  }

  token(t) {
    const b = this.bloqueTexto();
    b.texto += t;
    if (!this.pendiente) {
      this.pendiente = true;
      requestAnimationFrame(() => {
        this.pendiente = false;
        pintarMarkdown(b.el, b.texto);
        bajar();
      });
    }
  }

  actividad(ev) {
    this.bloqueActividad().agregar(ev);
    bajar();
  }

  terminar(textoFinal, cancelado) {
    this.quitarPensando();
    const textos = this.bloques.filter((b) => b.tipo === "texto");
    if (!textos.some((b) => b.texto.trim()) && textoFinal) {
      this.actual = null;
      this.bloqueTexto().texto = textoFinal;
    }
    for (const b of this.bloques) {
      if (b.tipo === "texto") {
        b.el.classList.remove("escribiendo");
        pintarMarkdown(b.el, b.texto, true);
      } else {
        b.cerrar();
      }
    }
    if (cancelado) {
      const nota = crear("p", "pensando", "Detuviste la respuesta.");
      this.cuerpo.append(nota);
    }
    this.agregarAcciones();
    bajar();
  }

  agregarAcciones() {
    const texto = this.bloques.filter((b) => b.tipo === "texto").map((b) => b.texto).join("\n\n").trim();
    if (!texto) return;
    const barra = crear("div", "acciones-mensaje");
    const copiar = crear("button", "icono-boton mini");
    copiar.type = "button";
    copiar.title = "Copiar respuesta";
    copiar.setAttribute("aria-label", "Copiar respuesta");
    copiar.append(icono("copy"));
    copiar.addEventListener("click", () => copiarTexto(texto, copiar));
    barra.append(copiar);
    this.el.append(barra);
  }
}

/* ---------- Bloque de actividad de los agentes ---------- */

class Actividad {
  constructor() {
    this.tipo = "actividad";
    this.pasos = [];
    this.el = crear("div", "actividad abierta");
    this.resumen = crear("button", "actividad-resumen");
    this.resumen.type = "button";
    this.resumen.setAttribute("aria-expanded", "true");
    this.sellos = crear("span", "sellos");
    this.textoResumen = crear("span", "texto", "Repartiendo el trabajo…");
    this.cuenta = crear("span", "pasos");
    this.resumen.append(this.sellos, this.textoResumen, this.cuenta, icono("chevron", "ico chevron"));
    this.detalle = crear("div", "actividad-detalle");
    this.el.append(this.resumen, this.detalle);
    this.resumen.addEventListener("click", () => {
      const abierta = this.el.classList.toggle("abierta");
      this.resumen.setAttribute("aria-expanded", String(abierta));
    });
  }

  nuevoPaso(agente, tarea) {
    const el = crear("div", "paso");
    el.dataset.agente = agente;
    const sello = crear("span", "sello vivo", (NOMBRES_AGENTE[agente] || agente)[0]);
    const cuerpo = crear("div", "paso-cuerpo");
    const titulo = crear("div", "paso-titulo");
    const estadoTxt = crear("span", "estado", "trabajando…");
    titulo.append(crear("strong", "", NOMBRES_AGENTE[agente] || agente), estadoTxt);
    cuerpo.append(titulo);
    if (tarea) cuerpo.append(crear("div", "paso-tarea", tarea));
    const herramientas = crear("ul", "herramientas");
    cuerpo.append(herramientas);
    el.append(sello, cuerpo);
    this.detalle.append(el);
    const paso = { agente, tarea, el, sello, cuerpo, estadoTxt, herramientas, activo: true, n: 0 };
    this.pasos.push(paso);
    return paso;
  }

  pasoActivo(agente) {
    for (let i = this.pasos.length - 1; i >= 0; i--) {
      if (this.pasos[i].agente === agente && this.pasos[i].activo) return this.pasos[i];
    }
    return null;
  }

  agregar(ev) {
    if (ev.tipo === "delegacion") {
      this.nuevoPaso(ev.agente, ev.tarea);
    } else if (ev.tipo === "herramienta") {
      const paso = this.pasoActivo(ev.agente) || this.nuevoPaso(ev.agente, null);
      const li = crear("li", `herramienta${ev.ok === false ? " fallo" : ""}`);
      const det = crear("details");
      const sum = crear("summary", "", `${ev.herramienta}(${ev.argumentos || ""})`);
      const pre = crear("pre", "", ev.resultado || "");
      det.append(sum, pre);
      li.append(icono(ev.ok === false ? "x" : "check"), det);
      paso.herramientas.append(li);
      paso.n += 1;
      if (ev.agente === "root") this.cerrarPaso(paso);
    } else if (ev.tipo === "termino") {
      const paso = this.pasoActivo(ev.agente);
      if (paso) {
        if (ev.resultado) paso.cuerpo.append(crear("div", "paso-resultado", ev.resultado));
        this.cerrarPaso(paso);
      }
    }
    this.actualizarResumen();
  }

  cerrarPaso(paso) {
    paso.activo = false;
    paso.sello.classList.remove("vivo");
    paso.estadoTxt.textContent = paso.n === 1 ? "1 acción" : paso.n ? `${paso.n} acciones` : "listo";
  }

  agentes() {
    return [...new Set(this.pasos.map((p) => p.agente))];
  }

  actualizarResumen() {
    this.sellos.replaceChildren(...this.agentes().map((a) => {
      const s = crear("span", "sello", (NOMBRES_AGENTE[a] || a)[0]);
      s.dataset.agente = a;
      if (this.pasos.some((p) => p.agente === a && p.activo)) s.classList.add("vivo");
      return s;
    }));
    const activo = [...this.pasos].reverse().find((p) => p.activo);
    if (activo) {
      const nombre = NOMBRES_AGENTE[activo.agente] || activo.agente;
      this.textoResumen.textContent = activo.tarea ? `${nombre}: ${activo.tarea}` : `${nombre} está trabajando…`;
    } else {
      this.textoResumen.textContent = `Trabajó con ${unirLista(this.agentes().map((a) => NOMBRES_AGENTE[a] || a))}`;
    }
    const n = this.pasos.length;
    this.cuenta.textContent = n === 1 ? "1 paso" : `${n} pasos`;
  }

  cerrar() {
    this.pasos.filter((p) => p.activo).forEach((p) => this.cerrarPaso(p));
    this.actualizarResumen();
    this.el.classList.remove("abierta");
    this.resumen.setAttribute("aria-expanded", "false");
  }
}

/* ============================ Chats (barra lateral) ============================ */

function grupoFecha(iso) {
  const fecha = new Date(iso);
  if (isNaN(fecha)) return "Anteriores";
  const hoy = new Date(); hoy.setHours(0, 0, 0, 0);
  const dias = Math.floor((hoy - new Date(fecha.getFullYear(), fecha.getMonth(), fecha.getDate())) / 86400000);
  if (dias <= 0) return "Hoy";
  if (dias === 1) return "Ayer";
  if (dias < 7) return "Últimos 7 días";
  if (dias < 31) return "Este mes";
  return "Anteriores";
}

function pintarChats() {
  const filtro = ui.buscar.value.trim().toLowerCase();
  const chats = estado.chats.filter((c) => !filtro || c.titulo.toLowerCase().includes(filtro));
  ui.lista.replaceChildren();
  if (!chats.length) {
    ui.lista.append(crear("p", "lista-vacia", filtro ? "Ningún chat coincide con la búsqueda." : "Aún no hay chats."));
  }
  let grupo = null;
  for (const c of chats) {
    const g = grupoFecha(c.actualizado);
    if (g !== grupo) { ui.lista.append(crear("div", "grupo-fecha", g)); grupo = g; }
    const item = crear("div", `item-chat${c.id === estado.chatActual ? " activo" : ""}`);
    const abrir = crear("button", "abrir", c.titulo || "Nuevo chat");
    abrir.type = "button";
    abrir.title = c.titulo;
    if (c.id === estado.chatActual) abrir.setAttribute("aria-current", "page");
    abrir.addEventListener("click", () => abrirChat(c.id));
    const borrar = crear("button", "borrar");
    borrar.type = "button";
    borrar.title = "Borrar chat";
    borrar.setAttribute("aria-label", `Borrar el chat ${c.titulo}`);
    borrar.append(icono("trash"));
    borrar.addEventListener("click", () => borrarChat(c.id, c.titulo));
    item.append(abrir, borrar);
    ui.lista.append(item);
  }
  const actual = estado.chats.find((c) => c.id === estado.chatActual);
  ui.titulo.textContent = actual?.titulo || "Nuevo chat";
  document.title = actual && actual.titulo !== "Nuevo chat" ? `${actual.titulo} · Agente local` : "Agente de IA Local";
}

function pintarTurnos(turnos) {
  ui.hilo.replaceChildren();
  estado.mensaje = null;
  for (const t of turnos) {
    if (t.rol === "user") {
      agregarUsuario(t.texto, t.adjunto);
    } else {
      const m = new MensajeAgente({ pensando: false });
      m.bloqueTexto().texto = t.texto;
      m.terminar(t.texto, false);
    }
  }
  actualizarVacio();
  bajar(true);
}

async function abrirChat(id) {
  cerrarLateral();
  if (id === estado.chatActual) return;
  try {
    const r = await api(`/api/chats/${encodeURIComponent(id)}`);
    estado.chatActual = r.id;
    pintarTurnos(r.turnos);
    pintarChats();
    ui.entrada.focus();
  } catch (e) { avisar(e.message, "error"); }
}

async function nuevoChat() {
  cerrarLateral();
  try {
    const r = await api("/api/chats", { metodo: "POST" });
    estado.chatActual = r.id;
    pintarTurnos([]);
    ui.entrada.focus();
  } catch (e) { avisar(e.message, "error"); }
}

async function borrarChat(id, titulo) {
  if (!confirm(`¿Borrar el chat "${titulo}"? No se puede deshacer.`)) return;
  try {
    const r = await api(`/api/chats/${encodeURIComponent(id)}`, { metodo: "DELETE" });
    if (r.actual !== estado.chatActual) {
      estado.chatActual = r.actual;
      pintarTurnos(r.turnos);
    }
    avisar("Chat borrado");
  } catch (e) { avisar(e.message, "error"); }
}

/* ============================ Compositor ============================ */

function ajustarAltura() {
  ui.entrada.style.height = "auto";
  ui.entrada.style.height = `${Math.min(ui.entrada.scrollHeight, window.innerHeight * 0.4)}px`;
}

function actualizarBotonEnviar() {
  if (estado.generando) {
    ui.enviar.disabled = false;
    ui.enviar.classList.add("detener");
    ui.enviar.setAttribute("aria-label", "Detener");
    ui.enviar.title = "Detener (Esc)";
    cambiarIcono(ui.enviar, "stop");
  } else {
    ui.enviar.disabled = !ui.entrada.value.trim() || estado.conversacion;
    ui.enviar.classList.remove("detener");
    ui.enviar.setAttribute("aria-label", "Enviar");
    ui.enviar.title = "Enviar (Enter)";
    cambiarIcono(ui.enviar, "send");
  }
}

function ponerGenerando(valor) {
  estado.generando = valor;
  actualizarBotonEnviar();
}

async function enviar() {
  if (estado.generando) { detener(); return; }
  const texto = ui.entrada.value.trim();
  if (!texto) return;
  const adjunto = estado.adjunto;
  if (!ui.hilo.children.length) ui.titulo.textContent = texto.slice(0, 40);
  agregarUsuario(texto, adjunto?.nombre);
  estado.mensaje = new MensajeAgente();
  estado.esperandoInicio = true;
  estado.ultimoEnviado = texto;
  ui.entrada.value = "";
  ajustarAltura();
  quitarAdjunto();
  ponerGenerando(true);
  bajar(true);
  try {
    await api("/api/enviar", { metodo: "POST", datos: { texto, adjunto } });
  } catch (e) {
    estado.esperandoInicio = false;
    estado.mensaje?.terminar(`No se pudo enviar: ${e.message}`, false);
    estado.mensaje = null;
    ponerGenerando(false);
  }
}

async function detener() {
  try { await api("/api/detener", { metodo: "POST" }); } catch { /* ya terminó */ }
}

async function subirArchivo(archivo) {
  const form = new FormData();
  form.append("archivo", archivo);
  ui.adjunto.hidden = false;
  ui.adjuntoNombre.textContent = `Subiendo ${archivo.name}…`;
  try {
    estado.adjunto = await api("/api/adjuntar", { metodo: "POST", form });
    ui.adjuntoNombre.textContent = estado.adjunto.nombre;
  } catch (e) {
    quitarAdjunto();
    avisar(e.message, "error");
  }
}

function quitarAdjunto() {
  estado.adjunto = null;
  ui.adjunto.hidden = true;
  ui.archivo.value = "";
}

async function alternarDictado() {
  try {
    if (!estado.grabando) {
      await api("/api/voz/iniciar", { metodo: "POST" });
      estado.grabando = true;
      ui.dictar.classList.add("grabando");
      ui.dictar.setAttribute("aria-pressed", "true");
      ui.dictar.title = "Detener y transcribir";
    } else {
      estado.grabando = false;
      ui.dictar.classList.remove("grabando");
      ui.dictar.setAttribute("aria-pressed", "false");
      ui.dictar.title = "Dictar con el micrófono";
      const r = await api("/api/voz/detener", { metodo: "POST" });
      if (r.texto) {
        ui.entrada.value = (ui.entrada.value ? ui.entrada.value + " " : "") + r.texto;
        ajustarAltura();
        actualizarBotonEnviar();
        ui.entrada.focus();
      } else {
        avisar("No entendí nada. Prueba a hablar más cerca del micrófono.");
      }
    }
  } catch (e) {
    estado.grabando = false;
    ui.dictar.classList.remove("grabando");
    ui.dictar.setAttribute("aria-pressed", "false");
    avisar(e.message, "error");
  }
}

async function alternarConversacion() {
  try {
    await api("/api/conversacion", { metodo: "POST", datos: { activo: !estado.conversacion } });
  } catch (e) { avisar(e.message, "error"); }
}

function pintarConversacion(activo, escuchando) {
  estado.conversacion = activo;
  ui.conversar.setAttribute("aria-pressed", String(activo));
  ui.conversar.classList.toggle("grabando", activo && escuchando);
  ui.conversar.title = activo ? "Terminar la conversación por voz" : "Conversación por voz, manos libres";
  ui.entrada.disabled = activo;
  ui.entrada.placeholder = activo ? (escuchando ? "Te escucho… di «salir» para terminar" : "Pensando…") : "Escribe lo que necesitas…";
  actualizarBotonEnviar();
}

function pintarAltavoz() {
  const on = !!estado.ajustes.altavoz;
  ui.altavoz.setAttribute("aria-pressed", String(on));
  cambiarIcono(ui.altavoz, on ? "speaker" : "speaker-off");
  ui.altavoz.title = on ? "Dejar de leer las respuestas en voz alta" : "Leer las respuestas en voz alta";
}

async function guardarAjustes(cambios) {
  try {
    const r = await api("/api/ajustes", { metodo: "POST", datos: cambios });
    aplicarAjustes(r.ajustes);
  } catch (e) { avisar(e.message, "error"); }
}

function aplicarAjustes(ajustes) {
  estado.ajustes = ajustes;
  document.documentElement.dataset.theme = ajustes.tema || "system";
  pintarAltavoz();
}

/* ============================ Preguntas (confirmar / plan) ============================ */

function describirAccion(herramienta, args) {
  switch (herramienta) {
    case "ejecutar_comando":
      return {
        titulo: "¿Ejecutar este comando?",
        texto: `El especialista sistema quiere ejecutarlo en ${args.carpeta ? `workspace/${args.carpeta}` : "tu carpeta workspace"}.`,
        codigo: args.comando,
      };
    case "instalar_dependencia":
      return {
        titulo: "¿Instalar este paquete?",
        texto: "Se instalará en el entorno de Python o Node del agente.",
        codigo: `${args.gestor || "pip"} install ${args.paquete}`,
      };
    case "git":
      return {
        titulo: "¿Ejecutar esta acción de git?",
        texto: `En ${args.carpeta ? `workspace/${args.carpeta}` : "tu carpeta workspace"}.`,
        codigo: `git ${args.accion}${args.mensaje ? ` -m "${args.mensaje}"` : ""}`,
      };
    default:
      return { titulo: `¿Permitir ${herramienta}?`, texto: "El agente quiere hacer esta acción.", codigo: JSON.stringify(args, null, 2) };
  }
}

function encolarPregunta(p) {
  if (estado.preguntas.some((x) => x.id === p.id) || estado.preguntaVisible?.id === p.id) return;
  estado.preguntas.push(p);
  mostrarSiguientePregunta();
}

function mostrarSiguientePregunta() {
  if (estado.preguntaVisible || !estado.preguntas.length) return;
  const p = estado.preguntas.shift();
  estado.preguntaVisible = p;
  if (p.tipo === "confirmar") {
    const d = describirAccion(p.herramienta, p.argumentos || {});
    $("#confirmarTitulo").textContent = d.titulo;
    $("#confirmarTexto").textContent = d.texto;
    $("#confirmarCodigo").textContent = d.codigo;
    ui.dConfirmar.returnValue = "";
    ui.dConfirmar.showModal();
  } else {
    pintarMarkdown($("#planTexto"), p.plan, true);
    ui.dPlan.returnValue = "";
    ui.dPlan.showModal();
  }
}

async function responderPregunta(dialogo) {
  const p = estado.preguntaVisible;
  estado.preguntaVisible = null;
  if (p && !p.cerrada) {
    try {
      await api("/api/responder", { metodo: "POST", datos: { id: p.id, valor: dialogo.returnValue === "si" } });
    } catch { /* la pregunta ya expiró */ }
  }
  mostrarSiguientePregunta();
}

function cerrarPregunta(id) {
  estado.preguntas = estado.preguntas.filter((p) => p.id !== id);
  if (estado.preguntaVisible?.id === id) {
    estado.preguntaVisible.cerrada = true;
    (ui.dConfirmar.open ? ui.dConfirmar : ui.dPlan).close();
  }
}

ui.dConfirmar.addEventListener("close", () => responderPregunta(ui.dConfirmar));
ui.dPlan.addEventListener("close", () => responderPregunta(ui.dPlan));

/* ============================ Ajustes ============================ */

async function abrirAjustes() {
  cerrarLateral();
  const a = estado.ajustes;
  const select = $("#ajusteModelo");
  const selectVision = $("#ajusteModeloVision");
  select.replaceChildren(new Option(a.modelo, a.modelo, true, true));
  selectVision.replaceChildren(new Option(a.modelo_vision, a.modelo_vision, true, true));
  ui.dAjustes.querySelectorAll('input[name="tema"]').forEach((r) => { r.checked = r.value === a.tema; });
  $("#ajusteConfirmaciones").checked = !!a.confirmaciones;
  $("#ajustePensar").checked = !!a.pensar;
  $("#ajustePlan").checked = !!a.modo_plan;
  $("#ajusteAltavoz").checked = !!a.altavoz;
  ui.dAjustes.returnValue = "";
  ui.dAjustes.showModal();
  try {
    const r = await api("/api/modelos");
    select.replaceChildren(...r.modelos.map((m) => new Option(m, m, m === a.modelo, m === a.modelo)));
    selectVision.replaceChildren(...r.modelos.map((m) => new Option(m, m, m === a.modelo_vision, m === a.modelo_vision)));
  } catch { /* Ollama apagado: se queda el modelo actual */ }
}

ui.dAjustes.addEventListener("close", () => {
  if (ui.dAjustes.returnValue !== "guardar") {
    document.documentElement.dataset.theme = estado.ajustes.tema; // deshace la vista previa
    return;
  }
  guardarAjustes({
    modelo: $("#ajusteModelo").value,
    modelo_vision: $("#ajusteModeloVision").value,
    tema: ui.dAjustes.querySelector('input[name="tema"]:checked')?.value || "system",
    confirmaciones: $("#ajusteConfirmaciones").checked,
    pensar: $("#ajustePensar").checked,
    modo_plan: $("#ajustePlan").checked,
    altavoz: $("#ajusteAltavoz").checked,
  });
});
// Vista previa del tema al elegirlo
ui.dAjustes.querySelectorAll('input[name="tema"]').forEach((r) =>
  r.addEventListener("change", () => { document.documentElement.dataset.theme = r.value; }));

/* ============================ Eventos en vivo ============================ */

function manejarEvento(ev) {
  switch (ev.tipo) {
    case "inicio":
      if (estado.esperandoInicio) { estado.esperandoInicio = false; break; }
      // Mensaje que no salió de esta ventana (modo conversación u otra pestaña)
      if (ev.chat === estado.chatActual) {
        agregarUsuario(ev.texto, ev.adjunto);
        estado.mensaje = new MensajeAgente();
      }
      ponerGenerando(true);
      break;
    case "token":
      if (!estado.mensaje) estado.mensaje = new MensajeAgente();
      estado.mensaje.token(ev.texto);
      break;
    case "actividad":
      if (!estado.mensaje) estado.mensaje = new MensajeAgente();
      estado.mensaje.actividad(ev.actividad);
      break;
    case "fin":
      estado.mensaje?.terminar(ev.texto, ev.cancelado);
      estado.mensaje = null;
      ponerGenerando(false);
      if (!estado.conversacion) ui.entrada.focus();
      break;
    case "chats":
      estado.chats = ev.chats;
      if (ev.actual) estado.chatActual = ev.actual;
      pintarChats();
      break;
    case "confirmar":
    case "plan":
      encolarPregunta(ev);
      break;
    case "pregunta_cerrada":
      cerrarPregunta(ev.id);
      break;
    case "ajustes":
      aplicarAjustes(ev.ajustes);
      break;
    case "conversacion":
      pintarConversacion(ev.activo, ev.escuchando);
      break;
    case "aviso":
      avisar(ev.texto, ev.nivel);
      break;
  }
}

function conectarEventos() {
  const fuente = new EventSource(`/api/eventos?token=${encodeURIComponent(TOKEN)}`);
  let caida = false;
  fuente.onmessage = (e) => {
    try { manejarEvento(JSON.parse(e.data)); } catch (err) { console.error(err); }
  };
  fuente.onopen = () => {
    ui.conexion.hidden = true;
    if (caida) { caida = false; sincronizar(false); }
  };
  fuente.onerror = () => { caida = true; ui.conexion.hidden = false; };
}

async function sincronizar(completo = true) {
  const r = await api("/api/estado");
  aplicarAjustes(r.ajustes);
  estado.nombre = r.nombre || "";
  estado.chats = r.chats;
  estado.chatActual = r.chat_actual;
  pintarChats();
  if (completo) {
    pintarTurnos(r.turnos);
    if (r.generando) estado.mensaje = new MensajeAgente();
  }
  ponerGenerando(r.generando);
  pintarConversacion(r.modo_conversacion, r.modo_conversacion);
  (r.pendientes || []).forEach(encolarPregunta);
}

/* ============================ Barra lateral en móvil ============================ */

function cerrarLateral() { ui.app.classList.remove("lateral-abierta"); }
$("#abrirLateral").addEventListener("click", () => ui.app.classList.add("lateral-abierta"));
$("#velo").addEventListener("click", cerrarLateral);

/* ============================ Conexiones de la página ============================ */

function pintarSugerencias() {
  ui.sugerencias.replaceChildren(...SUGERENCIAS.map((s) => {
    const b = crear("button", "sugerencia");
    b.type = "button";
    b.dataset.agente = s.agente;
    b.append(crear("span", "punto"), crear("span", "", s.texto));
    b.addEventListener("click", () => {
      if (s.archivo) {
        ui.entrada.value = "Analiza este archivo y hazme una gráfica con lo más importante";
        ui.archivo.click();
      } else {
        ui.entrada.value = s.texto;
      }
      ajustarAltura();
      actualizarBotonEnviar();
      ui.entrada.focus();
    });
    return b;
  }));
}

ui.form.addEventListener("submit", (e) => { e.preventDefault(); enviar(); });
ui.entrada.addEventListener("input", () => { ajustarAltura(); actualizarBotonEnviar(); });
ui.entrada.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    if (!estado.generando) enviar();
  } else if (e.key === "ArrowUp" && !ui.entrada.value && estado.ultimoEnviado) {
    e.preventDefault();
    ui.entrada.value = estado.ultimoEnviado;
    ajustarAltura();
    actualizarBotonEnviar();
  }
});
ui.adjuntar.addEventListener("click", () => ui.archivo.click());
ui.archivo.addEventListener("change", () => { if (ui.archivo.files[0]) subirArchivo(ui.archivo.files[0]); });
$("#quitarAdjunto").addEventListener("click", quitarAdjunto);
ui.dictar.addEventListener("click", alternarDictado);
ui.conversar.addEventListener("click", alternarConversacion);
ui.altavoz.addEventListener("click", () => guardarAjustes({ altavoz: !estado.ajustes.altavoz }));
$("#nuevoChat").addEventListener("click", nuevoChat);
$("#abrirAjustes").addEventListener("click", abrirAjustes);
ui.buscar.addEventListener("input", pintarChats);

// Arrastrar y soltar archivos sobre la ventana
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", (e) => {
  e.preventDefault();
  const f = e.dataTransfer?.files?.[0];
  if (f) subirArchivo(f);
});

document.addEventListener("keydown", (e) => {
  const mod = e.ctrlKey || e.metaKey;
  if (mod && e.key.toLowerCase() === "k") { e.preventDefault(); nuevoChat(); }
  else if (e.key === "Escape" && estado.generando && !document.querySelector("dialog[open]")) { detener(); }
});

/* ============================ Arranque ============================ */

pintarSugerencias();
actualizarVacio();
sincronizar()
  .catch((e) => avisar(`No se pudo cargar el estado: ${e.message}`, "error"))
  .finally(() => { conectarEventos(); ui.entrada.focus(); });
