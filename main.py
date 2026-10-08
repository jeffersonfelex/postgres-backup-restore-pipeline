import sys

from config import Config
from logger import get_logger
from scripts.core.utils import PipelineEmExecucaoError, lock_execucao
from scripts.etapas.baixar_recuperacao import iniciar_downloads
from scripts.etapas.extrair_recuperacao import iniciar_extracao
from scripts.etapas.restaurar_banco import iniciar_restauracao

log = get_logger("pipeline")


def executar_pipeline() -> bool:
    log.info("=" * 25 + " INICIANDO PIPELINE DE DADOS  " + "=" * 25)

    try:
        Config.validar()

        log.info("[ETAPA 1/3] - Iniciando downloads do servidor...")
        iniciar_downloads()

        log.info("[ETAPA 2/3] - Iniciando extração dos arquivos ZIP...")
        iniciar_extracao()

        log.info("[ETAPA 3/3] - Iniciando restauração no banco de dados...")
        iniciar_restauracao()

        log.info("Pipeline concluído com sucesso!")
        return True

    except Exception as e:
        log.error(f"[ERRO CRÍTICO] O pipeline foi interrompido: {e}")
        return False


if __name__ == "__main__":
    try:
        with lock_execucao(Config.LOCK_FILE_PATH, Config.LOCK_TIMEOUT_SEGUNDOS):
            sucesso = executar_pipeline()
    except PipelineEmExecucaoError as e:
        log.error(str(e))
        sucesso = False

    sys.exit(0 if sucesso else 1)