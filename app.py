import os
import sys
import threading
import customtkinter as ctk
import agente


def ruta_recurso(rel):
    """Encuentra archivos tanto en desarrollo como dentro del ejecutable."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

FUENTE = "Inter"

COLOR_FONDO = "#1e1e24"
COLOR_LATERAL = "#26262e"
COLOR_USUARIO = "#4d3f26"
COLOR_AGENTE = "#1f2d3d"
COLOR_ACCION = "#b57614"
COLOR_TEXTO = "#fff9e6"
COLOR_GRABANDO = "#fb4934"
COLOR_VOZ_ON = "#8ec07c"
COLOR_CHAT_ACTIVO = "#3a4a5e"


class ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Agente de IA Local")
        self.geometry("940x680")
        self.configure(fg_color=COLOR_FONDO)

        try:
            import tkinter as tk
            self.iconphoto(True, tk.PhotoImage(file=ruta_recurso(os.path.join("assets", "icono-256.png"))))
        except Exception as e:
            print("No se pudo cargar el icono:", e)

        self.grabadora = None
        self.grabando = False
        self.voz_activa = False
        self.modo_conversacion = False

        # ----- Barra lateral de chats -----
        self.lateral = ctk.CTkFrame(self, fg_color=COLOR_LATERAL, corner_radius=0, width=210)
        self.lateral.pack(side="left", fill="y")
        self.lateral.pack_propagate(False)

        ctk.CTkLabel(
            self.lateral, text="Chats", font=(FUENTE, 16, "bold"),
            text_color=COLOR_TEXTO,
        ).pack(pady=(16, 8))

        self.boton_nuevo = ctk.CTkButton(
            self.lateral, text="+ Nuevo chat", height=36, corner_radius=10,
            command=self.nuevo_chat, font=(FUENTE, 13, "bold"), fg_color=COLOR_USUARIO,
        )
        self.boton_nuevo.pack(padx=12, pady=(0, 10), fill="x")

        self.lista_chats = ctk.CTkScrollableFrame(self.lateral, fg_color="transparent")
        self.lista_chats.pack(padx=8, pady=4, fill="both", expand=True)

        # ----- Panel principal -----
        panel = ctk.CTkFrame(self, fg_color="transparent")
        panel.pack(side="right", fill="both", expand=True)

        cabecera = ctk.CTkLabel(
            panel, text="Agente de IA Local",
            font=(FUENTE, 20, "bold"), text_color=COLOR_TEXTO,
        )
        cabecera.pack(pady=(18, 4))

        subtitulo = ctk.CTkLabel(
            panel, text="Tu asistente local para crear proyectos, notas y eventos",
            font=(FUENTE, 12), text_color="#9aa0b5",
        )
        subtitulo.pack(pady=(0, 10))

        self.chat = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        self.chat.pack(padx=15, pady=5, fill="both", expand=True)

        self.boton_conversacion = ctk.CTkButton(
            panel, text="Iniciar modo conversación", height=40, corner_radius=12,
            command=self.alternar_conversacion, font=(FUENTE, 14, "bold"),
            fg_color=COLOR_USUARIO,
        )
        self.boton_conversacion.pack(padx=15, pady=(0, 8), fill="x")

        marco = ctk.CTkFrame(panel, fg_color=COLOR_AGENTE, corner_radius=14)
        marco.pack(padx=15, pady=(0, 15), fill="x")

        self.boton = ctk.CTkButton(
            marco, text="Enviar", width=80, corner_radius=10,
            command=self.enviar, font=(FUENTE, 13, "bold"),
        )
        self.boton.pack(side="right", padx=(0, 8), pady=8)

        self.boton_voz = ctk.CTkButton(
            marco, text="Voz", width=60, corner_radius=10, fg_color=COLOR_USUARIO,
            command=self.alternar_voz, font=(FUENTE, 13, "bold"),
        )
        self.boton_voz.pack(side="right", padx=(0, 6), pady=8)

        self.boton_altavoz = ctk.CTkButton(
            marco, text="Altavoz: off", width=90, corner_radius=10, fg_color=COLOR_USUARIO,
            command=self.alternar_altavoz, font=(FUENTE, 13, "bold"),
        )
        self.boton_altavoz.pack(side="right", padx=(0, 6), pady=8)

        self.entrada = ctk.CTkEntry(
            marco, placeholder_text="Escribe lo que quieres hacer...",
            font=(FUENTE, 14), border_width=0, fg_color="transparent",
        )
        self.entrada.pack(side="left", fill="x", expand=True, padx=14, pady=10, ipady=4)
        self.entrada.bind("<Return>", lambda e: self.enviar())

        # ----- Cargar el chat más reciente (o crear uno) -----
        chats = agente.listar_chats()
        if chats:
            self.chat_actual = chats[0]["id"]
        else:
            self.chat_actual = agente.crear_chat()
        self.mensajes = agente.cargar_chat(self.chat_actual)

        self._render_chat()
        self._refrescar_lista()
        self.entrada.focus()

    # ----- Render de la conversación -----

    def _render_chat(self):
        for widget in self.chat.winfo_children():
            widget.destroy()
        turnos = [m for m in self.mensajes
                  if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
        if turnos:
            for m in turnos:
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
        burbuja = ctk.CTkLabel(
            fila, text=texto, fg_color=color, text_color=COLOR_TEXTO,
            corner_radius=14, font=(FUENTE, 13), justify="left",
            wraplength=470, anchor="w",
        )
        burbuja.pack(anchor=anclaje, padx=6, ipadx=12, ipady=8)
        self.after(50, self._scroll_abajo)

    def _scroll_abajo(self):
        self.chat._parent_canvas.yview_moveto(1.0)

    # ----- Lista de chats (barra lateral) -----

    def _refrescar_lista(self):
        for widget in self.lista_chats.winfo_children():
            widget.destroy()
        for c in agente.listar_chats():
            fila = ctk.CTkFrame(self.lista_chats, fg_color="transparent")
            fila.pack(fill="x", pady=2)

            activo = (c["id"] == self.chat_actual)
            boton = ctk.CTkButton(
                fila, text=c["titulo"], anchor="w", height=32, corner_radius=8,
                font=(FUENTE, 12), fg_color=COLOR_CHAT_ACTIVO if activo else "transparent",
                hover_color=COLOR_CHAT_ACTIVO,
                command=lambda cid=c["id"]: self.cambiar_chat(cid),
            )
            boton.pack(side="left", fill="x", expand=True)

            borrar = ctk.CTkButton(
                fila, text="✕", width=26, height=32, corner_radius=8,
                font=(FUENTE, 12), fg_color="transparent", hover_color=COLOR_GRABANDO,
                command=lambda cid=c["id"]: self.borrar_chat(cid),
            )
            borrar.pack(side="right", padx=(2, 0))

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
        # Si borramos el chat activo, abrimos otro (o creamos uno nuevo).
        if chat_id == self.chat_actual:
            chats = agente.listar_chats()
            if chats:
                self.chat_actual = chats[0]["id"]
            else:
                self.chat_actual = agente.crear_chat()
            self.mensajes = agente.cargar_chat(self.chat_actual)
            self._render_chat()
        self._refrescar_lista()

    # ----- Modo texto / botón Voz -----

    def enviar(self):
        peticion = self.entrada.get().strip()
        if not peticion:
            return
        self.entrada.delete(0, "end")
        self._burbuja(peticion, "usuario")
        self.entrada.configure(state="disabled")
        self.boton.configure(state="disabled", text="...")
        threading.Thread(target=self._trabajar, args=(peticion,), daemon=True).start()

    def _trabajar(self, peticion):
        try:
            respuesta, acciones = agente.procesar(peticion, self.mensajes)
        except Exception as e:
            respuesta, acciones = f"Ocurrió un error: {e}", []
        self.after(0, self._mostrar, respuesta, acciones)

    def _mostrar(self, respuesta, acciones):
        for a in acciones:
            self._burbuja(f"-> {a}", "accion")
        if respuesta:
            self._burbuja(respuesta, "agente")
        self.entrada.configure(state="normal")
        self.boton.configure(state="normal", text="Enviar")
        self.entrada.focus()
        agente.guardar_chat(self.chat_actual, self.mensajes)
        self._refrescar_lista()
        if self.voz_activa and respuesta:
            threading.Thread(target=self._hablar, args=(respuesta,), daemon=True).start()

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
                respuesta, acciones = agente.procesar(texto, self.mensajes)
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
        agente.guardar_chat(self.chat_actual, self.mensajes)
        self._refrescar_lista()


if __name__ == "__main__":
    app = ChatApp()
    app.mainloop()
