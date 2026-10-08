# Postgres Backup Restore Pipeline

Pipeline em Python que **baixa backups via SFTP, extrai e restaura no PostgreSQL**, pensado para
arquivos grandes (dezenas de GB) e conexões instáveis. Roda em três etapas, cada uma com
paralelismo interno, e tem um modo agendado que só reprocessa a base cujo backup mudou.

```mermaid
flowchart LR
    A[Servidor remoto<br/>*_PROD.zip] -- 1. SFTP com retomada<br/>3 em paralelo --> B[local_dir/BASE/*.zip]
    B -- 2. extrai o .sql<br/>e apaga o .zip --> C[local_dir/BASE/*.sql]
    C -- 3. pg_restore -c --if-exists --> D[(PostgreSQL<br/>RESTORE_BASE)]
    D -. modo agendado .-> E[(banco de controle<br/>estado + histórico)]
    E -. resumo .-> F[Teams]
```

## Destaques técnicos

- **Download resiliente**: leitura em blocos com `seek`, retomando de onde parou após queda de conexão
  (até 6 tentativas, espera crescente), log de progresso e velocidade.
- **Paralelismo** com `ThreadPoolExecutor` (3 arquivos/bancos por vez), maiores arquivos primeiro.
- **Segurança SSH**: política **TOFU** (*trust on first use*) — a host key é fixada no primeiro contato
  e uma chave diferente depois disso derruba a conexão (possível MITM), em vez de ser aceita em silêncio.
- **Restauração tolerante só ao que é esperado**: falhas de `GRANT`/`OWNER` para roles que não existem no
  servidor de destino viram aviso; qualquer outro erro do `pg_restore` falha a etapa.
- **Higiene entre execuções**: `.sql` residual de uma rodada anterior é apagado antes da extração, para
  nunca restaurar um arquivo velho se a extração atual falhar.
- **Modo agendado** (`agendado.py`): compara tamanho e data de modificação do arquivo remoto com o estado
  gravado num banco de controle no próprio Postgres; espera 30 min de estabilidade antes de pegar um arquivo
  que ainda pode estar sendo enviado. Estado e histórico são gravados na mesma transação.
- **Lock com heartbeat**: impede duas execuções simultâneas e destrava sozinho se o processo morrer.
- **Fail fast**: `Config.validar()` lista as variáveis obrigatórias faltando; exit code `1` em qualquer
  falha, para o agendador detectar.

## Estrutura

```
postgres-backup-restore-pipeline/
├── .env.example            # modelo das variáveis de ambiente
├── main.py                 # executa as 3 etapas para todas as bases
├── agendado.py             # verificação periódica: processa só as bases com backup novo
├── config.py               # variáveis de ambiente, constantes e validação
├── logger.py               # log no console + arquivo rotativo (logs/pipeline.log)
├── scripts/
│   ├── core/
│   │   ├── ssh_client.py   # conexão SSH/SFTP com fixação de host key (TOFU)
│   │   ├── controle.py     # banco de controle (estado e histórico) no Postgres
│   │   ├── notificacao.py  # Adaptive Card no Teams via webhook
│   │   └── utils.py        # lock de execução, formatação, busca de arquivos
│   └── etapas/
│       ├── baixar_recuperacao.py   # ETAPA 1 - download
│       ├── extrair_recuperacao.py  # ETAPA 2 - extração dos ZIPs
│       └── restaurar_banco.py      # ETAPA 3 - pg_restore
└── tests/                  # pytest com mocks de SFTP e pg_restore
```

## Pré-requisitos

- Python 3.10+
- PostgreSQL com `pg_restore` instalado na máquina que executa o pipeline
- Acesso SSH/SFTP ao servidor dos backups

## Instalação e configuração

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate no Linux/macOS)
pip install -r requirements.txt
cp .env.example .env            # e preencha
```

As bases são definidas em `bases=` no `.env`: cada nome é procurado no nome do arquivo remoto,
vira a subpasta local e o banco `<db_prefixo><BASE>` (ex.: `RESTORE_NORTE`).

## Execução

```bash
python main.py        # as 3 etapas, para todas as bases
python agendado.py    # só as bases com backup novo (para rodar todo dia no agendador)
```

## Testes

```bash
pip install -r requirements-dev.txt
pytest
```

Os testes não precisam de servidor remoto nem de Postgres: SSH/SFTP, `pg_restore` e o banco de
controle são substituídos por mocks.

## Licença

[MIT](LICENSE)
