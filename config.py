import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    HOST = os.getenv("host")
    PORTA = int(os.getenv("port", 22))
    USUARIO = os.getenv("usuario")
    SENHA = os.getenv("senha")
    TIMEOUT_CONEXAO = 30

    LOCAL_DIR = os.getenv("local_dir", "").strip('"\'')
    REMOTE_DIR = os.getenv("remote_dir")

    DB_HOST = os.getenv("db_host")
    DB_PORT = os.getenv("db_port", "5432")
    DB_USER = os.getenv("db_user")
    DB_PASS = os.getenv("db_pass")
    PG_RESTORE_PATH = os.getenv("pg_restore_path")
    DB_CONTROLE = os.getenv("db_controle", "PIPELINE_CONTROLE")

    TEAMS_WEBHOOK_URL = os.getenv("teams_webhook_url")

    MINUTOS_ESTABILIZACAO = 30

    MAPEAMENTO_NOMES = {
        base.strip(): base.strip()
        for base in os.getenv("bases", "NORTE,SUL,CENTRO").split(",")
        if base.strip()
    }
    DB_PREFIXO = os.getenv("db_prefixo", "RESTORE_")

    PASTAS_ALVO = list(MAPEAMENTO_NOMES.values())

    TAMANHO_BLOCO = 262144
    MAX_TENTATIVAS = 6
    ESPERA_ENTRE_TENTATIVAS = 15
    LOG_PROGRESSO_A_CADA = 200 * 1024 * 1024

    MAX_TRABALHOS_PARALELOS = 3

    KNOWN_HOSTS_PATH = os.path.join(os.path.dirname(__file__), "known_hosts")
    LOCK_FILE_PATH = os.path.join(os.path.dirname(__file__), "pipeline.lock")
    LOCK_TIMEOUT_SEGUNDOS = 60 * 60

    _OBRIGATORIAS = (
        "HOST", "USUARIO", "SENHA",
        "LOCAL_DIR", "REMOTE_DIR",
        "DB_HOST", "DB_USER", "DB_PASS", "PG_RESTORE_PATH",
    )

    @classmethod
    def validar(cls):
        faltando = [nome for nome in cls._OBRIGATORIAS if not getattr(cls, nome)]
        if faltando:
            raise RuntimeError(
                "Variáveis de ambiente obrigatórias ausentes ou vazias no .env: "
                + ", ".join(faltando)
            )