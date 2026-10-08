import pytest

from config import Config


def test_validar_passa_com_tudo_preenchido(monkeypatch):
    for nome in Config._OBRIGATORIAS:
        monkeypatch.setattr(Config, nome, "valor")

    Config.validar()  # não deve levantar exceção


def test_validar_falha_e_lista_variaveis_faltando(monkeypatch):
    for nome in Config._OBRIGATORIAS:
        monkeypatch.setattr(Config, nome, "valor")

    monkeypatch.setattr(Config, "DB_PASS", None)
    monkeypatch.setattr(Config, "HOST", "")

    with pytest.raises(RuntimeError) as exc_info:
        Config.validar()

    assert "DB_PASS" in str(exc_info.value)
    assert "HOST" in str(exc_info.value)
