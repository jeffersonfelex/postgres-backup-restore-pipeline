import os
import time

import pytest

from scripts.core.utils import (
    PipelineEmExecucaoError,
    encontrar_arquivo_por_extensao,
    formatar_mb,
    formatar_velocidade,
    garantir_pasta,
    identificar_pasta,
    lock_execucao,
)


def test_formatar_mb():
    assert formatar_mb(1024 * 1024) == "1.0 MB"
    assert formatar_mb(0) == "0.0 MB"
    assert formatar_mb(5 * 1024 * 1024) == "5.0 MB"


def test_formatar_velocidade():
    assert formatar_velocidade(10 * 1024 * 1024, 2) == "5.0 MB/s"


def test_formatar_velocidade_tempo_zero_ou_negativo():
    assert formatar_velocidade(100, 0) == "0.0 MB/s"
    assert formatar_velocidade(100, -1) == "0.0 MB/s"


def test_identificar_pasta_encontra_match():
    mapeamento = {"NORTE": "NORTE", "SUL": "SUL"}
    assert identificar_pasta("BKP_NORTE_2024_PROD.zip", mapeamento) == "NORTE"


def test_identificar_pasta_sem_match_retorna_none():
    mapeamento = {"NORTE": "NORTE"}
    assert identificar_pasta("BKP_OUTRO_PROD.zip", mapeamento) is None


def test_garantir_pasta_cria_diretorio(tmp_path):
    alvo = tmp_path / "subpasta" / "aninhada"
    resultado = garantir_pasta(str(alvo))
    assert os.path.isdir(alvo)
    assert resultado == str(alvo)


def test_garantir_pasta_nao_falha_se_ja_existir(tmp_path):
    alvo = tmp_path / "existente"
    os.makedirs(alvo)
    garantir_pasta(str(alvo))  # não deve levantar exceção


def test_encontrar_arquivo_por_extensao_encontra(tmp_path):
    (tmp_path / "dump.sql").write_text("select 1;")
    (tmp_path / "outro.txt").write_text("irrelevante")

    caminho = encontrar_arquivo_por_extensao(str(tmp_path), ".sql")
    assert caminho == str(tmp_path / "dump.sql")


def test_encontrar_arquivo_por_extensao_nao_encontra(tmp_path):
    (tmp_path / "outro.txt").write_text("irrelevante")
    assert encontrar_arquivo_por_extensao(str(tmp_path), ".sql") is None


def test_encontrar_arquivo_por_extensao_pasta_inexistente(tmp_path):
    assert encontrar_arquivo_por_extensao(str(tmp_path / "nao_existe"), ".sql") is None


def test_lock_execucao_cria_e_libera_arquivo(tmp_path):
    caminho_lock = str(tmp_path / "pipeline.lock")

    with lock_execucao(caminho_lock, timeout_segundos=3600):
        assert os.path.exists(caminho_lock)

    assert not os.path.exists(caminho_lock)


def test_lock_execucao_bloqueia_execucao_concorrente(tmp_path):
    caminho_lock = str(tmp_path / "pipeline.lock")

    with lock_execucao(caminho_lock, timeout_segundos=3600):
        with pytest.raises(PipelineEmExecucaoError):
            with lock_execucao(caminho_lock, timeout_segundos=3600):
                pass


def test_lock_execucao_libera_mesmo_com_erro(tmp_path):
    caminho_lock = str(tmp_path / "pipeline.lock")

    with pytest.raises(ValueError):
        with lock_execucao(caminho_lock, timeout_segundos=3600):
            raise ValueError("falha simulada")

    assert not os.path.exists(caminho_lock)


def test_lock_execucao_destrava_lock_velho(tmp_path):
    caminho_lock = str(tmp_path / "pipeline.lock")
    with open(caminho_lock, "w") as f:
        f.write("12345")

    tempo_antigo = time.time() - 100
    os.utime(caminho_lock, (tempo_antigo, tempo_antigo))

    with lock_execucao(caminho_lock, timeout_segundos=10):
        assert os.path.exists(caminho_lock)


def test_lock_execucao_renova_o_lock_enquanto_executa(tmp_path):
    import time

    caminho_lock = str(tmp_path / "pipeline.lock")

    with lock_execucao(caminho_lock, timeout_segundos=3600, intervalo_renovacao=0.05):
        antigo = time.time() - 1000
        os.utime(caminho_lock, (antigo, antigo))
        time.sleep(0.3)

        assert os.path.getmtime(caminho_lock) > antigo + 500
