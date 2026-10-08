import os

import paramiko

from config import Config
from logger import get_logger

log = get_logger("ssh")


class PoliticaTofu(paramiko.MissingHostKeyPolicy):
    """Confia e fixa a chave do host apenas no primeiro contato (Trust On First Use).

    Em conexões seguintes, o paramiko compara automaticamente contra a chave
    já salva em known_hosts e derruba a conexão (BadHostKeyException) se ela
    mudou — o que pode indicar um ataque man-in-the-middle.
    """

    def missing_host_key(self, client, hostname, key):
        log.warning(
            f"Host key de '{hostname}' desconhecida. Fixando (TOFU) em "
            f"'{Config.KNOWN_HOSTS_PATH}'. Fingerprint: {key.get_fingerprint().hex()}"
        )
        client.get_host_keys().add(hostname, key.get_name(), key)
        client.save_host_keys(Config.KNOWN_HOSTS_PATH)


def abrir_conexao() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()

    if os.path.exists(Config.KNOWN_HOSTS_PATH):
        ssh.load_host_keys(Config.KNOWN_HOSTS_PATH)

    ssh.set_missing_host_key_policy(PoliticaTofu())
    ssh.connect(
        Config.HOST,
        Config.PORTA,
        Config.USUARIO,
        Config.SENHA,
        timeout=Config.TIMEOUT_CONEXAO,
        banner_timeout=Config.TIMEOUT_CONEXAO,
        auth_timeout=Config.TIMEOUT_CONEXAO,
    )
    transport = ssh.get_transport()
    transport.set_keepalive(30)
    transport.use_compression(False)
    return ssh
