<!-- markdownlint-disable -->
<div align="center">
  <img src="./assets/logo.svg" alt="navarro" width="200" />
    <h1>Kappa Streaming Lakehouse</h1>
    <h2>Data Lake em Tempo Real com Flink, Iceberg, Nessie, Doris & Cube.js</h2>

  🇺🇸 [English](./README.md) | 🇧🇷 **Português**
</div>

## O Problema

Plataformas de e-commerce geram um volume massivo de eventos de clickstream a cada segundo — page views, adições ao carrinho, compras. Times de produto e marketing precisam de respostas em tempo real: quais produtos convertem, como os usuários navegam pelos funis, quais sessões estão ativas.

Arquiteturas de dados tradicionais impõem um trade-off:

- **Batch-first (data warehouse)** — Resultados são precisos mas defasados. Dashboards ficam horas atrás da realidade e decisões são tomadas com dados de ontem.
- **Arquitetura Lambda** — Roda um caminho rápido de streaming junto com um caminho lento de batch. Duas bases de código precisam produzir resultados idênticos, criando o clássico problema de manutenção dupla: quando divergem, qual está correta?

Nenhuma das opções oferece simultaneamente frescor em tempo real e corretude sem dobrar a complexidade.

## A Solução

Uma **arquitetura Kappa** onde um único pipeline de streaming processa tanto dados em tempo real quanto reprocessamento histórico. Cada evento passa por um único caminho, chegando a um **lakehouse medallion (bronze/silver/gold)** com uma camada semântica federada por cima:

> **Kafka → Flink → Iceberg (bronze/silver/gold) + PostgreSQL (serving) → Doris + Cube.js (federação/BI)**

Não há camada batch. Quando você precisa recomputar o histórico, reproduz o log do Kafka desde o início — o mesmo código, o mesmo pipeline, apenas a partir do offset 0.

## Por Que Esta Arquitetura Funciona

| Problema | Como Kappa + Lakehouse resolve |
|---------|--------------------------------|
| Divergência de código batch/streaming | Uma base de código — se funciona nos dados ao vivo, funciona nos dados reproduzidos |
| Latência de dashboard (horas → segundos) | Flink processa evento a evento; resultados chegam ao PostgreSQL em tempo sub-segundo |
| Reprocessamento sem camada batch | Kafka é a fonte imutável de verdade — replay desde o offset 0 substitui o batch |
| Data lake sem ACID / time travel | Iceberg traz transações ACID, evolução de schema e time travel para object storage |
| Leituras de dashboard lentas no data lake | Upserts no PostgreSQL entregam queries sub-10ms para dashboards |
| Mudanças de schema quebram consumidores | Nessie oferece branching estilo Git para evolução de schema segura no catálogo |
| "Qual sistema tem esse dado?" | Doris federa Iceberg + PostgreSQL; Cube.js expõe uma única API semântica sobre ambos |

---

## Diagramas

Diagramas mais profundos — componentes, boundaries, o runbook de bootstrap/reprocessamento, uma sequência de query federada, a linhagem medallion e a máquina de estados de sessão — vivem como HTML autocontido e sensível a tema em [`diagrams/`](diagrams/) (toggle claro/escuro, exportação PNG/SVG embutida). Capturas em PNG:

### Arquitetura

<img src="diagrams/architecture.png" alt="Diagrama de arquitetura do Kappa Streaming Lakehouse: componentes, storage e boundaries" width="100%">

Componentes, storage e boundaries de segurança/região de toda a stack, do simulador de eventos até Doris + Cube.js. [Versão interativa](diagrams/architecture.html).

### Workflow

<img src="diagrams/workflow.png" alt="Diagrama de workflow do bootstrap da stack e do runbook de reprocessamento" width="100%">

A sequência de bootstrap do `make up` (Compose → Flyway → Flink → submissão de jobs, com a federação Doris/Cube.js subindo em paralelo) e o caminho de exceção do `make reprocess`. [Versão interativa](diagrams/workflow.html).

### Sequência

<img src="diagrams/sequence.png" alt="Diagrama de sequência de query federada do Cube.js com fallback de cache miss no Doris" width="100%">

Uma query do Cube.js em um cache miss de pré-agregação, caindo para uma leitura federada do Doris entre os catálogos Iceberg e PostgreSQL na mesma sessão. [Versão interativa](diagrams/sequence.html).

### Data Flow

<img src="diagrams/dataflow.png" alt="Diagrama de data flow e linhagem bronze, silver e gold" width="100%">

Linhagem bronze → silver → gold, boundaries de sensibilidade do `user_id`, e consumidores downstream. [Versão interativa](diagrams/dataflow.html).

### Lifecycle

<img src="diagrams/lifecycle.png" alt="Diagrama de máquina de estados do ciclo de vida da sessão do usuário" width="100%">

A máquina de estados da sessão — ingestão de evento, validação, o gap watch de 30 minutos, e os desfechos terminais. [Versão interativa](diagrams/lifecycle.html).

---

## Início Rápido

**Requisitos:** Docker ≥ 24, Docker Compose ≥ 2.20, 8 GB RAM, 4 CPUs

```bash
git clone https://github.com/otiagonavarro/kappa-streaming-lakehouse kappa-streaming-lakehouse
cd kappa-streaming-lakehouse

# 1. Sobe a stack completa (MinIO por padrão, sem precisar de credenciais GCS)
make up

# 2. Aguarde ~2 minutos até todos os serviços ficarem saudáveis
make check

# 3. Consulte a camada de serving
psql postgresql://kappa:kappa@localhost:5432/kappa -f examples/queries/top_converting_products.sql
```

Abra a Flink Web UI em **<http://localhost:8081>** para ver os jobs e DAGs em execução.  
Abra o console do MinIO em **<http://localhost:9001>** (minioadmin / minioadmin) para navegar pelos arquivos de dados do Iceberg.  
Abra o Cube.js Playground em **<http://localhost:4000>** para explorar a camada semântica e rodar queries de exemplo.  
Consulte o Doris diretamente com `mysql -h127.0.0.1 -P9030 -uroot`. Dois catálogos já vêm registrados: `lakehouse` (tabelas Iceberg via Nessie, ex. `lakehouse.gold.session_metrics`) e `postgres` (a camada de serving federada via JDBC, ex. `postgres.public.session_metrics`, `postgres.public.users`) — ambos consultáveis na mesma sessão, incluindo joins entre eles.

---

## Modelo de Dados

### Tópicos Kafka

**`raw-events`** — eventos de clickstream, consumidos por três jobs (`raw_event_ingestion`, `silver_enrichment`, `product_funnel`):

```json
{
  "event_id":   "uuid-v4",
  "event_type": "page_view | add_to_cart | purchase",
  "user_id":    "U1234",
  "session_id": "uuid-v4",
  "product_id": "P123",
  "timestamp":  "2024-03-15T10:22:31.456789+00:00",
  "metadata":   { "page": "/products/P123", "referrer": "https://..." }
}
```

**`entity-updates`** — um único tópico de CDC com schema largo carregando usuários, produtos, categorias e pedidos ([ADR-0010](adr/0010-wide-schema-cdc-topic.md)). `entity_sync.py` e `order_ingestion.py` o consomem para tabelas de dimensão/fato tanto no Iceberg quanto no PostgreSQL, mas — veja [Lacunas Conhecidas](#lacunas-conhecidas) — nenhum dos dois jobs está conectado à execução padrão do `job-submitter` ainda.

### Tabelas Iceberg (arquitetura medallion, catálogo Nessie)

| Camada | Tabela | Particionado por | Contrato |
|-------|-------|-----------------|----------|
| Bronze | `bronze.raw_events` | `event_date` | [contracts/bronze/raw_events.yaml](contracts/bronze/raw_events.yaml) |
| Silver | `silver.validated_events` | `event_date` | [contracts/silver/validated_events.yaml](contracts/silver/validated_events.yaml) |
| Silver | `silver.user_sessions` | `session_date` | [contracts/silver/user_sessions.yaml](contracts/silver/user_sessions.yaml) |
| Gold | `gold.session_metrics` | `session_date` | [contracts/gold/session_metrics.yaml](contracts/gold/session_metrics.yaml) |
| Gold | `gold.product_funnel_1m` | — | [contracts/gold/product_funnel_1m.yaml](contracts/gold/product_funnel_1m.yaml) |
| Gold | `gold.user_360` | — | [contracts/gold/user_360.yaml](contracts/gold/user_360.yaml) |

### Tabelas de Serving PostgreSQL

| Tabela | Chave | Atualizado por | Migração |
|-------|-----|-----------|-----------|
| `session_metrics` | `session_id` (upsert) | `session_aggregation.py` | `V1__create_session_metrics.sql` |
| `product_funnel_1m` | `(product_id, window_start)` | `product_funnel.py` | `V2__create_product_funnel_1m.sql` |
| `categories`, `users`, `products`, `orders`, `order_items` | PKs de entidade/pedido | `entity_sync.py`, `order_ingestion.py` (não conectados — veja [Lacunas Conhecidas](#lacunas-conhecidas)) | `V3__create_ecommerce_entities.sql` |

---

## Data Contracts

Dois formatos de contrato de dados coexistem hoje (reconciliá-los está rastreado na [RFC-0010](rfcs/RFC-0010-roadmap.md)):

1. **Contratos medallion** ([Data Contract Specification](https://datacontract.com/) 1.1.0) em [`contracts/{bronze,silver,gold}/`](contracts) — um YAML por tabela, declarando schema, tipos, regras de qualidade (`notNull`, `uniqueness`, `enumeration`, `freshness`), particionamento e SLAs. `services/flink-jobs/src/contracts/loader.py` carrega esses contratos em runtime (`ddl_columns`, `partition_spec`), e cada job medallion monta seu DDL de `CREATE TABLE` a partir do contrato em vez de hardcoded.
2. **Contrato ODCS legado** ([Open Data Contract Standard](https://bitol-io.github.io/open-data-contract-standard/)) em [`services/flink-jobs/contracts/raw_events.contract.yaml`](services/flink-jobs/contracts/raw_events.contract.yaml) — o formato original de contrato, anterior aos contratos medallion e hoje na prática substituído por `contracts/bronze/raw_events.yaml`.

De qualquer forma, mudar o schema, os tipos ou a chave de partição de uma tabela exige só editar o YAML correspondente — não o código do job.

---

## Trade-offs

> Análise completa: [docs/tradeoffs.md](docs/tradeoffs.md)

| Aspecto | Escolha | Motivo |
|---------|--------|-----|
| Arquitetura | Kappa | Pipeline único; reprocessamento via replay do Kafka |
| Formato de tabela | Iceberg | Melhor conector Flink, agnóstico de engine, nativo GCS |
| Catálogo | Nessie | Branching estilo Git, API REST de nível produção |
| Engine de streaming | PyFlink | Python nativo, DataStream + Table API completos |
| Camada de serving | PostgreSQL | Latência sub-10ms para queries de dashboard |
| Dev local | MinIO | Proxy GCS sem custo, `STORAGE_BACKEND=gcs` para trocar |
| Data contracts | Bronze/Silver/Gold + YAML por camada | Boundary explícito de validação/enriquecimento; DDL não pode divergir do contrato |
| Tópico de CDC | `entity-updates` único, schema largo | Um único caminho de consumo para cinco tipos de entidade, ao custo de tipagem mais fraca por entidade |
| Camada semântica / BI | Federação Doris + Cube.js | Uma API sobre Iceberg + PostgreSQL, definições de métricas consistentes |

---

## Reprocessamento

A propriedade central do Kappa: descartar todo estado derivado e re-derivá-lo a partir do log do Kafka.

```bash
make reprocess
```

Isso irá:

1. Cancelar todos os jobs Flink em execução
2. Truncar as tabelas de serving do PostgreSQL (`session_metrics`, `product_funnel_1m`, `users`, `products`, `categories`, `orders`, `order_items`)
3. Derrubar as tabelas Iceberg nas camadas bronze → silver → gold
4. Reiniciar todos os jobs com `--from-beginning` (consumer group do Kafka resetado para offset 0)

Após o reprocessamento, a contagem de linhas será idêntica à execução original.

---

## Modo Cloud GCS

1. Crie um bucket GCS e uma service account com `roles/storage.admin`
2. Baixe a chave JSON da SA para `./secrets/gcp-sa.json`
3. Edite `.env`:

   ```
   STORAGE_BACKEND=gcs
   GCS_BUCKET=my-kappa-lake
   GCS_PROJECT_ID=my-project
   ```

4. Rode `make up` — o Flink escreverá os arquivos Iceberg diretamente no GCS

---

## Matriz de Versões

| Componente | Versão |
|-----------|---------|
| Apache Flink (PyFlink) | 1.18.1 |
| Apache Iceberg | 1.5.2 (flink-runtime-1.18) |
| Project Nessie | 0.108.2 |
| Apache Doris | 4.1.3 |
| Cube.js | latest |
| Redpanda (compatível Kafka) | 23.3.6 |
| PostgreSQL | 15.6 |
| Python | 3.11 |
| MinIO | RELEASE.2024-03-15 |
| Flyway | 10.10.0 |

---

## Documentação

| Onde | O quê |
|-------|------|
| [`rfcs/`](rfcs) | RFC-0000..RFC-0010 — framing do problema, arquitetura, modelo de domínio/dados, API, segurança, observabilidade, escalabilidade, recuperação de falhas, roadmap |
| [`adr/`](adr) | ADR-0001..ADR-0011 — decisões arquiteturais individuais (Kappa vs. Lambda, Iceberg vs. Delta/Hudi, Flink vs. Spark, Nessie, DDL orientado a contrato, contratos medallion, tópico de CDC de schema largo, federação Doris + Cube.js) |
| [`docs/tradeoffs.md`](docs/tradeoffs.md) | Resumo cross-cutting de trade-offs, com link de volta para cada ADR |
| [`docs/runbook.md`](docs/runbook.md), [`docs/playbook.md`](docs/playbook.md), [`docs/troubleshooting.md`](docs/troubleshooting.md), [`docs/faq.md`](docs/faq.md) | Documentação operacional |
| [`docs/flink-jobs.md`](docs/flink-jobs.md) | Referência de DAG por job do pipeline PyFlink |
| [`docs/compliance-gap-report.md`](docs/compliance-gap-report.md) | Avaliação pontual do retrofit estrutural |

### Lacunas Conhecidas

Rastreadas por completo em [`rfcs/RFC-0010-roadmap.md`](rfcs/RFC-0010-roadmap.md). As mais relevantes antes de rodar isso localmente:

- **`entity_sync.py` e `order_ingestion.py` não estão conectados ao `job-submitter`** — as tabelas de dimensão/fato que eles populam (`users`, `products`, `categories`, `orders`, `order_items` tanto no Iceberg quanto no Postgres) existem em forma de schema/contrato, mas ficam vazias até que esses dois jobs sejam adicionados à lista `JOBS` de `infra/job-submitter/submit_jobs.py`.
- `scripts/time-travel-demo.sh` atualmente falha — ele chama dois scripts auxiliares que ainda não existem.
- Sem dead-letter queue: o `silver_enrichment` descarta eventos malformados em vez de roteá-los para inspeção.
- `STORAGE_BACKEND=gcs` está implementado mas nunca foi executado contra um GCS real.

---

## Estrutura do Projeto

```
kappa-streaming-lakehouse/
├── .github/workflows/        # CI (lint + testes)
├── rfcs/                     # RFC-0000..RFC-0010, o registro de design
├── adr/                      # Registros de decisão arquitetural (0001-0011)
├── diagrams/                 # Diagramas de arquitetura/workflow/sequência/dataflow/lifecycle (JSON + HTML + PNG)
├── docs/                     # Trade-offs, runbook, playbook, troubleshooting, FAQ, referência dos jobs Flink
├── contracts/                # Contratos de dados medallion (Data Contract Specification 1.1.0)
│   ├── bronze/                  # raw_events.yaml
│   ├── silver/                  # validated_events.yaml, user_sessions.yaml
│   └── gold/                    # session_metrics.yaml, product_funnel_1m.yaml, user_360.yaml
├── examples/
│   └── queries/               # Exemplos de SQL analítico
├── services/
│   ├── flink-jobs/
│   │   ├── contracts/           # Contrato ODCS legado (raw_events.contract.yaml)
│   │   └── src/                 # Jobs de streaming PyFlink
│   │       ├── common.py          # Config de ambiente compartilhada + setup de catálogo
│   │       ├── contracts/loader.py  # Carrega contracts/{bronze,silver,gold}/*.yaml
│   │       ├── raw_event_ingestion.py  # Kafka → bronze.raw_events
│   │       ├── silver_enrichment.py    # bronze → silver.validated_events
│   │       ├── session_aggregation.py  # silver.user_sessions + gold.session_metrics
│   │       ├── product_funnel.py       # Kafka → gold.product_funnel_1m
│   │       ├── user_360.py             # gold.session_metrics → gold.user_360
│   │       ├── entity_sync.py          # entity-updates → dimensões (não conectado)
│   │       └── order_ingestion.py      # entity-updates → fatos (não conectado)
│   ├── simulator/              # Simulador de eventos em Python
│   │   └── src/simulator/
│   │       ├── events.py         # Geradores de eventos (page_view, add_to_cart, purchase)
│   │       ├── entities.py       # Geradores de entidade/CDC
│   │       └── main.py           # CLI com Click
│   ├── cube/model/cubes/       # Modelos da camada semântica Cube.js
│   └── db/migrations/          # Migrações SQL Flyway (V1-V3)
├── infra/
│   ├── compose/
│   │   └── docker-compose.yml
│   ├── job-submitter/          # Submete os 5 jobs PyFlink conectados
│   ├── terraform/               # (vazio — sem IaC ainda)
│   └── docker/                  # (vazio — sem Dockerfiles avulsos ainda)
├── tests/
│   └── simulator/               # Testes unitários do simulador
├── scripts/                     # Scripts de demo + operações
└── LICENSE
```
