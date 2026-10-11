"""ajustes.json es el único lugar donde se eligen los modelos."""

import json

from agentes import config


def test_config_lee_los_modelos_de_ajustes(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MODELO", "respaldo")
    monkeypatch.setattr(config, "MODELO_VISION", "respaldo-vision")
    ruta = tmp_path / "ajustes.json"
    ruta.write_text(json.dumps({"modelo": "qwen3:8b", "modelo_vision": "llama3.2-vision"}))
    config.cargar_ajustes(str(ruta))
    assert config.MODELO == "qwen3:8b"
    assert config.MODELO_VISION == "llama3.2-vision"


def test_sin_ajustes_se_quedan_los_de_respaldo(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MODELO", "respaldo")
    config.cargar_ajustes(str(tmp_path / "no_existe.json"))
    assert config.MODELO == "respaldo"
    (tmp_path / "roto.json").write_text("{esto no es json")
    config.cargar_ajustes(str(tmp_path / "roto.json"))
    assert config.MODELO == "respaldo"


def test_claves_vacias_no_borran_el_modelo(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MODELO", "respaldo")
    ruta = tmp_path / "ajustes.json"
    ruta.write_text(json.dumps({"modelo": "  ", "tema": "dark"}))
    config.cargar_ajustes(str(ruta))
    assert config.MODELO == "respaldo"


def test_los_agentes_usan_el_modelo_actual(monkeypatch):
    from agentes.especialistas import ESPECIALISTAS
    monkeypatch.setattr(config, "MODELO", "qwen3:8b")
    assert all(a.modelo == "qwen3:8b" for a in ESPECIALISTAS.values())
