import threading
import customtkinter as ctk
import agente

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Paleta de colores
COLOR_FONDO = "#1a1a2e"
COLOR_USUARIO = "#0f3460"
COLOR_AGENTE = "#16213e"
COLOR_ACCION = "#1f6f54"
COLOR_TEXTO = "#e8e8e8"


class ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Agente de IA Local")
        self.geometry("760x680")
        self.configure(fg_color=COLOR_FONDO)

        # Ícono de la ventana (si existe el archivo)
        try:
            import tkinter as tk
            import os
            ruta_icono = os.path.join(os.path.dirname(__file__), "assets", "icono-256.png")
            self.iconphoto(True, tk.PhotoImage(file=ruta_icono))
        except Exception as e:
            print("No se pudo cargar el icono:", e)

        self.mensajes = [agente.MENSAJE_SISTEMA]

        # Encabezado
        cabecera = ctk.CTkLabel(
            self, text=" Agente de IA Local",
            font=("Arial", 20, "bold"), text_color=COLOR_TEXTO,
        )
        cabecera.pack(pady=(18, 4))

        subtitulo = ctk.CTkLabel(
            self, text="Tu asistente local para crear proyectos, notas y eventos",
            font=("Arial", 12), text_color="#9aa0b5",
        )
        subtitulo.pack(pady=(0, 10))

        # Área scrollable donde aparecen las burbujas
        self.chat = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.chat.pack(padx=15, pady=5, fill="both", expand=True)

        # Zona de entrada
        marco = ctk.CTkFrame(self, fg_color=COLOR_AGENTE, corner_radius=14)
        marco.pack(padx=15, pady=15, fill="x")

        self.entrada = ctk.CTkEntry(
            marco, placeholder_text="Escribe lo que quieres hacer...",
            font=("Arial", 14), border_width=0, fg_color="transparent",
        )
        self.entrada.pack(side="left", fill="x", expand=True, padx=14, pady=10, ipady=4)
        self.entrada.bind("<Return>", lambda e: self.enviar())

        self.boton = ctk.CTkButton(
            marco, text="Enviar", width=100, corner_radius=10,
            command=self.enviar, font=("Arial", 13, "bold"),
        )
        self.boton.pack(side="right", padx=(0, 8), pady=8)

        self._burbuja("¡Hola! Dime qué quieres que haga.", "agente")
        self.entrada.focus()

    def _burbuja(self, texto, tipo):
        """tipo: 'usuario', 'agente' o 'accion'."""
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
            corner_radius=14, font=("Arial", 13), justify="left",
            wraplength=470, anchor="w",
        )
        burbuja.pack(anchor=anclaje, padx=6, ipadx=12, ipady=8)
        self.after(50, self._scroll_abajo)

    def _scroll_abajo(self):
        self.chat._parent_canvas.yview_moveto(1.0)

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
            self._burbuja(f"⚙️  {a}", "accion")
        if respuesta:
            self._burbuja(respuesta, "agente")
        self.entrada.configure(state="normal")
        self.boton.configure(state="normal", text="Enviar")
        self.entrada.focus()


if __name__ == "__main__":
    app = ChatApp()
    app.mainloop()
