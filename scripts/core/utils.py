import contextlib
import os
import threading
import time


class PipelineEmExecucaoError(Exception):
    """Levantada quando já existe uma execução do pipeline em andamento."""


@contextlib.contextmanager
def lock_execucao(caminho_lock: str, timeout_segundos: int, intervalo_renovacao: float = 60):
    """Impede que duas execuções do pipeline rodem ao mesmo tempo.

    Usa a idade do arquivo de lock (em vez de checar o PID) porque
    verificar se um processo está vivo por PID no Windows via os.kill
    pode acabar matando um processo com PID reaproveitado.

    Enquanto a execução vive, uma thread renova o mtime do lock; assim uma execução
    longa (downloads de horas) nunca é confundida com um lock velho de crash.
    """
    if os.path.exists(caminho_lock):
        idade = time.time() - os.path.getmtime(caminho_lock)
        if idade < timeout_segundos:
            raise PipelineEmExecucaoError(
                f"Já existe uma execução em andamento (lock criado há {idade:.0f}s "
                f"em '{caminho_lock}'). Se tiver certeza de que não há outra execução "
                f"rodando, apague o arquivo de lock manualmente."
            )
        os.remove(caminho_lock)  # lock velho demais, provavelmente sobra de um crash

    with open(caminho_lock, "w") as f:
        f.write(str(os.getpid()))

    parar = threading.Event()

    def renovar():
        while not parar.wait(intervalo_renovacao):
            try:
                os.utime(caminho_lock)
            except OSError:
                pass

    threading.Thread(target=renovar, daemon=True).start()

    try:
        yield
    finally:
        parar.set()
        try:
            os.remove(caminho_lock)
        except FileNotFoundError:
            pass


def formatar_mb(tamanho_bytes: float) -> str:
    return f"{tamanho_bytes / (1024 * 1024):.1f} MB"


def formatar_velocidade(bytes_baixados: float, segundos: float) -> str:
    if segundos <= 0:
        return "0.0 MB/s"
    velocidade = bytes_baixados / segundos / (1024 * 1024)
    return f"{velocidade:.1f} MB/s"


def identificar_pasta(nome_arquivo: str, mapeamento: dict) -> str | None:
    for palavra_chave, nome_pasta in mapeamento.items():
        if palavra_chave in nome_arquivo:
            return nome_pasta
    return None


def garantir_pasta(caminho: str) -> str:
    os.makedirs(caminho, exist_ok=True)
    return caminho


def encontrar_arquivo_por_extensao(pasta: str, extensao: str) -> str | None:
    if not os.path.exists(pasta):
        return None

    for arquivo in os.listdir(pasta):
        if arquivo.endswith(extensao):
            return os.path.join(pasta, arquivo)
    return None

