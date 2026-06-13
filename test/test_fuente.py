import tkinter as tk
from tkinter import font

raiz = tk.Tk()
raiz.title("Prueba de fuentes")
raiz.geometry("500x400")

# Qué fuentes ve Tkinter (no el sistema)
familias = sorted(font.families())
print("¿Está DejaVu Sans?:", "DejaVu Sans" in familias)
print("¿Está Noto Sans?:", "Noto Sans" in familias)
print("Fuente por defecto:", font.nametofont("TkDefaultFont").actual())

pruebas = [
    ("Fuente por defecto (sin especificar)", None),
    ("TkDefaultFont", "TkDefaultFont"),
    ("DejaVu Sans", ("DejaVu Sans", 16)),
    ("Helvetica", ("Helvetica", 16)),
]

for etiqueta, f in pruebas:
    if f is None:
        tk.Label(raiz, text=f"{etiqueta}: Hola Agente 123").pack(pady=8)
    else:
        tk.Label(raiz, text=f"{etiqueta}: Hola Agente 123", font=f).pack(pady=8)

raiz.mainloop()
