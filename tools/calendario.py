from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent / "workspace"


def crear_evento(titulo: str, fecha: str, hora: str = "09:00", duracion_horas: int = 1) -> str:
    """Crea un evento de calendario en formato .ics.
    fecha en formato AAAA-MM-DD, hora en formato HH:MM (24h)."""
    cal = BASE_DIR / "calendario"
    cal.mkdir(parents=True, exist_ok=True)

    inicio = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
    fin = inicio.replace(hour=(inicio.hour + duracion_horas) % 24)

    fmt = "%Y%m%dT%H%M%S"
    creado = datetime.now().strftime(fmt)

    contenido = (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//Mi Agente IA//ES\n"
        "BEGIN:VEVENT\n"
        f"DTSTAMP:{creado}\n"
        f"DTSTART:{inicio.strftime(fmt)}\n"
        f"DTEND:{fin.strftime(fmt)}\n"
        f"SUMMARY:{titulo}\n"
        "END:VEVENT\n"
        "END:VCALENDAR\n"
    )

    archivo = cal / f"{titulo.replace(' ', '_')}_{fecha}.ics"
    archivo.write_text(contenido)
    return f"Evento '{titulo}' creado para {fecha} {hora}: {archivo}"
