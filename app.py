import os
import sys
import json
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
import agente
import lectura


def ruta_recurso(rel):
    """Encuentra archivos tanto en desarrollo como dentro del ejecutable."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


RUTA_AJUSTES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ajustes.json")

FUENTE = "Inter"

# Cada color es una tupla (claro, oscuro): CustomTkinter usa el primero en
# tema "light" y el segundo en tema "dark", y cambia solo al cambiar el tema.
COLOR_FONDO = ("#f2f2f5", "#1e1e24")
COLOR_LATERAL = ("#e6e6ea", "#26262e")
COLOR_USUARIO = ("#e7d8b0", "#4d3f26")
COLOR_AGENTE = ("#dbe6f0", "#1f2d3d")
COLOR_ACCION = ("#e8a93b", "#b57614")
COLOR_TEXTO = ("#1a1a1a", "#fff9e6")
COLOR_GRABANDO = ("#e85d52", "#fb4934")
COLOR_VOZ_ON = ("#5fa86a", "#8ec07c")
COLOR_CHAT_ACTIVO = ("#c3d2e2", "#3a4a5e")
COLOR_ADJUNTO = ("#6b6f7d", "#9aa0b5")


def cargar_ajustes():
    base = {"modelo": agente.MODELO, "tema": "dark", "confirmaciones": True,
            "altavoz": False, "modo_plan": False}
    if os.path.exists(RUTA_AJUSTES):
        try:
            with open(RUTA_AJUSTES, encoding="utf-8") as f:
                base.update(json.load(f))
        except Exception:
            pass
    return base


class ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ----- Ajustes -----
        self.ajustes = cargar_ajustes()
        agente.MODELO = self.ajustes["modelo"]
        ctk.set_appearance_mode(self.ajustes["tema"])
        ctk.set_default_color_theme("green")
        self.confirmaciones = self.ajustes["confirmaciones"]
        self.voz_activa = self.ajustes["altavoz"]
        self.modo_plan = self.ajustes["modo_plan"]

        self.title("Agente de IA Local")
        self.geometry("960x680")
        self.configure(fg_color=COLOR_FONDO)

        try:
            import tkinter as tk
            self.iconphoto(True, tk.PhotoImage(file=ruta_recurso(os.path.join("assets", "icono-256.png"))))
        except Exception as e:
            print("No se pudo cargar el icono:", e)

        self.grabadora = None
        self.grabando = False
        self.modo_conversacion = False

        # Estado de streaming y adjuntos
        self.label_actual = None
        self.texto_actual = ""
        self.adjunto = None
        self.adjunto_texto = None
        self._conf_resultado = None
        # Estado de cancelación y atajos
        self.generando = False
        self.cancelar_flag = threading.Event()
        self._plan_resultado = None
        self.ultima_respuesta = ""
        self.ultimo_usuario = ""

        # ----- Barra lateral -----
        self.lateral = ctk.CTkFrame(self, fg_color=COLOR_LATERAL, corner_radius=0, width=210)
        self.lateral.pack(side="left", fill="y")
        self.lateral.pack_propagate(False)

        ctk.CTkLabel(self.lateral, text="Chats", font=(FUENTE, 16, "bold"),
                     text_color=COLOR_TEXTO).pack(pady=(16, 8))

        self.boton_nuevo = ctk.CTkButton(
            self.lateral, text="+ Nuevo chat", height=36, corner_radius=10,
            command=self.nuevo_chat, font=(FUENTE, 13, "bold"), fg_color=COLOR_USUARIO,
        )
        self.boton_nuevo.pack(padx=12, pady=(0, 8), fill="x")

        self.entrada_busqueda = ctk.CTkEntry(
            self.lateral, placeholder_text="Buscar chats...", font=(FUENTE, 12))
        self.entrada_busqueda.pack(padx=12, pady=(0, 8), fill="x")
        self.entrada_busqueda.bind("<KeyRelease>", lambda e: self._refrescar_lista())

        self.boton_ajustes = ctk.CTkButton(
            self.lateral, text="Ajustes", height=34, corner_radius=10,
            command=self.abrir_ajustes, font=(FUENTE, 12, "bold"), fg_color=COLOR_AGENTE,
        )
        self.boton_ajustes.pack(side="bottom", padx=12, pady=12, fill="x")

        self.lista_chats = ctk.CTkScrollableFrame(self.lateral, fg_color="transparent")
        self.lista_chats.pack(padx=8, pady=4, fill="both", expand=True)

        # ----- Panel principal -----
        panel = ctk.CTkFrame(self, fg_color="transparent")
        panel.pack(side="right", fill="both", expand=True)

        ctk.CTkLabel(panel, text="Agente de IA Local", font=(FUENTE, 20, "bold"),
                     text_color=COLOR_TEXTO).pack(pady=(18, 4))
        ctk.CTkLabel(panel, text="Tu asistente local para crear proyectos, notas y eventos",
                     font=(FUENTE, 12), text_color=COLOR_ADJUNTO).pack(pady=(0, 10))

        self.chat = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        self.chat.pack(padx=15, pady=5, fill="both", expand=True)

        self.boton_conversacion = ctk.CTkButton(
            panel, text="Iniciar modo conversación", height=40, corner_radius=12,
            command=self.alternar_conversacion, font=(FUENTE, 14, "bold"), fg_color=COLOR_USUARIO,
        )
        self.boton_conversacion.pack(padx=15, pady=(0, 4), fill="x")

        # Etiqueta del archivo adjunto
        self.label_adjunto = ctk.CTkLabel(panel, text="", font=(FUENTE, 11), text_color=COLOR_ADJUNTO)
        self.label_adjunto.pack(padx=15, anchor="w")

        marco = ctk.CTkFrame(panel, fg_color=COLOR_AGENTE, corner_radius=14)
        marco.pack(padx=15, pady=(2, 15), fill="x")

        self.boton = ctk.CTkButton(marco, text="Enviar", width=80, corner_radius=10,
                                   command=self.enviar, font=(FUENTE, 13, "bold"))
        self.boton.pack(side="right", padx=(0, 8), pady=8)

        self.boton_voz = ctk.CTkButton(marco, text="Voz", width=60, corner_radius=10,
                                       fg_color=COLOR_USUARIO, command=self.alternar_voz,
                                       font=(FUENTE, 13, "bold"))
        self.boton_voz.pack(side="right", padx=(0, 6), pady=8)

        self.boton_altavoz = ctk.CTkButton(
            marco, text=("Altavoz: on" if self.voz_activa else "Altavoz: off"), width=90,
            corner_radius=10, fg_color=(COLOR_VOZ_ON if self.voz_activa else COLOR_USUARIO),
            command=self.alternar_altavoz, font=(FUENTE, 13, "bold"))
        self.boton_altavoz.pack(side="right", padx=(0, 6), pady=8)

        self.boton_adjuntar = ctk.CTkButton(marco, text="📎", width=44, corner_radius=10,
                                            fg_color=COLOR_USUARIO, command=self.adjuntar,
                                            font=(FUENTE, 14, "bold"))
        self.boton_adjuntar.pack(side="right", padx=(0, 6), pady=8)

        self.entrada = ctk.CTkEntry(marco, placeholder_text="Escribe lo que quieres hacer...",
                                    font=(FUENTE, 14), border_width=0, fg_color="transparent")
        self.entrada.pack(side="left", fill="x", expand=True, padx=14, pady=10, ipady=4)
        self.entrada.bind("<Return>", lambda e: self.enviar())

        # ----- Cargar el chat más reciente (o crear uno) -----
        chats = agente.listar_chats()
        self.chat_actual = chats[0]["id"] if chats else agente.crear_chat()
        self.mensajes = agente.cargar_chat(self.chat_actual)

        self._render_chat()
        self._refrescar_lista()
        self.entrada.focus()

        # ----- Atajos de teclado -----
        self.bind("<Escape>", lambda e: self.detener_generacion())
        self.bind("<Control-f>", self._focus_busqueda)
        self.bind("<Control-c>", self._atajo_copiar)
        self.entrada.bind("<Up>", self._reusar_ultimo)

    # ----- Render -----

    def _render_chat(self):
        for widget in self.chat.winfo_children():
            widget.destroy()
        self.label_actual = None
        turnos = [m for m in self.mensajes
                  if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
        if turnos:
            for m in turnos:
                if m.get("content"):
                    self._burbuja(m["content"], "usuario" if m["role"] == "user" else "agente")
        else:
            self._burbuja("¡Hola! Dime qué quieres que haga.", "agente")

    def _burbuja(self, texto, tipo):
        if tipo == "usuario":
            color, anclaje = COLOR_USUARIO, "e"
        elif tipo == "accion":
            color, anclaje = COLOR_ACCION, "w"
        else:
            color, anclaje = COLOR_AGENTE, "w"

        fila = ctk.CTkFrame(self.chat, fg_color="transparent")
        fila.pack(fill="x", pady=4)
        burbuja = ctk.CTkLabel(fila, text=texto, fg_color=color, text_color=COLOR_TEXTO,
                               corner_radius=14, font=(FUENTE, 13), justify="left",
                               wraplength=470, anchor="w")
        burbuja.pack(anchor=anclaje, padx=6, ipadx=12, ipady=8)
        self.after(50, self._scroll_abajo)
        return burbuja

    def _scroll_abajo(self):
        self.chat._parent_canvas.yview_moveto(1.0)

    # ----- Lista lateral -----

    def _refrescar_lista(self):
        for widget in self.lista_chats.winfo_children():
            widget.destroy()
        filtro = ""
        if hasattr(self, "entrada_busqueda"):
            filtro = self.entrada_busqueda.get().strip().lower()
        for c in agente.listar_chats():
            if filtro and filtro not in c["titulo"].lower():
                continue
            fila = ctk.CTkFrame(self.lista_chats, fg_color="transparent")
            fila.pack(fill="x", pady=2)
            activo = (c["id"] == self.chat_actual)
            # La X se empaqueta primero para que SIEMPRE tenga su sitio reservado.
            ctk.CTkButton(fila, text="✕", width=26, height=32, corner_radius=8,
                          font=(FUENTE, 12), fg_color="transparent", hover_color=COLOR_GRABANDO,
                          command=lambda cid=c["id"]: self.borrar_chat(cid)
                          ).pack(side="right", padx=(2, 0))
            # El título se recorta si es muy largo para no empujar a la X.
            titulo = c["titulo"]
            if len(titulo) > 20:
                titulo = titulo[:20] + "…"
            ctk.CTkButton(fila, text=titulo, anchor="w", height=32, corner_radius=8,
                          font=(FUENTE, 12),
                          fg_color=COLOR_CHAT_ACTIVO if activo else "transparent",
                          hover_color=COLOR_CHAT_ACTIVO,
                          command=lambda cid=c["id"]: self.cambiar_chat(cid)
                          ).pack(side="left", fill="x", expand=True)

    def nuevo_chat(self):
        self.chat_actual = agente.crear_chat()
        self.mensajes = agente.cargar_chat(self.chat_actual)
        self._render_chat()
        self._refrescar_lista()
        self.entrada.focus()

    def cambiar_chat(self, chat_id):
        if chat_id == self.chat_actual:
            return
        self.chat_actual = chat_id
        self.mensajes = agente.cargar_chat(chat_id)
        self._render_chat()
        self._refrescar_lista()
        self.entrada.focus()

    def borrar_chat(self, chat_id):
        agente.borrar_chat(chat_id)
        if chat_id == self.chat_actual:
            chats = agente.listar_chats()
            self.chat_actual = chats[0]["id"] if chats else agente.crear_chat()
            self.mensajes = agente.cargar_chat(self.chat_actual)
            self._render_chat()
        self._refrescar_lista()

    # ----- Adjuntar archivos -----

    def adjuntar(self):
        ruta = filedialog.askopenfilename(
            title="Elige un archivo",
            filetypes=[("Documentos", "*.pdf *.txt *.md *.py *.json *.csv *.html"), ("Todos", "*.*")],
        )
        if not ruta:
            return
        self.adjunto = ruta
        self.adjunto_texto = lectura.leer_archivo(ruta)
        self.label_adjunto.configure(text=f"📎 {os.path.basename(ruta)}  (se enviará con tu mensaje)")

    def _quitar_adjunto(self):
        self.adjunto = None
        self.adjunto_texto = None
        self.label_adjunto.configure(text="")

    # ----- Confirmación (llamada desde el hilo de trabajo) -----

    def _confirmar(self, nombre, argumentos):
        if not self.confirmaciones:
            return True
        self._conf_resultado = None
        evento = threading.Event()

        def preguntar():
            self._conf_resultado = messagebox.askyesno(
                "Confirmar acción",
                f"El agente quiere ejecutar:\n\n{nombre}\n{argumentos}\n\n¿Permitir?",
            )
            evento.set()

        self.after(0, preguntar)
        evento.wait()
        return bool(self._conf_resultado)

    # ----- Enviar (modo texto, con streaming) -----

    def enviar(self):
        peticion = self.entrada.get().strip()
        if not peticion:
            return
        self.entrada.delete(0, "end")

        if self.adjunto_texto:
            nombre = os.path.basename(self.adjunto)
            contexto = self.adjunto_texto[:6000]
            peticion_final = (f"Contenido del archivo adjunto '{nombre}':\n{contexto}\n\n"
                              f"Petición del usuario: {peticion}")
            self._burbuja(f"{peticion}   📎 {nombre}", "usuario")
            self._quitar_adjunto()
        else:
            peticion_final = peticion
            self._burbuja(peticion, "usuario")

        self.ultimo_usuario = peticion
        self.entrada.configure(state="disabled")
        self.generando = True
        self.cancelar_flag.clear()
        self.boton.configure(text="Detener", command=self.detener_generacion)
        self.label_actual = None
        self.texto_actual = ""
        threading.Thread(target=self._trabajar, args=(peticion_final,), daemon=True).start()

    def detener_generacion(self):
        if self.generando:
            self.cancelar_flag.set()

    def _cancelado(self):
        return self.cancelar_flag.is_set()

    def _trabajar(self, peticion):
        try:
            respuesta, _ = agente.procesar(
                peticion, self.mensajes,
                confirmador=self._confirmar,
                on_token=self._on_token,
                on_accion=self._on_accion,
                cancelado=self._cancelado,
                planificador=self._aprobar_plan if self.modo_plan else None,
            )
        except Exception as e:
            respuesta = f"Ocurrió un error: {e}"
            self.after(0, self._burbuja, respuesta, "accion")
        self.after(0, self._fin_envio, respuesta)

    def _on_token(self, delta):
        self.after(0, self._append_token, delta)

    def _append_token(self, delta):
        if self.label_actual is None:
            self.texto_actual = ""
            self.label_actual = self._burbuja("", "agente")
        self.texto_actual += delta
        self.label_actual.configure(text=self.texto_actual)
        self.after(20, self._scroll_abajo)

    def _on_accion(self, linea):
        self.after(0, self._burbuja, f"-> {linea}", "accion")

    def _fin_envio(self, respuesta):
        self.generando = False
        self.cancelar_flag.clear()
        self.entrada.configure(state="normal")
        self.boton.configure(state="normal", text="Enviar", command=self.enviar)
        self.entrada.focus()
        # Si por algún motivo no se hizo streaming pero hay texto, lo mostramos.
        if self.label_actual is None and respuesta:
            self._burbuja(respuesta, "agente")
        self.label_actual = None
        if respuesta:
            self.ultima_respuesta = respuesta
        agente.guardar_chat(self.chat_actual, self.mensajes)
        self._refrescar_lista()
        if self.voz_activa and respuesta:
            threading.Thread(target=self._hablar, args=(respuesta,), daemon=True).start()

    # ----- Modo plan (aprobación, llamada desde el hilo de trabajo) -----

    def _aprobar_plan(self, plan):
        self._plan_resultado = None
        evento = threading.Event()

        def preguntar():
            win = ctk.CTkToplevel(self)
            win.title("Plan del agente")
            win.geometry("460x420")
            win.configure(fg_color=COLOR_FONDO)
            win.transient(self)
            win.after(120, win.lift)
            ctk.CTkLabel(win, text="El agente planea hacer esto:", font=(FUENTE, 14, "bold"),
                         text_color=COLOR_TEXTO).pack(pady=(16, 8), padx=16, anchor="w")
            caja = ctk.CTkTextbox(win, font=(FUENTE, 12), wrap="word")
            caja.pack(padx=16, pady=4, fill="both", expand=True)
            caja.insert("1.0", plan)
            caja.configure(state="disabled")
            fila = ctk.CTkFrame(win, fg_color="transparent")
            fila.pack(fill="x", padx=16, pady=12)

            def resolver(ok):
                self._plan_resultado = ok
                win.destroy()
                evento.set()

            ctk.CTkButton(fila, text="Ejecutar", command=lambda: resolver(True),
                          fg_color=COLOR_VOZ_ON, font=(FUENTE, 13, "bold")).pack(side="right", padx=(6, 0))
            ctk.CTkButton(fila, text="Cancelar", command=lambda: resolver(False),
                          fg_color=COLOR_USUARIO, font=(FUENTE, 13, "bold")).pack(side="right")
            win.protocol("WM_DELETE_WINDOW", lambda: resolver(False))

        self.after(0, preguntar)
        evento.wait()
        if self._plan_resultado:
            self.after(0, self._burbuja, f"Plan aprobado:\n{plan}", "accion")
        return bool(self._plan_resultado)

    # ----- Atajos de teclado -----

    def _focus_busqueda(self, event=None):
        self.entrada_busqueda.focus()
        return "break"

    def _atajo_copiar(self, event=None):
        # Si el foco está en un campo de texto, deja el copiado normal del sistema.
        foco = self.focus_get()
        if foco in (self.entrada, getattr(self, "entrada_busqueda", None)):
            return
        if self.ultima_respuesta:
            self.clipboard_clear()
            self.clipboard_append(self.ultima_respuesta)
        return "break"

    def _reusar_ultimo(self, event=None):
        if not self.entrada.get().strip() and self.ultimo_usuario:
            self.entrada.delete(0, "end")
            self.entrada.insert(0, self.ultimo_usuario)
            return "break"

    def _hablar(self, texto):
        try:
            from tools import habla
            habla.decir(texto)
        except Exception as e:
            print("No se pudo hablar:", e)

    def alternar_altavoz(self):
        self.voz_activa = not self.voz_activa
        if self.voz_activa:
            self.boton_altavoz.configure(text="Altavoz: on", fg_color=COLOR_VOZ_ON)
        else:
            self.boton_altavoz.configure(text="Altavoz: off", fg_color=COLOR_USUARIO)

    def alternar_voz(self):
        from tools import voz
        if not self.grabando:
            try:
                self.grabadora = voz.Grabadora()
                self.grabadora.iniciar()
            except Exception as e:
                self._burbuja(f"No se pudo iniciar la voz: {e}", "accion")
                return
            self.grabando = True
            self.boton_voz.configure(text="Detener", fg_color=COLOR_GRABANDO)
        else:
            self.grabando = False
            self.boton_voz.configure(state="disabled", text="...")
            threading.Thread(target=self._transcribir, daemon=True).start()

    def _transcribir(self):
        try:
            texto = self.grabadora.detener()
        except Exception as e:
            texto = ""
            self.after(0, lambda: self._burbuja(f"Error al transcribir: {e}", "accion"))
        self.after(0, self._poner_texto_voz, texto)

    def _poner_texto_voz(self, texto):
        self.boton_voz.configure(state="normal", text="Voz", fg_color=COLOR_USUARIO)
        if texto:
            self.entrada.delete(0, "end")
            self.entrada.insert(0, texto)
        self.entrada.focus()

    # ----- Modo conversación manos libres -----

    def alternar_conversacion(self):
        if not self.modo_conversacion:
            self.modo_conversacion = True
            self.voz_activa = True
            self.boton_altavoz.configure(text="Altavoz: on", fg_color=COLOR_VOZ_ON)
            self.boton_conversacion.configure(text="Detener conversación", fg_color=COLOR_GRABANDO)
            threading.Thread(target=self._bucle_conversacion, daemon=True).start()
        else:
            self.modo_conversacion = False
            self.boton_conversacion.configure(text="Iniciar modo conversación", fg_color=COLOR_USUARIO)

    def _bucle_conversacion(self):
        from tools import escucha, habla
        while self.modo_conversacion:
            try:
                texto = escucha.escuchar_una_frase(parar=lambda: not self.modo_conversacion)
            except Exception as e:
                self.after(0, lambda: self._burbuja(f"Error al escuchar: {e}", "accion"))
                break
            if not self.modo_conversacion:
                break
            if not texto:
                continue
            if texto.lower().strip() in ("salir", "detente", "adiós", "adios", "para", "para ya"):
                self.after(0, self.alternar_conversacion)
                break

            self.after(0, self._burbuja, texto, "usuario")
            try:
                respuesta, acciones = agente.procesar(
                    texto, self.mensajes, confirmador=self._confirmar)
            except Exception as e:
                respuesta, acciones = f"Ocurrió un error: {e}", []
            self.after(0, self._mostrar_conversacion, respuesta, acciones)
            if respuesta:
                try:
                    habla.decir(respuesta)
                except Exception as e:
                    print("No se pudo hablar:", e)

    def _mostrar_conversacion(self, respuesta, acciones):
        for a in acciones:
            self._burbuja(f"-> {a}", "accion")
        if respuesta:
            self._burbuja(respuesta, "agente")
            self.ultima_respuesta = respuesta
        agente.guardar_chat(self.chat_actual, self.mensajes)
        self._refrescar_lista()

    # ----- Panel de ajustes -----

    def abrir_ajustes(self):
        win = ctk.CTkToplevel(self)
        win.title("Ajustes")
        win.geometry("380x440")
        win.configure(fg_color=COLOR_FONDO)
        win.transient(self)
        win.after(120, win.lift)

        ctk.CTkLabel(win, text="Ajustes", font=(FUENTE, 18, "bold"),
                     text_color=COLOR_TEXTO).pack(pady=(16, 12))

        ctk.CTkLabel(win, text="Modelo de Ollama", font=(FUENTE, 12),
                     text_color=COLOR_TEXTO, anchor="w").pack(padx=20, anchor="w")
        modelos = agente.modelos_disponibles()
        if agente.MODELO not in modelos:
            modelos = [agente.MODELO] + modelos
        menu_modelo = ctk.CTkOptionMenu(win, values=modelos)
        menu_modelo.set(agente.MODELO)
        menu_modelo.pack(padx=20, pady=(2, 12), fill="x")

        ctk.CTkLabel(win, text="Tema", font=(FUENTE, 12),
                     text_color=COLOR_TEXTO, anchor="w").pack(padx=20, anchor="w")
        menu_tema = ctk.CTkOptionMenu(win, values=["dark", "light", "system"])
        menu_tema.set(self.ajustes.get("tema", "dark"))
        menu_tema.pack(padx=20, pady=(2, 14), fill="x")

        switch_conf = ctk.CTkSwitch(win, text="Pedir confirmación en comandos")
        switch_conf.pack(padx=20, pady=6, anchor="w")
        if self.confirmaciones:
            switch_conf.select()

        switch_voz = ctk.CTkSwitch(win, text="Altavoz activado por defecto")
        switch_voz.pack(padx=20, pady=6, anchor="w")
        if self.voz_activa:
            switch_voz.select()

        switch_plan = ctk.CTkSwitch(win, text="Modo plan (aprobar pasos antes de actuar)")
        switch_plan.pack(padx=20, pady=6, anchor="w")
        if self.modo_plan:
            switch_plan.select()

        def guardar():
            agente.MODELO = menu_modelo.get()
            tema = menu_tema.get()
            ctk.set_appearance_mode(tema)
            self.configure(fg_color=COLOR_FONDO)  # refuerza el fondo de la raíz
            self.confirmaciones = bool(switch_conf.get())
            self.voz_activa = bool(switch_voz.get())
            self.modo_plan = bool(switch_plan.get())
            self.boton_altavoz.configure(
                text=("Altavoz: on" if self.voz_activa else "Altavoz: off"),
                fg_color=(COLOR_VOZ_ON if self.voz_activa else COLOR_USUARIO))
            self.ajustes = {"modelo": agente.MODELO, "tema": tema,
                            "confirmaciones": self.confirmaciones, "altavoz": self.voz_activa,
                            "modo_plan": self.modo_plan}
            try:
                with open(RUTA_AJUSTES, "w", encoding="utf-8") as f:
                    json.dump(self.ajustes, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print("No se pudieron guardar los ajustes:", e)
            win.destroy()

        ctk.CTkButton(win, text="Guardar", height=38, corner_radius=10,
                      command=guardar, font=(FUENTE, 13, "bold"),
                      fg_color=COLOR_USUARIO).pack(padx=20, pady=18, fill="x")


if __name__ == "__main__":
    app = ChatApp()
    app.mainloop()
