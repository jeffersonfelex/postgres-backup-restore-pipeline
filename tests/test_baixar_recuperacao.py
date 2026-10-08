import os
import socket
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from config import Config
from scripts.etapas import baixar_recuperacao


class FakeRemoteFile:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def seek(self, n):
        self.pos = n

    def read(self, n):
        pedaco = self.data[self.pos:self.pos + n]
        self.pos += len(pedaco)
        return pedaco

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeSFTP:
    def __init__(self, remote_data: bytes, existe: bool = True):
        self.remote_data = remote_data
        self.existe = existe

    def stat(self, path):
        if not self.existe:
            raise FileNotFoundError()
        return SimpleNamespace(st_size=len(self.remote_data))

    def open(self, path, mode):
        return FakeRemoteFile(self.remote_data)

    def close(self):
        pass


class FakeSSH:
    def __init__(self, sftp: FakeSFTP):
        self._sftp = sftp

    def open_sftp(self):
        return self._sftp

    def close(self):
        pass


@pytest.fixture(autouse=True)
def config_padrao(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "MAPEAMENTO_NOMES", {"NORTE": "NORTE"})
    monkeypatch.setattr(Config, "LOCAL_DIR", str(tmp_path))
    monkeypatch.setattr(Config, "REMOTE_DIR", "/remoto")
    monkeypatch.setattr(Config, "TAMANHO_BLOCO", 4)
    monkeypatch.setattr(Config, "LOG_PROGRESSO_A_CADA", 1024)
    monkeypatch.setattr(Config, "MAX_TENTATIVAS", 3)
    monkeypatch.setattr(Config, "ESPERA_ENTRE_TENTATIVAS", 0)
    return tmp_path


def test_baixar_arquivo_pasta_nao_mapeada_nao_conecta(monkeypatch):
    mock_conexao = MagicMock()
    monkeypatch.setattr(baixar_recuperacao, "abrir_conexao", mock_conexao)

    resultado = baixar_recuperacao.baixar_arquivo("BKP_DESCONHECIDO_PROD.zip")

    assert resultado is False
    mock_conexao.assert_not_called()


def test_baixar_arquivo_ja_completo_nao_baixa_de_novo(tmp_path, monkeypatch):
    pasta = tmp_path / "NORTE"
    pasta.mkdir()
    (pasta / "BKP_NORTE_PROD.zip").write_bytes(b"conteudo completo")

    sftp = FakeSFTP(remote_data=b"conteudo completo")
    monkeypatch.setattr(baixar_recuperacao, "abrir_conexao", lambda: FakeSSH(sftp))

    resultado = baixar_recuperacao.baixar_arquivo("BKP_NORTE_PROD.zip")

    assert resultado is True


def test_baixar_arquivo_download_do_zero(monkeypatch):
    sftp = FakeSFTP(remote_data=b"0123456789")
    monkeypatch.setattr(baixar_recuperacao, "abrir_conexao", lambda: FakeSSH(sftp))

    resultado = baixar_recuperacao.baixar_arquivo("BKP_NORTE_PROD.zip")

    assert resultado is True
    caminho = os.path.join(Config.LOCAL_DIR, "NORTE", "BKP_NORTE_PROD.zip")
    assert open(caminho, "rb").read() == b"0123456789"


def test_baixar_arquivo_retoma_download_parcial(tmp_path, monkeypatch):
    pasta = tmp_path / "NORTE"
    pasta.mkdir()
    (pasta / "BKP_NORTE_PROD.zip").write_bytes(b"01234")

    sftp = FakeSFTP(remote_data=b"0123456789")
    monkeypatch.setattr(baixar_recuperacao, "abrir_conexao", lambda: FakeSSH(sftp))

    resultado = baixar_recuperacao.baixar_arquivo("BKP_NORTE_PROD.zip")

    assert resultado is True
    caminho = pasta / "BKP_NORTE_PROD.zip"
    assert caminho.read_bytes() == b"0123456789"


def test_baixar_arquivo_arquivo_remoto_sumiu_nao_tenta_de_novo(monkeypatch):
    sftp = FakeSFTP(remote_data=b"", existe=False)
    mock_conexao = MagicMock(side_effect=lambda: FakeSSH(sftp))
    monkeypatch.setattr(baixar_recuperacao, "abrir_conexao", mock_conexao)

    resultado = baixar_recuperacao.baixar_arquivo("BKP_NORTE_PROD.zip")

    assert resultado is False
    assert mock_conexao.call_count == 1


def test_baixar_arquivo_recupera_apos_falha_de_conexao(monkeypatch):
    sftp = FakeSFTP(remote_data=b"0123456789")
    mock_conexao = MagicMock(side_effect=[socket.timeout(), FakeSSH(sftp)])
    monkeypatch.setattr(baixar_recuperacao, "abrir_conexao", mock_conexao)

    resultado = baixar_recuperacao.baixar_arquivo("BKP_NORTE_PROD.zip")

    assert resultado is True
    assert mock_conexao.call_count == 2


def test_baixar_arquivo_desiste_apos_max_tentativas(monkeypatch):
    mock_conexao = MagicMock(side_effect=socket.timeout())
    monkeypatch.setattr(baixar_recuperacao, "abrir_conexao", mock_conexao)

    resultado = baixar_recuperacao.baixar_arquivo("BKP_NORTE_PROD.zip")

    assert resultado is False
    assert mock_conexao.call_count == Config.MAX_TENTATIVAS
