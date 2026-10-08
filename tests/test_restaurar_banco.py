import os
import subprocess
from unittest.mock import MagicMock

import pytest

from config import Config
from scripts.etapas import restaurar_banco


@pytest.fixture
def pasta_com_sql(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "LOCAL_DIR", str(tmp_path))
    monkeypatch.setattr(Config, "PG_RESTORE_PATH", "pg_restore")
    monkeypatch.setattr(Config, "DB_HOST", "localhost")
    monkeypatch.setattr(Config, "DB_USER", "usuario")
    monkeypatch.setattr(Config, "DB_PORT", "5432")
    monkeypatch.setattr(Config, "DB_PASS", "segredo")

    subpasta = tmp_path / "NORTE"
    subpasta.mkdir()
    (subpasta / "dump.sql").write_text("select 1;")
    return subpasta


def test_restaurar_banco_sucesso_apaga_sql(pasta_com_sql, monkeypatch):
    processo_ok = MagicMock(returncode=0, stderr="")
    mock_run = MagicMock(return_value=processo_ok)
    monkeypatch.setattr(subprocess, "run", mock_run)

    resultado = restaurar_banco.restaurar_banco("NORTE")

    assert resultado is True
    assert not (pasta_com_sql / "dump.sql").exists()

    comando = mock_run.call_args.args[0]
    assert comando[0] == "pg_restore"
    assert "RESTORE_NORTE" in comando

    ambiente = mock_run.call_args.kwargs["env"]
    assert ambiente["PGPASSWORD"] == "segredo"


def test_restaurar_banco_falha_pg_restore_mantem_sql(pasta_com_sql, monkeypatch):
    processo_falho = MagicMock(returncode=1, stderr="erro qualquer")
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=processo_falho))

    resultado = restaurar_banco.restaurar_banco("NORTE")

    assert resultado is False
    assert (pasta_com_sql / "dump.sql").exists()  # não apaga se a restauração falhou


def test_restaurar_banco_sem_pg_restore_instalado(pasta_com_sql, monkeypatch):
    monkeypatch.setattr(subprocess, "run", MagicMock(side_effect=FileNotFoundError()))

    resultado = restaurar_banco.restaurar_banco("NORTE")

    assert resultado is False


def test_restaurar_banco_pasta_inexistente(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "LOCAL_DIR", str(tmp_path))

    resultado = restaurar_banco.restaurar_banco("NAO_EXISTE")

    assert resultado is False


def test_restaurar_banco_sem_arquivo_sql(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "LOCAL_DIR", str(tmp_path))
    subpasta = tmp_path / "SUL"
    subpasta.mkdir()

    resultado = restaurar_banco.restaurar_banco("SUL")

    assert resultado is False


def test_iniciar_restauracao_levanta_erro_se_alguma_falhar(monkeypatch):
    monkeypatch.setattr(Config, "PASTAS_ALVO", ["NORTE", "SUL"])
    monkeypatch.setattr(Config, "MAX_TRABALHOS_PARALELOS", 2)
    monkeypatch.setattr(
        restaurar_banco, "restaurar_banco", lambda pasta: pasta == "NORTE"
    )

    with pytest.raises(RuntimeError, match="SUL"):
        restaurar_banco.iniciar_restauracao()


def test_restaurar_banco_erros_so_de_role_contam_como_sucesso(pasta_com_sql, monkeypatch):
    stderr = (
        'pg_restore: error: could not execute query: ERRO:  role "luan_silva" não existe\n'
        "Command was: GRANT SELECT ON TABLE public.teste TO luan_silva;\n\n"
        "pg_restore: warning: errors ignored on restore: 1\n"
    )
    monkeypatch.setattr(
        subprocess, "run", MagicMock(return_value=MagicMock(returncode=1, stderr=stderr))
    )

    assert restaurar_banco.restaurar_banco("NORTE") is True
    assert not (pasta_com_sql / "dump.sql").exists()


def test_restaurar_banco_erro_de_role_misturado_com_outro_erro_falha(pasta_com_sql, monkeypatch):
    stderr = (
        'pg_restore: error: could not execute query: ERRO:  role "luan_silva" não existe\n'
        "pg_restore: error: could not execute query: ERRO:  relation \"x\" already exists\n"
    )
    monkeypatch.setattr(
        subprocess, "run", MagicMock(return_value=MagicMock(returncode=1, stderr=stderr))
    )

    assert restaurar_banco.restaurar_banco("NORTE") is False
    assert (pasta_com_sql / "dump.sql").exists()
