import logging
import os
from logging.handlers import RotatingFileHandler

os.makedirs("logs", exist_ok=True)

def get_logger(nome: str) -> logging.Logger:
    logger = logging.getLogger(nome)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formato = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    arquivo = RotatingFileHandler(
        "logs/pipeline.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    arquivo.setFormatter(formato)

    console = logging.StreamHandler()
    console.setFormatter(formato)

    logger.addHandler(arquivo)
    logger.addHandler(console)
    return logger