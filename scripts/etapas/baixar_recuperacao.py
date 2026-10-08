import os
import socket
import time
import concurrent.futures
from datetime import datetime, timezone

import paramiko

from config import Config
from logger import get_logger
from scripts.core.ssh_client import abrir_conexao
from scripts.core.utils import (
    formatar_mb,
    formatar_velocidade,
    identificar_pasta,
    garantir_pasta,
)

log = get_logger("download")


def baixar_arquivo(arquivo: str) -> bool:
    pasta_alvo = identificar_pasta(arquivo, Config.MAPEAMENTO_NOMES)
    if not pasta_alvo:
        log.warning(f"Nenhuma pasta mapeada para {arquivo}, ignorando.")
        return False

    caminho_subpasta = garantir_pasta(os.path.join(Config.LOCAL_DIR, pasta_alvo))
    remote_file = f"{Config.REMOTE_DIR.rstrip('/')}/{arquivo}"
    local_file = os.path.join(caminho_subpasta, arquivo)

    tentativa = 0
    while tentativa < Config.MAX_TENTATIVAS:
        tentativa += 1
        ssh = None
        sftp = None
        try:
            ssh = abrir_conexao()
            sftp = ssh.open_sftp()

            try:
                tamanho_remoto = sftp.stat(remote_file).st_size
            except FileNotFoundError:
                log.error(f"[{pasta_alvo}] Arquivo remoto não existe (mais): {remote_file}")
                return False

            tamanho_local = os.path.getsize(local_file) if os.path.exists(local_file) else 0

            if tamanho_local >= tamanho_remoto:
                log.info(f"[{pasta_alvo}] JÁ COMPLETO: {arquivo}")
                return True

            if tamanho_local > 0:
                log.info(
                    f"[{pasta_alvo}] Retomando {arquivo} a partir de {formatar_mb(tamanho_local)} "
                    f"(tentativa {tentativa}/{Config.MAX_TENTATIVAS})"
                )
                modo_local = "ab"
            else:
                log.info(f"[{pasta_alvo}] Iniciando download de: {arquivo} ({formatar_mb(tamanho_remoto)})")
                modo_local = "wb"

            proximo_log = tamanho_local + Config.LOG_PROGRESSO_A_CADA
            inicio = time.time()

            with sftp.open(remote_file, "rb") as arquivo_remoto:
                arquivo_remoto.seek(tamanho_local)
                with open(local_file, modo_local) as arquivo_local:
                    baixado = tamanho_local
                    while True:
                        pedaco = arquivo_remoto.read(Config.TAMANHO_BLOCO)
                        if not pedaco:
                            break
                        arquivo_local.write(pedaco)
                        baixado += len(pedaco)

                        if baixado >= proximo_log:
                            decorrido = time.time() - inicio
                            velocidade = formatar_velocidade(baixado - tamanho_local, decorrido)
                            log.info(
                                f"[{pasta_alvo}] {arquivo}: {formatar_mb(baixado)} / "
                                f"{formatar_mb(tamanho_remoto)} ({velocidade})"
                            )
                            proximo_log += Config.LOG_PROGRESSO_A_CADA

            log.info(f"[{pasta_alvo}] CONCLUÍDO: {arquivo}")
            return True

        except (paramiko.SSHException, socket.timeout, socket.error, EOFError, OSError) as erro:
            espera = Config.ESPERA_ENTRE_TENTATIVAS * tentativa
            log.warning(
                f"[{pasta_alvo}] Falha em {arquivo} (tentativa {tentativa}/{Config.MAX_TENTATIVAS}): "
                f"{erro}. Tentando retomar em {espera}s..."
            )
            time.sleep(espera)

        except Exception as erro:
            log.error(f"[{pasta_alvo}] Erro definitivo ao baixar {arquivo}: {erro}")
            return False

        finally:
            try:
                if sftp:
                    sftp.close()
            finally:
                if ssh:
                    ssh.close()

    log.error(f"[{pasta_alvo}] DESISTI de {arquivo} após {Config.MAX_TENTATIVAS} tentativas.")
    return False


def listar_arquivos_remotos() -> dict[str, tuple[int, datetime]]:
    """Retorna {arquivo: (tamanho, data de modificação em UTC)} dos '_PROD.zip' do servidor."""
    ssh = abrir_conexao()
    try:
        sftp = ssh.open_sftp()
        try:
            return {
                attr.filename: (attr.st_size, datetime.fromtimestamp(attr.st_mtime, timezone.utc))
                for attr in sftp.listdir_attr(Config.REMOTE_DIR)
                if attr.filename.endswith("_PROD.zip")
            }
        finally:
            sftp.close()
    finally:
        ssh.close()


def iniciar_downloads():
    garantir_pasta(Config.LOCAL_DIR)

    log.info("Conectando ao servidor para ler a lista de arquivos...")

    try:
        ssh_lista = abrir_conexao()
        sftp_lista = ssh_lista.open_sftp()
        arquivos_brutos = sftp_lista.listdir(Config.REMOTE_DIR)

        tamanhos = {}
        for arq in arquivos_brutos:
            if arq.endswith("_PROD.zip"):
                caminho = f"{Config.REMOTE_DIR.rstrip('/')}/{arq}"
                try:
                    tamanhos[arq] = sftp_lista.stat(caminho).st_size
                except Exception:
                    tamanhos[arq] = 0

        sftp_lista.close()
        ssh_lista.close()
    except Exception as erro:
        log.error(f"Erro ao tentar ler a pasta no servidor: {erro}")
        raise  # deixa o main.py saber que a etapa falhou

    arquivos_validos = sorted(tamanhos.keys(), key=lambda a: tamanhos[a], reverse=True)

    if not arquivos_validos:
        log.warning("Nenhum arquivo '_PROD.zip' encontrado.")
        return

    log.info(f"Encontrados {len(arquivos_validos)} arquivos válidos (ordenados do maior pro menor).")
    for a in arquivos_validos:
        log.info(f"  - {a}: {formatar_mb(tamanhos[a])}")
    log.info("Disparando os downloads simultâneos...")

    with concurrent.futures.ThreadPoolExecutor(Config.MAX_TRABALHOS_PARALELOS) as executor:
        resultados = list(executor.map(baixar_arquivo, arquivos_validos))

    if not all(resultados):
        falharam = [a for a, ok in zip(arquivos_validos, resultados) if not ok]
        raise RuntimeError(f"O download falhou para: {falharam}")

    log.info("Todos os processos paralelos foram finalizados!")


if __name__ == "__main__":
    iniciar_downloads()