import json
import urllib.request

from config import Config
from logger import get_logger

log = get_logger("notificacao")


def notificar_teams(titulo: str, linhas: list[str]) -> bool:
    """Posta um cartão no Teams pelo webhook do Workflows. Nunca levanta exceção:
    falha na notificação não pode derrubar (nem mascarar o resultado de) o pipeline."""
    if not Config.TEAMS_WEBHOOK_URL:
        log.info("teams_webhook_url não configurada no .env; notificação ignorada.")
        return False

    cartao = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {"type": "TextBlock", "text": titulo, "weight": "Bolder", "size": "Medium", "wrap": True},
                    {"type": "TextBlock", "text": "\n\n".join(linhas), "wrap": True},
                ],
            },
        }],
    }
    requisicao = urllib.request.Request(
        Config.TEAMS_WEBHOOK_URL,
        data=json.dumps(cartao).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=30) as resposta:
            log.info(f"Notificação enviada ao Teams (HTTP {resposta.status}).")
        return True
    except Exception as erro:
        log.warning(f"Não foi possível enviar a notificação ao Teams: {erro}")
        return False
