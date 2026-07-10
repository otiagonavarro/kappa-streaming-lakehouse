<!-- markdownlint-disable -->
<div align="center">
  <img src="./assets/logo.svg" alt="navarro" width="400" />
    <h1>Kappa Streaming Lakehouse</h1>
    <h2>Data Lake em Tempo Real com Flink, Iceberg, Nessie & PostgreSQL</h2>

  🇺🇸 [English](./README.md) | 🇧🇷 **Português**
</div>

Implementação de referência de nível produção da **arquitetura Kappa** aplicada a analytics de clickstream de e-commerce.
Diferente da Lambda, não há camada batch separada — todo processamento passa por um único pipeline de streaming, e o reprocessamento histórico é feito reproduzindo eventos do Kafka.

---

## Arquitetura

```mermaid
flowchart LR
    SIM["🐍 Event Simulator\n(Python + Faker)"]
    KAFKA["📨 Kafka\n(Redpanda)"]
    FLINK["⚡ Apache Flink\n(PyFlink 1.18)"]
    NESSIE["🗂 Nessie Catalog\n(REST)"]
    ICEBERG["🧊 Iceberg Tables\n(GCS / MinIO)"]
    PG["🐘 PostgreSQL\n(Serving layer)"]
    BI["📊 Analytics\n(DuckDB / psql)"]

    SIM -->|"page_view\nadd_to_cart\npurchase"| KAFKA
    KAFKA -->|raw-events| FLINK
    FLINK -->|"raw_event_ingestion\n(exactly-once)"| ICEBERG
    FLINK -->|"session_aggregation\n(upsert)"| PG
    FLINK -->|"product_funnel\n(1-min windows)"| PG
    NESSIE -.->|"catalog metadata"| ICEBERG
    ICEBERG -->|"time-travel\nDuckDB queries"| BI
    PG -->|"low-latency\nanalytical queries"| BI
```

**Por que Kappa?** Lambda exige duas bases de código (batch + streaming) que precisam produzir resultados idênticos — o clássico problema de manutenção dupla. Kappa mantém um único pipeline; reprocessar a partir do offset 0 do Kafka substitui a camada batch. Veja [docs/trade-offs.md](docs/trade-offs.md) para a análise completa.

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
psql postgresql://kappa:kappa@localhost:5432/kappa -f queries/top_converting_products.sql
```

Abra a Flink Web UI em **<http://localhost:8081>** para ver os jobs e DAGs em execução.
Abra o console do MinIO em **<http://localhost:9001>** (minioadmin / minioadmin) para navegar pelos arquivos de dados do Iceberg.

---

## Modelo de Dados

### Tópico Kafka: `raw-events`

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

### Tabelas Iceberg (catálogo Nessie → namespace `kappa`)

| Tabela | Particionado por | Propósito |
|-------|---------------|---------|
| `kappa.raw_events` | `event_date` (diário) | Arquivo imutável de eventos, time-travel |
| `kappa.session_metrics` | `session_date` (diário) | Agregados por sessão |

### Tabelas de Serving PostgreSQL

| Tabela | Chave | Atualizado por |
|-------|-----|-----------|
| `session_metrics` | `session_id` (upsert) | `session_aggregation.py` |
| `product_funnel_1m` | `(product_id, window_start)` | `product_funnel.py` |

---

## Data Contracts

O job `raw_event_ingestion` é orientado por um contrato YAML no formato [ODCS](https://bitol-io.github.io/open-data-contract-standard/) (Open Data Contract Standard) em [`flink-jobs/contracts/raw_events.contract.yaml`](flink-jobs/contracts/raw_events.contract.yaml), em vez de DDL SQL hardcoded.

O contrato é o ponto único de contato entre o tópico Kafka `raw-events` e a tabela Iceberg `kappa.raw_events` — ele declara:

- **`servers`** — a fonte Kafka (tópico, formato, opções do conector) e o destino Iceberg (catálogo, database, propriedades da tabela)
- **`schema`** — nomes de colunas, tipos, nullability e a chave de partição
- **`customProperties`** — config a nível de job (modo de checkpointing, intervalo de checkpoint)

`flink-jobs/src/common.py` carrega o contrato em runtime (`load_contract`) e monta o DDL da fonte Kafka e do sink Iceberg a partir dele (`kafka_source_ddl_from_contract`, `iceberg_sink_ddl_from_contract`) — mudar o tópico, o schema da tabela ou as propriedades de storage exige só editar o YAML, não o código do job.

---

## Trade-offs

> Análise completa: [docs/trade-offs.md](docs/trade-offs.md)

| Aspecto | Escolha | Motivo |
|---------|--------|-----|
| Arquitetura | Kappa | Pipeline único; reprocessamento via replay do Kafka |
| Formato de tabela | Iceberg | Melhor conector Flink, agnóstico de engine, nativo GCS |
| Catálogo | Nessie | Branching estilo Git, API REST de nível produção |
| Engine de streaming | PyFlink | Python nativo, DataStream + Table API completos |
| Camada de serving | PostgreSQL | Latência sub-10ms para queries de dashboard |
| Dev local | MinIO | Proxy GCS sem custo, `STORAGE_BACKEND=gcs` para trocar |

---

## Reprocessamento

A propriedade central do Kappa: descartar todo estado derivado e re-derivá-lo a partir do log do Kafka.

```bash
make reprocess
```

Isso irá:

1. Cancelar todos os jobs Flink em execução
2. Truncar `session_metrics` e `product_funnel_1m` no PostgreSQL
3. Truncar as tabelas Iceberg
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
| Project Nessie | 0.76.6 |
| Redpanda (compatível Kafka) | 23.3.6 |
| PostgreSQL | 15.6 |
| Python | 3.11 |
| MinIO | RELEASE.2024-03-15 |
| Flyway | 10.10.0 |

---

## Estrutura do Projeto

```
kappa-streaming-lakehouse/
├── flink-jobs/
│   ├── contracts/           # Data contracts ODCS (YAML)
│   │   └── raw_events.contract.yaml
│   └── src/                 # Jobs de streaming PyFlink
│       ├── common.py        # Config de ambiente compartilhada + setup de catálogo + loader de contrato
│       ├── raw_event_ingestion.py
│       ├── session_aggregation.py
│       └── product_funnel.py
├── simulator/              # Simulador de eventos em Python
│   └── src/simulator/
│       ├── events.py       # Geradores de eventos (page_view, add_to_cart, purchase)
│       └── main.py         # CLI com Click
├── db/migrations/          # Migrações SQL Flyway
├── infra/                  # Docker Compose + job submitter
│   ├── docker-compose.yml
│   └── job-submitter/
├── queries/                # Exemplos de SQL analítico
├── scripts/                # Scripts de demo + operações
└── docs/                   # Documentação de arquitetura
```
