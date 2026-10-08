import os
import zipfile

from scripts.etapas.extrair_recuperacao import processar_arquivo_zip


def _criar_zip(caminho_zip: str, arquivos: dict[str, bytes]):
    with zipfile.ZipFile(caminho_zip, "w") as z:
        for nome, conteudo in arquivos.items():
            z.writestr(nome, conteudo)


def test_processar_arquivo_zip_extrai_sql_e_apaga_zip(tmp_path):
    caminho_zip = str(tmp_path / "BKP_NORTE_PROD.zip")
    _criar_zip(caminho_zip, {"dump.sql": b"select 1;"})

    resultado = processar_arquivo_zip(caminho_zip)

    assert resultado is True
    assert not os.path.exists(caminho_zip)
    caminho_sql = tmp_path / "dump.sql"
    assert caminho_sql.exists()
    assert caminho_sql.read_bytes() == b"select 1;"


def test_processar_arquivo_zip_sem_sql_mantem_zip(tmp_path):
    caminho_zip = str(tmp_path / "BKP_NORTE_PROD.zip")
    _criar_zip(caminho_zip, {"leia_me.txt": b"nada aqui"})

    resultado = processar_arquivo_zip(caminho_zip)

    assert resultado is False
    assert os.path.exists(caminho_zip)


def test_processar_arquivo_zip_corrompido_retorna_false(tmp_path):
    caminho_zip = str(tmp_path / "corrompido_PROD.zip")
    with open(caminho_zip, "wb") as f:
        f.write(b"isso nao e um zip valido")

    resultado = processar_arquivo_zip(caminho_zip)

    assert resultado is False
    assert os.path.exists(caminho_zip)
