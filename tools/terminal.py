"""
tools/terminal.py

Ejecuta comandos del sistema desde el agente. Devuelve STRINGS para
encajar con agente.py (van directo a {"role": "tool", "content": ...}).

Usa el MISMO workspace que filesystem.py: project_root/workspace.
Seguridad: lista negra de patrones peligrosos + todo corre dentro del
workspace + timeout.
"""

import subprocess
from pathlib import Path

# Mismo workspace que filesystem.py (un nivel arriba de tools/).
BASE_DIR = Path(__file__).resolve().parent.parent / "workspace"
BASE_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT = 60  # segundos maximos por comando

# Patrones que NUNCA se ejecutan (borrado masivo, formateo, apagado, etc.)
PELIGROSOS = [
    "rm -rf", "rm -fr", "mkfs", "dd if=", ":(){", "shutdown", "reboot",
    "> /dev/sd", "chmod -r 777 /", "mv / ", "sudo rm", "del /f", "format ",
    "rmdir /s",
]


def _es_peligroso(comando: str) -> bool:
    bajo = comando.lower()
    return any(p in bajo for p in PELIGROSOS)


def _carpeta_segura(carpeta: str | None) -> Path:
    """Devuelve una carpeta dentro del workspace, sin escapar de el."""
    if not carpeta:
        return BASE_DIR
    destino = (BASE_DIR / carpeta).resolve()
    if not str(destino).startswith(str(BASE_DIR.resolve())):
        return BASE_DIR
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def ejecutar(comando: str, carpeta: str | None = None) -> str:
    """Ejecuta un comando de shell dentro del workspace y devuelve su salida."""
    if _es_peligroso(comando):
        return f"RECHAZADO por seguridad: el comando '{comando}' parece destructivo."

    directorio = _carpeta_segura(carpeta)

    try:
        proceso = subprocess.run(
            comando, shell=True, cwd=str(directorio),
            capture_output=True, text=True, timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return f"El comando tardo mas de {TIMEOUT}s y se cancelo."
    except Exception as e:
        return f"Error al ejecutar: {e}"

    salida = (proceso.stdout or "") + (proceso.stderr or "")
    salida = salida.strip() or "(sin salida)"
    if len(salida) > 3000:
        salida = salida[:3000] + "\n... (salida recortada)"
    return f"[codigo {proceso.returncode}]\n{salida}"


def instalar_dependencia(paquete: str, gestor: str = "pip") -> str:
    """Instala un paquete con pip, npm o apt."""
    gestor = gestor.lower().strip()
    comandos = {
        "pip": f"pip install {paquete}",
        "npm": f"npm install {paquete}",
        "apt": f"sudo apt-get install -y {paquete}",
    }
    if gestor not in comandos:
        return f"Gestor desconocido '{gestor}'. Usa pip, npm o apt."
    return ejecutar(comandos[gestor])


def git(accion: str, mensaje: str | None = None, carpeta: str | None = None) -> str:
    """Operaciones git comunes: init, status, add, commit, log."""
    acciones = {
        "init": "git init",
        "status": "git status",
        "add": "git add .",
        "log": "git log --oneline -10",
        "commit": f'git add . && git commit -m "{mensaje or "actualizacion"}"',
    }
    cmd = acciones.get(accion.lower().strip())
    if not cmd:
        return f"Accion git desconocida '{accion}'. Usa init, status, add, commit o log."
    return ejecutar(cmd, carpeta=carpeta)
