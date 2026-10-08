import os
import re
import subprocess
import concurrent.futures

from config import Config
from logger import get_logger
from scripts.core.utils import encontrar_arquivo_por_extensao

log = get_logger("restauracao")


_ERRO_DE_ROLE = re.compile(r'role ".+" .*exist')


def _somente_erros_de_role(stderr: str) -> bool:
    """True se todos os erros do pg_restore são de role inexistente (GRANT/OWNER/privilégios)."""
    erros = [linha for linha in stderr.splitlines() if linha.startswith("pg_restore: error")]
    return bool(erros) and all(_ERRO_DE_ROLE.search(linha) for linha in erros)


def restaurar_banco(pasta: str) -> bool:
    caminho_subpasta = os.path.join(Config.LOCAL_DIR, pasta)

    if not os.path.exists(caminho_subpasta):
        log.warning(f"[{pasta}] A pasta {caminho_subpasta} não existe. Ignorando.")
        return False

    caminho_sql = encontrar_arquivo_por_extensao(caminho_subpasta, ".sql")
    if not caminho_sql:
        log.warning(f"[{pasta}] Nenhum arquivo .sql encontrado na pasta {caminho_subpasta}.")
        return False

    nome_banco = f"{Config.DB_PREFIXO}{pasta}"

    log.info(f"[{pasta}] Iniciando restauração no banco '{nome_banco}'...")

    comando = [
        Config.PG_RESTORE_PATH,
        "-h", Config.DB_HOST,
        "-U", Config.DB_USER,
        "-p", Config.DB_PORT,
        "-d", nome_banco,
        "-c",
        "--if-exists",
        caminho_sql,
    ]

    ambiente = os.environ.copy()
    ambiente["PGPASSWORD"] = Config.DB_PASS

    try:
        processo = subprocess.run(comando, env=ambiente, capture_output=True, text=True)

        if processo.returncode != 0:
            if not _somente_erros_de_role(processo.stderr):
                log.error(f"[{pasta}] ERRO na restauração:\n{processo.stderr}")
                return False
            log.warning(
                f"[{pasta}] pg_restore terminou com avisos: só GRANTs/owners de roles que não "
                f"existem neste servidor foram ignorados. Dados restaurados normalmente."
            )

        log.info(f"[{pasta}] CONCLUÍDO! Banco '{nome_banco}' restaurado com sucesso.")

        try:
            os.remove(caminho_sql)
        except OSError as erro:
            log.warning(f"[{pasta}] Restauração ok, mas falhou ao apagar o .sql: {erro}")

        return True

    except FileNotFoundError:
        log.error(
            f"[{pasta}] O executável do pg_restore não foi encontrado em "
            f"'{Config.PG_RESTORE_PATH}'. Verifique o caminho no .env."
        )
        return False
    except Exception as erro:
        log.error(f"[{pasta}] Ocorreu um erro inesperado: {erro}")
        return False


def iniciar_restauracao():
    log.info(f"Verificando arquivos em: {Config.LOCAL_DIR}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=Config.MAX_TRABALHOS_PARALELOS) as executor:
        resultados = list(executor.map(restaurar_banco, Config.PASTAS_ALVO))

    if not all(resultados):
        falharam = [p for p, ok in zip(Config.PASTAS_ALVO, resultados) if not ok]
        raise RuntimeError(f"A restauração falhou (ou foi ignorada) para: {falharam}")

    log.info("Processo de restauração finalizado com sucesso para todos os bancos!")


if __name__ == "__main__":
    iniciar_restauracao()