from datetime import datetime, timezone

import psycopg2
from psycopg2 import sql

from config import Config
from logger import get_logger

log = get_logger("controle")

_DDL = """
CREATE TABLE IF NOT EXISTS pipeline_estado (
    pasta          TEXT PRIMARY KEY,
    arquivo        TEXT NOT NULL,
    tamanho_remoto BIGINT NOT NULL,
    mtime_remoto   TIMESTAMPTZ NOT NULL,
    processado_em  TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_execucoes (
    id             BIGSERIAL PRIMARY KEY,
    pasta          TEXT NOT NULL,
    arquivo        TEXT NOT NULL,
    tamanho_remoto BIGINT,
    mtime_remoto   TIMESTAMPTZ,
    inicio         TIMESTAMPTZ NOT NULL,
    fim            TIMESTAMPTZ,
    status         TEXT NOT NULL,
    mensagem       TEXT
);
"""


def _conectar(banco: str):
    return psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASS,
        dbname=banco,
    )


def garantir_banco_controle() -> None:
    """Cria o banco de controle e suas tabelas, se ainda não existirem."""
    conexao = _conectar("postgres")
    conexao.autocommit = True
    try:
        with conexao.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (Config.DB_CONTROLE,))
            if not cur.fetchone():
                log.info(f"Criando banco de controle '{Config.DB_CONTROLE}'...")
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(Config.DB_CONTROLE)))
    finally:
        conexao.close()

    conexao = _conectar(Config.DB_CONTROLE)
    try:
        with conexao, conexao.cursor() as cur:
            cur.execute(_DDL)
    finally:
        conexao.close()


def ler_estado(pasta: str) -> tuple[int, datetime] | None:
    """Retorna (tamanho, mtime) do último arquivo restaurado com sucesso para a pasta."""
    conexao = _conectar(Config.DB_CONTROLE)
    try:
        with conexao, conexao.cursor() as cur:
            cur.execute(
                "SELECT tamanho_remoto, mtime_remoto FROM pipeline_estado WHERE pasta = %s",
                (pasta,),
            )
            linha = cur.fetchone()
            return (linha[0], linha[1]) if linha else None
    finally:
        conexao.close()


def registrar_execucao(
    pasta: str,
    arquivo: str,
    tamanho: int,
    mtime: datetime,
    inicio: datetime,
    sucesso: bool,
    mensagem: str,
) -> None:
    """Grava o log da execução e, se deu certo, atualiza o estado da pasta (mesma transação)."""
    fim = datetime.now(timezone.utc)
    conexao = _conectar(Config.DB_CONTROLE)
    try:
        with conexao, conexao.cursor() as cur:
            cur.execute(
                "INSERT INTO pipeline_execucoes "
                "(pasta, arquivo, tamanho_remoto, mtime_remoto, inicio, fim, status, mensagem) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (pasta, arquivo, tamanho, mtime, inicio, fim, "sucesso" if sucesso else "erro", mensagem),
            )
            if sucesso:
                cur.execute(
                    "INSERT INTO pipeline_estado (pasta, arquivo, tamanho_remoto, mtime_remoto, processado_em) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (pasta) DO UPDATE SET arquivo = EXCLUDED.arquivo, "
                    "tamanho_remoto = EXCLUDED.tamanho_remoto, mtime_remoto = EXCLUDED.mtime_remoto, "
                    "processado_em = EXCLUDED.processado_em",
                    (pasta, arquivo, tamanho, mtime, fim),
                )
    finally:
        conexao.close()
