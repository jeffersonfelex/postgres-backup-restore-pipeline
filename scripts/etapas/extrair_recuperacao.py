import os
import zipfile
import shutil
import concurrent.futures

from config import Config
from logger import get_logger
from scripts.core.utils import garantir_pasta

log = get_logger("extracao")


def processar_arquivo_zip(caminho_zip: str) -> bool:
    pasta_pai = os.path.dirname(caminho_zip)
    nome_zip = os.path.basename(caminho_zip)

    try:
        with zipfile.ZipFile(caminho_zip, "r") as z:
            caminho_interno_sql = next(
                (nome for nome in z.namelist() if nome.endswith(".sql")), None
            )

            if not caminho_interno_sql:
                log.warning(f"[{nome_zip}] Nenhum arquivo .sql encontrado dentro do ZIP.")
                return False

            nome_final_sql = os.path.basename(caminho_interno_sql)
            caminho_destino_sql = os.path.join(pasta_pai, nome_final_sql)

            log.info(f"[{nome_final_sql}] Extraindo do ZIP...")

            with z.open(caminho_interno_sql) as origem, open(caminho_destino_sql, "wb") as destino:
                shutil.copyfileobj(origem, destino)

        os.remove(caminho_zip)
        log.info(f"[{nome_final_sql}] CONCLUÍDO e arquivo .zip original foi excluído.")
        return True

    except Exception as erro:
        log.error(f"[{nome_zip}] Erro ao processar o arquivo: {erro}")
        return False


def _limpar_sql_residual(pasta: str, caminho_subpasta: str) -> None:
    """Remove .sql de rodadas anteriores, para nunca restaurar um arquivo velho se a extração falhar."""
    for arquivo in os.listdir(caminho_subpasta):
        if arquivo.endswith(".sql"):
            caminho_sql_antigo = os.path.join(caminho_subpasta, arquivo)
            log.info(f"[{pasta}] Removendo .sql residual de execução anterior: {arquivo}")
            os.remove(caminho_sql_antigo)


def extrair_pasta(pasta: str) -> bool:
    """Extrai o(s) _PROD.zip de uma única pasta. False se não havia zip ou a extração falhou."""
    caminho_subpasta = garantir_pasta(os.path.join(Config.LOCAL_DIR, pasta))
    _limpar_sql_residual(pasta, caminho_subpasta)

    zips = [
        os.path.join(caminho_subpasta, arquivo)
        for arquivo in os.listdir(caminho_subpasta)
        if arquivo.endswith("_PROD.zip")
    ]
    if not zips:
        log.warning(f"[{pasta}] Nenhum arquivo ZIP encontrado para extração.")
        return False

    return all([processar_arquivo_zip(caminho_zip) for caminho_zip in zips])


def iniciar_extracao():
    zips_para_extrair = []

    log.info("Mapeando arquivos .zip nas pastas...")

    for pasta in Config.PASTAS_ALVO:
        caminho_subpasta = garantir_pasta(os.path.join(Config.LOCAL_DIR, pasta))

        _limpar_sql_residual(pasta, caminho_subpasta)

        for arquivo in os.listdir(caminho_subpasta):
            if arquivo.endswith("_PROD.zip"):
                zips_para_extrair.append(os.path.join(caminho_subpasta, arquivo))

    if not zips_para_extrair:
        log.warning("Nenhum arquivo ZIP encontrado para extração.")
        return

    log.info(f"Encontrados {len(zips_para_extrair)} arquivos ZIP. Iniciando extração simultânea...")

    with concurrent.futures.ThreadPoolExecutor(Config.MAX_TRABALHOS_PARALELOS) as executor:
        resultados = list(executor.map(processar_arquivo_zip, zips_para_extrair))

    if not all(resultados):
        falharam = [z for z, ok in zip(zips_para_extrair, resultados) if not ok]
        raise RuntimeError(f"A extração falhou para: {falharam}")

    log.info("Todos os arquivos foram extraídos e os ZIPs apagados com sucesso!")


if __name__ == "__main__":
    iniciar_extracao()