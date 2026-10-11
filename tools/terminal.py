"""
tools/terminal.py

Ejecuta comandos del sistema desde el agente (siempre dentro de workspace/).

Seguridad (por capas):
  1. SIN shell: el comando se parte con shlex y se ejecuta con shell=False,
     así que ; && || | > ` $( ) no funcionan y no se pueden encadenar comandos.
  2. LISTA BLANCA de programas: solo se pueden ejecutar los de PERMITIDOS.
  3. Argumentos: se rechazan rutas absolutas, '~' y '..' (no se puede salir del workspace).
  4. Timeout y salida recortada.
  5. Además, el agente pide confirmación al usuario antes de cada comando.

OJO: esto reduce mucho el riesgo, pero NO es una sandbox perfecta (por ejemplo,
'python script.py' puede hacer lo que el script diga). Para aislamiento real,
ejecuta el agente dentro de un contenedor (Docker, bubblewrap o firejail).
"""

import re
import sys
import shlex
import subprocess
from pathlib import Path

from tools.filesystem import BASE_DIR, ruta_segura

TIMEOUT = 60          # segundos máximos por comando
MAX_SALIDA = 3000     # caracteres máximos de salida que se devuelven

PERMITIDOS = {
    "ls", "cat", "head", "tail", "wc", "grep", "echo", "pwd", "tree",
    "mkdir", "touch", "cp", "mv",
    "python", "python3", "pip", "pip3", "pytest",
    "node", "npm", "npx",
    "git",
}

# Opciones que permiten ejecutar código arbitrario escrito en la propia línea.
OPCIONES_PROHIBIDAS = {
    "python": {"-c"}, "python3": {"-c"},
    "node": {"-e", "--eval", "-p", "--print"},
}

OPERADORES_SHELL = re.compile(r"[;&|<>`$]")


def _validar(argumentos: list[str]) -> str | None:
    """Devuelve un mensaje de error si el comando no está permitido, o None si es válido."""
    if not argumentos:
        return "Comando vacío."
    programa = argumentos[0]
    if programa not in PERMITIDOS:
        return (f"El programa '{programa}' no está permitido. "
                f"Permitidos: {', '.join(sorted(PERMITIDOS))}.")
    prohibidas = OPCIONES_PROHIBIDAS.get(programa, set())
    for arg in argumentos[1:]:
        if arg in prohibidas:
            return f"La opción '{arg}' no está permitida con {programa}."
        if arg.startswith(("/", "~")) or ".." in Path(arg).parts:
            return f"Argumento no permitido (sale del workspace): '{arg}'."
    return None


def _correr(argumentos: list[str], directorio: Path) -> str:
    try:
        proceso = subprocess.run(
            argumentos, shell=False, cwd=str(directorio),
            capture_output=True, text=True, timeout=TIMEOUT,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return f"El comando tardó más de {TIMEOUT}s y se canceló."
    except FileNotFoundError:
        return f"No se encontró el programa '{argumentos[0]}' en el sistema."
    except Exception as e:
        return f"Error al ejecutar: {e}"

    salida = ((proceso.stdout or "") + (proceso.stderr or "")).strip() or "(sin salida)"
    if len(salida) > MAX_SALIDA:
        salida = salida[:MAX_SALIDA] + "\n... (salida recortada)"
    return f"[código {proceso.returncode}]\n{salida}"


def _carpeta(carpeta: str | None) -> Path:
    if not carpeta:
        return BASE_DIR
    destino = ruta_segura(carpeta)
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def ejecutar(comando: str, carpeta: str | None = None) -> str:
    """Ejecuta UN comando (sin tuberías ni encadenado) dentro del workspace."""
    if OPERADORES_SHELL.search(comando):
        return ("RECHAZADO: no se permiten operadores de shell (; && || | > < ` $). "
                "Ejecuta un solo comando por llamada.")
    try:
        argumentos = shlex.split(comando)
    except ValueError as e:
        return f"No se pudo interpretar el comando: {e}"
    error = _validar(argumentos)
    if error:
        return "RECHAZADO: " + error
    try:
        directorio = _carpeta(carpeta)
    except ValueError as e:
        return f"RECHAZADO: {e}"
    return _correr(argumentos, directorio)


NOMBRE_PAQUETE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-\[\]=<>~!,@/]*$")


def instalar_dependencia(paquete: str, gestor: str = "pip") -> str:
    """Instala un paquete con pip o npm (en el entorno actual / en el workspace)."""
    gestor = (gestor or "pip").lower().strip()
    paquete = (paquete or "").strip()
    if not NOMBRE_PAQUETE.match(paquete) or ".." in paquete:
        return f"Nombre de paquete no válido: '{paquete}'."
    if gestor == "pip":
        # sys.executable -m pip instala en el MISMO Python que corre el agente.
        return _correr([sys.executable, "-m", "pip", "install", paquete], BASE_DIR)
    if gestor == "npm":
        return _correr(["npm", "install", paquete], BASE_DIR)
    if gestor == "apt":
        return ("No instalo paquetes del sistema (apt necesita sudo). "
                f"Instálalo tú con: sudo apt-get install {paquete}")
    return f"Gestor desconocido '{gestor}'. Usa pip o npm."


def git(accion: str, mensaje: str | None = None, carpeta: str | None = None) -> str:
    """Operaciones git comunes: init, status, add, commit, log."""
    accion = (accion or "").lower().strip()
    try:
        directorio = _carpeta(carpeta)
    except ValueError as e:
        return f"RECHAZADO: {e}"

    if accion == "commit":
        # El mensaje va como argumento separado: no se puede inyectar nada.
        r_add = _correr(["git", "add", "."], directorio)
        r_commit = _correr(["git", "commit", "-m", mensaje or "actualización"], directorio)
        return f"git add .\n{r_add}\n\ngit commit\n{r_commit}"

    acciones = {
        "init": ["git", "init"],
        "status": ["git", "status"],
        "add": ["git", "add", "."],
        "log": ["git", "log", "--oneline", "-10"],
    }
    if accion not in acciones:
        return f"Acción git desconocida '{accion}'. Usa init, status, add, commit o log."
    return _correr(acciones[accion], directorio)
