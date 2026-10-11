"""
tools/memoria.py

Memoria persistente de datos del usuario: cosas que el agente debe
recordar entre sesiones (nombre, preferencias, proyectos, etc.).

Se guarda en tools/recuerdos.json (no se sube al repo). Es distinto del
historial de chats (carpeta chats/): esto son HECHOS, no conversaciones.

Devuelve STRINGS para encajar con agente.py.
"""

import os
import json

RUTA = os.path.join(os.path.dirname(__file__), "recuerdos.json")


def _cargar():
    if os.path.exists(RUTA):
        try:
            with open(RUTA, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _guardar(datos):
    with open(RUTA, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def recordar(clave, valor):
    """Guarda un dato del usuario. Ej: recordar('lenguaje favorito', 'Python')."""
    datos = _cargar()
    datos[clave.lower().strip()] = valor
    _guardar(datos)
    return f"Recordado: {clave} = {valor}"


def recuperar(clave):
    """Devuelve un dato guardado. Si no existe exacto, busca por coincidencia."""
    datos = _cargar()
    clave_n = clave.lower().strip()
    if clave_n in datos:
        return f"{clave}: {datos[clave_n]}"
    # busqueda parcial
    coincidencias = {k: v for k, v in datos.items() if clave_n in k}
    if coincidencias:
        return "\n".join(f"{k}: {v}" for k, v in coincidencias.items())
    return f"No recuerdo nada sobre '{clave}'."


def olvidar(clave):
    """Borra un dato guardado."""
    datos = _cargar()
    clave_n = clave.lower().strip()
    if clave_n in datos:
        del datos[clave_n]
        _guardar(datos)
        return f"Olvidado: {clave}"
    return f"No habia nada guardado con '{clave}'."


def listar_recuerdos():
    """Devuelve todo lo que el agente recuerda del usuario."""
    datos = _cargar()
    if not datos:
        return "Todavia no recuerdo nada del usuario."
    return "\n".join(f"- {k}: {v}" for k, v in datos.items())


def contexto_memoria():
    """Texto resumido de lo que se recuerda, para inyectar al system prompt."""
    datos = _cargar()
    if not datos:
        return ""
    hechos = "; ".join(f"{k}: {v}" for k, v in datos.items())
    return f"Datos que recuerdas del usuario: {hechos}."
