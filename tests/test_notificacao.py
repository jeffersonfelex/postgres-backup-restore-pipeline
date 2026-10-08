import json
from unittest.mock import MagicMock

from config import Config
from scripts.core import notificacao


def test_sem_url_configurada_nao_envia(monkeypatch):
    monkeypatch.setattr(Config, "TEAMS_WEBHOOK_URL", None)
    urlopen = MagicMock()
    monkeypatch.setattr(notificacao.urllib.request, "urlopen", urlopen)

    assert notificacao.notificar_teams("t", ["a"]) is False
    urlopen.assert_not_called()


def test_envia_cartao_adaptativo_com_titulo_e_linhas(monkeypatch):
    monkeypatch.setattr(Config, "TEAMS_WEBHOOK_URL", "https://exemplo.test/hook")
    resposta = MagicMock(status=202)
    resposta.__enter__.return_value = resposta
    urlopen = MagicMock(return_value=resposta)
    monkeypatch.setattr(notificacao.urllib.request, "urlopen", urlopen)

    assert notificacao.notificar_teams("Titulo", ["linha 1", "linha 2"]) is True

    requisicao = urlopen.call_args.args[0]
    corpo = json.loads(requisicao.data)["attachments"][0]["content"]["body"]
    assert corpo[0]["text"] == "Titulo"
    assert "linha 1" in corpo[1]["text"] and "linha 2" in corpo[1]["text"]


def test_falha_de_rede_nao_levanta_excecao(monkeypatch):
    monkeypatch.setattr(Config, "TEAMS_WEBHOOK_URL", "https://exemplo.test/hook")
    monkeypatch.setattr(notificacao.urllib.request, "urlopen", MagicMock(side_effect=OSError("sem rede")))

    assert notificacao.notificar_teams("t", ["a"]) is False
