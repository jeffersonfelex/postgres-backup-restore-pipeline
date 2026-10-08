"""Verificação periódica: processa cada base assim que um backup novo aparece no servidor."""
import sys
from datetime import datetime, timedelta, timezone

from config import Config
from logger import get_logger
from scripts.core import controle
from scripts.core.notificacao import notificar_teams
from scripts.core.utils import PipelineEmExecucaoError, identificar_pasta, lock_execucao
from scripts.etapas.baixar_recuperacao import baixar_arquivo, listar_arquivos_remotos
from scripts.etapas.extrair_recuperacao import extrair_pasta
from scripts.etapas.restaurar_banco import restaurar_banco

log = get_logger("agendado")


def escolher_arquivos_novos(remotos: dict, agora: datetime) -> dict:
    """Para cada pasta, o arquivo remoto mais recente se ele for diferente do último restaurado."""
    mais_recente_por_pasta = {}
    for arquivo, (tamanho, mtime) in remotos.items():
        pasta = identificar_pasta(arquivo, Config.MAPEAMENTO_NOMES)
        if pasta and (pasta not in mais_recente_por_pasta or mtime > mais_recente_por_pasta[pasta][2]):
            mais_recente_por_pasta[pasta] = (arquivo, tamanho, mtime)

    novos = {}
    limite = agora - timedelta(minutes=Config.MINUTOS_ESTABILIZACAO)
    for pasta in Config.PASTAS_ALVO:
        if pasta not in mais_recente_por_pasta:
            log.info(f"[{pasta}] Nenhum arquivo no servidor.")
            continue

        arquivo, tamanho, mtime = mais_recente_por_pasta[pasta]
        if controle.ler_estado(pasta) == (tamanho, mtime):
            log.info(f"[{pasta}] {arquivo} já processado. Nada a fazer.")
        elif mtime > limite:
            log.info(f"[{pasta}] {arquivo} modificado há menos de {Config.MINUTOS_ESTABILIZACAO} min; fica para a próxima verificação.")
        else:
            novos[pasta] = (arquivo, tamanho, mtime)
    return novos


def processar_pasta(pasta: str, arquivo: str) -> tuple[bool, str]:
    log.info(f"[{pasta}] Arquivo novo detectado: {arquivo}")

    if not baixar_arquivo(arquivo):
        return False, "falha no download"
    if not extrair_pasta(pasta):
        return False, "falha na extração"
    if not restaurar_banco(pasta):
        return False, "falha na restauração"
    return True, "baixado, extraído e restaurado"


def executar() -> bool:
    Config.validar()
    controle.garantir_banco_controle()

    novos = escolher_arquivos_novos(listar_arquivos_remotos(), datetime.now(timezone.utc))
    if not novos:
        log.info("Nenhuma base nova para atualizar.")
        return True

    tudo_ok = True
    resumo = []
    for pasta, (arquivo, tamanho, mtime) in novos.items():
        inicio = datetime.now(timezone.utc)
        try:
            ok, mensagem = processar_pasta(pasta, arquivo)
        except Exception as erro:
            ok, mensagem = False, f"erro inesperado: {erro}"
            log.error(f"[{pasta}] {mensagem}")

        controle.registrar_execucao(pasta, arquivo, tamanho, mtime, inicio, ok, mensagem)
        log.info(f"[{pasta}] {'CONCLUÍDO' if ok else 'FALHOU'}: {mensagem}")
        resumo.append(f"{'✅' if ok else '❌'} {pasta} ({arquivo}): {mensagem}")
        tudo_ok = tudo_ok and ok

    notificar_teams(
        "Restauração: bases atualizadas" if tudo_ok else "Restauração: atualização com falha",
        resumo,
    )
    return tudo_ok


if __name__ == "__main__":
    try:
        with lock_execucao(Config.LOCK_FILE_PATH, Config.LOCK_TIMEOUT_SEGUNDOS):
            try:
                sucesso = executar()
            except Exception as erro:
                log.error(f"[ERRO CRÍTICO] A verificação foi interrompida: {erro}")
                sucesso = False
    except PipelineEmExecucaoError as erro:
        log.error(str(erro))
        sucesso = False

    sys.exit(0 if sucesso else 1)
