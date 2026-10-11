"""
tools/calendario.py

Crea eventos de calendario .ics compatibles con Google Calendar, Outlook y Apple.
"""

import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone

from tools.filesystem import ruta_segura, nombre_archivo_seguro, BASE_DIR


def _escapar_ics(texto: str) -> str:
    """Escapa caracteres especiales según RFC 5545."""
    return (str(texto).replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def crear_evento(titulo: str, fecha: str, hora: str = "09:00", duracion_horas: float = 1) -> str:
    """Crea un evento de calendario en formato .ics.
    fecha en formato AAAA-MM-DD, hora en formato HH:MM (24h)."""
    hora = (hora or "09:00").strip()
    try:
        inicio = datetime.strptime(f"{fecha.strip()} {hora}", "%Y-%m-%d %H:%M")
    except ValueError:
        return (f"Formato inválido (fecha='{fecha}', hora='{hora}'). "
                f"Usa fecha AAAA-MM-DD y hora HH:MM en 24 horas.")
    try:
        duracion = float(duracion_horas or 1)
    except (TypeError, ValueError):
        return f"Duración inválida: '{duracion_horas}'. Debe ser un número de horas."
    if duracion <= 0 or duracion > 24 * 7:
        return "La duración debe ser mayor que 0 y como máximo una semana."

    # timedelta maneja bien eventos que cruzan la medianoche.
    fin = inicio + timedelta(hours=duracion)

    fmt = "%Y%m%dT%H%M%S"
    lineas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Mi Agente IA//ES",
        "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@mi-agente-ia",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime(fmt)}Z",
        f"DTSTART:{inicio.strftime(fmt)}",
        f"DTEND:{fin.strftime(fmt)}",
        f"SUMMARY:{_escapar_ics(titulo)}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    contenido = "\r\n".join(lineas) + "\r\n"  # RFC 5545 exige CRLF

    archivo = ruta_segura(Path("calendario") / f"{nombre_archivo_seguro(titulo)}_{inicio:%Y-%m-%d}.ics")
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_bytes(contenido.encode("utf-8"))
    return (f"Evento '{titulo}' creado del {inicio:%Y-%m-%d %H:%M} al {fin:%Y-%m-%d %H:%M}: "
            f"{archivo.relative_to(BASE_DIR)}")
