"""
app.py — abre la interfaz gráfica del agente.

La interfaz es una página HTML/CSS (carpeta interfaz/static) servida por un
servidor local. Se dibuja con un motor web, así que las letras y las esquinas
se ven suaves y nítidas igual en Linux, Windows y macOS.

Cómo se abre la ventana (en este orden):
  1. pywebview  -> ventana nativa propia            (pip install pywebview)
  2. Chrome / Chromium / Edge / Brave en "modo app" -> ventana sin pestañas
  3. el navegador predeterminado

Opciones:
  python app.py               abre la ventana
  python app.py --navegador   salta pywebview y usa Chrome/Edge o el navegador
  python app.py --servidor    solo arranca el servidor y muestra la dirección
"""

import os
import sys
import time
import socket
import shutil
import logging
import secrets
import argparse
import platform
import threading
import subprocess
import webbrowser
import urllib.request

RAIZ = os.path.dirname(os.path.abspath(__file__))
TITULO = "Agente de IA Local"


def puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def arrancar_servidor(puerto, token):
    from interfaz import servidor

    # Silencia los mensajes de Flask/Werkzeug en la terminal.
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    import flask.cli
    flask.cli.show_server_banner = lambda *a, **k: None

    app, _, _ = servidor.crear_app(token, hosts_permitidos={"127.0.0.1", "localhost"})
    hilo = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=puerto, threaded=True, use_reloader=False),
        daemon=True,
    )
    hilo.start()

    url = f"http://127.0.0.1:{puerto}/"
    for _ in range(100):  # espera hasta 10 s a que responda
        try:
            urllib.request.urlopen(url, timeout=0.5).close()
            break
        except OSError:
            time.sleep(0.1)
    return url


def abrir_con_pywebview(url):
    """Ventana nativa. En Linux necesita Qt (pip install "pywebview[qt]") o GTK."""
    try:
        import webview
    except ImportError:
        return False
    try:
        try:
            webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        except Exception:
            pass
        webview.create_window(TITULO, url, width=1200, height=820, min_size=(380, 560),
                              background_color="#f4f2ec", text_select=True)
        webview.start(private_mode=False, storage_path=os.path.join(RAIZ, ".ventana"))
        return True
    except Exception as e:
        print(f"(pywebview no pudo abrir la ventana: {e})")
        return False


def buscar_chromium():
    """Busca un navegador basado en Chromium para abrirlo en modo aplicación."""
    nombres = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
               "microsoft-edge", "microsoft-edge-stable", "brave-browser", "vivaldi"]
    for n in nombres:
        ruta = shutil.which(n)
        if ruta:
            return ruta
    sistema = platform.system()
    candidatos = []
    if sistema == "Windows":
        for base in (os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                     os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                     os.environ.get("LOCALAPPDATA", "")):
            candidatos += [os.path.join(base, r"Microsoft\Edge\Application\msedge.exe"),
                           os.path.join(base, r"Google\Chrome\Application\chrome.exe")]
    elif sistema == "Darwin":
        candidatos += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                       "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                       "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    for c in candidatos:
        if c and os.path.exists(c):
            return c
    return None


def abrir_en_modo_app(url):
    navegador = buscar_chromium()
    if not navegador:
        return False
    perfil = os.path.join(RAIZ, ".ventana")  # perfil propio: ventana independiente
    try:
        proceso = subprocess.Popen([
            navegador, f"--app={url}", f"--user-data-dir={perfil}",
            "--window-size=1200,820", "--no-first-run", "--no-default-browser-check",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    inicio = time.time()
    codigo = proceso.wait()  # el programa termina cuando cierras la ventana
    if codigo != 0 and time.time() - inicio < 3:
        print(f"(El navegador se cerró al arrancar, código {codigo}; pruebo otra forma)")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description=TITULO)
    parser.add_argument("--navegador", action="store_true", help="no usar pywebview")
    parser.add_argument("--servidor", action="store_true", help="solo arrancar el servidor")
    parser.add_argument("--puerto", type=int, default=0, help="puerto fijo (por defecto, uno libre)")
    args = parser.parse_args()

    os.chdir(RAIZ)
    token = secrets.token_urlsafe(24)
    url = arrancar_servidor(args.puerto or puerto_libre(), token)

    if not args.servidor:
        if not args.navegador and abrir_con_pywebview(url):
            return
        if abrir_en_modo_app(url):
            return
        webbrowser.open(url)

    print(f"{TITULO} funcionando en {url}")
    print("Pulsa Ctrl+C para cerrar.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main())
