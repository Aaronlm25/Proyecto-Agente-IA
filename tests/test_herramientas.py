"""Pruebas de seguridad y de funcionamiento de las herramientas."""

import shutil

import pandas as pd
import pytest

from tools import filesystem, calendario, configuracion, terminal, datos


# ----------------- workspace / rutas -----------------

@pytest.mark.parametrize("ruta", ["../fuera", "../../fuera", "/etc", "a/../../fuera"])
def test_ruta_segura_bloquea_salidas(workspace, ruta):
    with pytest.raises(ValueError):
        filesystem.ruta_segura(ruta)


def test_ruta_segura_bloquea_carpeta_hermana(workspace):
    # Con startswith esto pasaba: /x/workspace_hermano empieza por /x/workspace
    with pytest.raises(ValueError):
        filesystem.ruta_segura(f"../{workspace.name}_hermano")


def test_crear_nota_con_titulo_malicioso_queda_dentro(workspace):
    filesystem.crear_nota("../../FUERA", "hola")
    notas = list((workspace / "notas").glob("*.md"))
    assert len(notas) == 1
    assert not (workspace.parent / "FUERA.md").exists()


def test_crear_proyecto_no_permite_subcarpetas_fuera(workspace):
    with pytest.raises(ValueError):
        filesystem.crear_proyecto("ok", ["src", "../../FUERA"])
    assert not (workspace / "ok").exists()  # no crea nada a medias


def test_crear_proyecto_normal(workspace):
    filesystem.crear_proyecto("tienda")
    for sub in ("src", "docs", "tests", "README.md"):
        assert (workspace / "tienda" / sub).exists()


# ----------------- configuración -----------------

def test_generar_config_no_sobrescribe_env(workspace):
    (workspace / "app").mkdir()
    (workspace / "app" / ".env").write_text("API_KEY=secreto\n")
    msg = configuracion.generar_config("app", "python")
    assert (workspace / "app" / ".env").read_text() == "API_KEY=secreto\n"
    assert ".env" in msg and "no se tocaron" in msg


def test_generar_config_fuera_del_workspace(workspace):
    with pytest.raises(ValueError):
        configuracion.generar_config("../../FUERA", "python")


# ----------------- calendario -----------------

def test_evento_que_cruza_medianoche(workspace):
    calendario.crear_evento("cena", "2026-12-31", "23:00", 2)
    ics = next((workspace / "calendario").glob("*.ics")).read_bytes().decode()
    assert "DTSTART:20261231T230000" in ics
    assert "DTEND:20270101T010000" in ics
    assert "UID:" in ics and "\r\n" in ics


def test_evento_duracion_como_texto(workspace):
    msg = calendario.crear_evento("x", "2026-12-01", "10:00", "1.5")
    assert "11:30" in msg


def test_evento_fecha_invalida(workspace):
    assert "Formato inválido" in calendario.crear_evento("x", "mañana", "10am")


def test_evento_titulo_malicioso(workspace):
    calendario.crear_evento("../../FUERA", "2026-01-01")
    assert len(list((workspace / "calendario").glob("*.ics"))) == 1


# ----------------- terminal -----------------

@pytest.mark.parametrize("comando", [
    "echo hola; whoami",
    "echo hola && whoami",
    "ls | head",
    "echo hola > archivo.txt",
    "rm -rf carpeta",
    "rm -r -f carpeta",
    "find / -delete",
    "cat /etc/passwd",
    "cat ~/.ssh/id_rsa",
    "cat ../../secreto",
    "python -c 'import os'",
    "curl http://ejemplo.com",
    "bash script.sh",
    "echo $(whoami)",
])
def test_terminal_rechaza_peligrosos(workspace, comando):
    assert terminal.ejecutar(comando).startswith("RECHAZADO")


def test_terminal_ejecuta_permitidos(workspace):
    r = terminal.ejecutar("echo hola mundo")
    assert "[código 0]" in r and "hola mundo" in r


def test_terminal_carpeta_fuera(workspace):
    assert terminal.ejecutar("ls", carpeta="../..").startswith("RECHAZADO")


@pytest.mark.parametrize("paquete", ["requests; rm -rf /", "x && whoami", "../evil", "$(whoami)", ""])
def test_instalar_rechaza_nombres_raros(workspace, paquete):
    assert "no válido" in terminal.instalar_dependencia(paquete)


def test_instalar_apt_no_usa_sudo(workspace):
    assert "sudo apt-get install htop" in terminal.instalar_dependencia("htop", "apt")


@pytest.mark.skipif(shutil.which("git") is None, reason="git no instalado")
def test_git_commit_sin_inyeccion(workspace):
    terminal.git("init", carpeta="repo")
    (workspace / "repo" / "a.txt").write_text("x")
    terminal._correr(["git", "config", "user.email", "t@t"], workspace / "repo")
    terminal._correr(["git", "config", "user.name", "t"], workspace / "repo")
    r = terminal.git("commit", mensaje='x" ; echo INYECTADO ; echo "', carpeta="repo")
    assert "INYECTADO\n" not in r.replace("echo INYECTADO", "")
    log = terminal.git("log", carpeta="repo")
    assert "echo INYECTADO" in log  # el texto quedó como mensaje, no se ejecutó


# ----------------- datos (código generado) -----------------

@pytest.mark.parametrize("codigo", [
    "import os\nresultado = os.getcwd()",
    "from os import getcwd\nresultado = getcwd()",
    "import pathlib\npathlib.Path('x').write_text('y')",
    "resultado = open('/etc/passwd').read()",
    "resultado = pd.read_csv('/etc/passwd')",
    "df.to_csv('/tmp/robado.csv')",
    "resultado = df.__class__.__bases__",
    "resultado = getattr(df, 'to_csv')",
    "resultado = eval('1+1')",
    "resultado = df.query('a > 1')",
])
def test_datos_bloquea_codigo_peligroso(codigo):
    with pytest.raises(ValueError):
        datos._ejecutar(codigo, pd.DataFrame({"a": [1, 2]}))


def test_datos_permite_pandas_normal():
    df = pd.DataFrame({"mes": ["ene", "ene", "feb"], "ventas": [10, 5, 7]})
    entorno, _ = datos._ejecutar(
        "resultado = df.groupby('mes')['ventas'].sum().to_dict()", df)
    assert entorno["resultado"] == {"ene": 15, "feb": 7}


def test_analizar_tabla_con_modelo_falso(workspace, modelo):
    ruta = workspace / "ventas.csv"
    pd.DataFrame({"producto": ["a", "b"], "total": [100, 250]}).to_csv(ruta, index=False)
    modelo({"codigo": [("texto", "```python\nresultado = df['total'].sum()\n```")]})
    assert datos.analizar_tabla(str(ruta), "¿cuánto vendí?") == "350"


def test_graficar_tabla_crea_png(workspace, modelo):
    ruta = workspace / "ventas.csv"
    pd.DataFrame({"mes": ["ene", "feb"], "total": [1, 2]}).to_csv(ruta, index=False)
    modelo({"codigo": [("texto", "plt.bar(df['mes'], df['total'])\nplt.title('Ventas')")]})
    msg = datos.graficar_tabla(str(ruta), "barras")
    assert "Gráfica creada" in msg
    assert list((workspace / "graficas").glob("*.png"))
