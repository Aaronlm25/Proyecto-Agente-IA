"""
registro.py

Registro (logging) de acciones y errores del agente.
Crea logs/agente.log en la raíz del proyecto.
"""

import os
import logging

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(CARPETA, exist_ok=True)
ARCHIVO = os.path.join(CARPETA, "agente.log")

logging.basicConfig(
    filename=ARCHIVO,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)

_log = logging.getLogger("agente")


def accion(texto):
    """Registra una acción ejecutada por el agente."""
    _log.info("ACCION: %s", texto)


def error(texto):
    """Registra un error."""
    _log.error("%s", texto)


def info(texto):
    _log.info("%s", texto)
