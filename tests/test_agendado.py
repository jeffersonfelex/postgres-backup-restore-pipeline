from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

import agendado
from config import Config

AGORA = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
ANTIGO = AGORA - timedelta(days=1)


@pytest.fixture(autouse=True)
def config_basica(monkeypatch):
    monkeypatch.setattr(Config, "PASTAS_ALVO", ["NORTE", "SUL", "CENTRO"])
    monkeypatch.setattr(Config, "MINUTOS_ESTABILIZACAO", 30)


@pytest.fixture
def estado(monkeypatch):
    dados = {}
    monkeypatch.setattr(agendado.controle, "ler_estado", lambda pasta: dados.get(pasta))
    return dados


def test_detecta_apenas_arquivos_novos(estado):
    estado["NORTE"] = (100, ANTIGO)  # igual ao remoto: já processado
    remotos = {
        "BKP_NORTE_PROD.zip": (100, ANTIGO),
        "BKP_SUL_PROD.zip": (200, ANTIGO),
    }

    novos = agendado.escolher_arquivos_novos(remotos, AGORA)

    assert list(novos) == ["SUL"]  # NORTE já feito, CENTRO ainda não chegou


def test_arquivo_com_mesmo_nome_mas_mtime_diferente_e_novo(estado):
    estado["NORTE"] = (100, ANTIGO - timedelta(days=30))
    remotos = {"BKP_NORTE_PROD.zip": (100, ANTIGO)}

    assert "NORTE" in agendado.escolher_arquivos_novos(remotos, AGORA)


def test_arquivo_recem_modificado_espera_proxima_verificacao(estado):
    remotos = {"BKP_CENTRO_PROD.zip": (500, AGORA - timedelta(minutes=5))}

    assert agendado.escolher_arquivos_novos(remotos, AGORA) == {}


def test_varios_arquivos_da_mesma_base_escolhe_o_mais_recente(estado):
    remotos = {
        "BKP_NORTE_PROD.zip": (100, ANTIGO - timedelta(days=30)),
        "BKP_NORTE_2_PROD.zip": (150, ANTIGO),
    }

    novos = agendado.escolher_arquivos_novos(remotos, AGORA)

    assert novos["NORTE"][0] == "BKP_NORTE_2_PROD.zip"


def _preparar_executar(monkeypatch, novos, resultados):
    monkeypatch.setattr(Config, "validar", lambda: None)
    monkeypatch.setattr(agendado.controle, "garantir_banco_controle", lambda: None)
    monkeypatch.setattr(agendado, "listar_arquivos_remotos", lambda: {})
    monkeypatch.setattr(agendado, "escolher_arquivos_novos", lambda r, a: novos)
    monkeypatch.setattr(agendado, "processar_pasta", lambda pasta, arq: resultados[pasta])
    registrar = MagicMock()
    monkeypatch.setattr(agendado.controle, "registrar_execucao", registrar)
    return registrar


def test_executar_sem_novidade_nao_registra_nada(monkeypatch):
    registrar = _preparar_executar(monkeypatch, {}, {})

    assert agendado.executar() is True
    registrar.assert_not_called()


def test_executar_registra_sucesso_e_erro_por_base(monkeypatch):
    novos = {"NORTE": ("norte.zip", 1, ANTIGO), "CENTRO": ("centro.zip", 2, ANTIGO)}
    resultados = {"NORTE": (True, "ok"), "CENTRO": (False, "falha no download")}
    registrar = _preparar_executar(monkeypatch, novos, resultados)

    assert agendado.executar() is False

    status = {c.args[0]: c.args[5] for c in registrar.call_args_list}
    assert status == {"NORTE": True, "CENTRO": False}


def test_executar_erro_inesperado_numa_base_nao_impede_as_outras(monkeypatch):
    novos = {"NORTE": ("norte.zip", 1, ANTIGO), "CENTRO": ("centro.zip", 2, ANTIGO)}
    registrar = _preparar_executar(monkeypatch, novos, {"CENTRO": (True, "ok")})

    def processar(pasta, arquivo):
        if pasta == "NORTE":
            raise ValueError("quebrou")
        return True, "ok"

    monkeypatch.setattr(agendado, "processar_pasta", processar)

    assert agendado.executar() is False
    assert registrar.call_count == 2


def test_executar_notifica_resumo_so_quando_processou_algo(monkeypatch):
    notificar = MagicMock()
    monkeypatch.setattr(agendado, "notificar_teams", notificar)

    _preparar_executar(monkeypatch, {}, {})
    agendado.executar()
    notificar.assert_not_called()  # nada novo: sem mensagem diária

    novos = {"NORTE": ("norte.zip", 1, ANTIGO), "CENTRO": ("centro.zip", 2, ANTIGO)}
    _preparar_executar(monkeypatch, novos, {"NORTE": (True, "ok"), "CENTRO": (False, "falha no download")})
    agendado.executar()

    titulo, linhas = notificar.call_args.args
    assert "falha" in titulo
    assert any("NORTE" in l and "✅" in l for l in linhas)
    assert any("CENTRO" in l and "❌" in l for l in linhas)
