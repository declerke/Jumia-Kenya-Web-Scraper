# Jumia Kenya Web Scraper

Production-grade e-commerce price intelligence pipeline that scrapes 6 Jumia Kenya categories daily, transforms raw data through dbt, and serves interactive dashboards via Apache Superset — all orchestrated by Apache Airflow 3.0 in Docker.

---

## Architecture

```
 ┌─────────────────────────────────────────────────────────────────┐
 │                    Apache Airflow 3.0 (DAG: jumia_price_pipeline)│
 └───────────────────────────┬─────────────────────────────────────┘
                             │ orchestrates
          ┌──────────────────┼──────────────────────┐
          ▼                  ▼                       ▼
  ┌───────────────┐  ┌──────────────┐      ┌──────────────────┐
  │ Jumia.co.ke   │  │  dbt-postgres│      │  Apache Superset  │
  │ (6 categories)│  │  4 models    │      │  Dashboards       │
  └──────┬────────┘  └──────┬───────┘      └────────┬─────────┘
         │ requests+BS4     │ transforms             │ reads
         ▼                  ▼                        ▼
  ┌──────────────────────────────────────────────────────────────┐
  │               PostgreSQL 15  —  jumia_db                     │
  │  raw.product_prices  →  staging  →  marts                   │
  └──────────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Scraping library | requests + BeautifulSoup4 | Jumia Kenya is server-side rendered — no JavaScript execution needed. Saves ~40% memory vs. Playwright and eliminates browser management complexity |
| Database | PostgreSQL 15 | Superset native connector, concurrent write safety with Airflow's LocalExecutor, UPSERT support via ON CONFLICT clause |
| Orchestration | Apache Airflow 3.0 | DAG-based dependency management, retry logic, scheduling — industry-standard for data pipelines |
| Transformation | dbt-postgres | Declarative SQL, lineage tracking, schema tests, and easy model layer separation (staging → marts) |
| Rate limiting | 2–4s random sleep | Avoids triggering anti-scraping defenses while keeping scrape time under 10 minutes for 6 categories × 3 pages |
| UPSERT strategy | ON CONFLICT (product_url, scrape_date) | Idempotent daily runs — re-triggering the DAG updates prices without creating duplicate rows |

---

## Tech Stack

| Component | Technology | Role |
|---|---|---|
| Web Scraping | Python requests + BeautifulSoup4 | Fetch and parse Jumia Kenya HTML pages |
| Orchestration | Apache Airflow 3.0 | DAG scheduling, task dependency, retry logic |
| Raw Storage | PostgreSQL 15 | Persist scraped product price rows |
| Transformation | dbt-postgres 1.8 | Staging views, fact tables, mart aggregations |
| Dashboards | Apache Superset | Interactive price and discount analysis |
| Containerisation | Docker + Docker Compose | Reproducible environment for all services |
| Testing | pytest | Unit tests for parsing logic |
| Security | pip-audit (GitHub Actions) | Weekly CVE scan of Python dependencies |

---

## Data Schema

### Raw table — `raw.product_prices`

| Column | Type | Description |
|---|---|---|
| product_id | SERIAL PK | Auto-incremented row identifier |
| product_name | VARCHAR(500) | Full product display name |
| current_price_kes | NUMERIC(12,2) | Current listed price in KES |
| old_price_kes | NUMERIC(12,2) | Pre-discount price (NULL if no deal) |
| discount_pct | NUMERIC(5,2) | Discount badge percentage |
| category | VARCHAR(100) | Jumia category label |
| product_url | TEXT | Absolute product page URL |
| scraped_at | TIMESTAMPTZ | Timestamp of the scrape write |
| page_num | INT | Pagination page the product was found on |
| scrape_date | DATE | Calendar date of the run (UPSERT key) |

---

## Pipeline Flow

1. **Airflow triggers** `jumia_price_pipeline` DAG on schedule (`@daily`) or manually
2. **`scrape_all_categories`** — Python task spawns a `requests.Session` per category; scrapes 3 pages x 6 categories with 2–4 s rate-limiting between pages; UPSERTs all records into `raw.product_prices`
3. **`run_dbt_models`** — BashOperator runs `dbt run`; builds `stg_jumia_products` (view), then `fct_product_prices`, `mart_category_summary`, `mart_discount_leaders` (tables)
4. **`run_dbt_tests`** — BashOperator runs `dbt test`; validates not_null, unique, accepted_values constraints across all models
5. **`log_summary`** — Python task queries `raw.product_prices`, logs per-category product counts and grand total

---

## dbt Models

| Model | Layer | Description | Tests |
|---|---|---|---|
| `stg_jumia_products` | Staging | Type casting, price cleaning (0.0 to NULL), brand extraction from product name | not_null, unique, accepted_values |
| `fct_product_prices` | Marts | Full fact table with has_discount flag, price_delta_kes, days_since_scraped | not_null, unique |
| `mart_category_summary` | Marts | Per-category per-day: avg/min/max price, avg discount, pct_discounted | not_null |
| `mart_discount_leaders` | Marts | Top 20 products by discount per category, most recent scrape only | not_null |

---

## Test Coverage

| Type | Count | Scope |
|---|---|---|
| pytest unit tests | 22 | Price parsing, discount parsing, URL building, HTML product card parsing, edge cases |
| dbt schema tests | 16 | not_null x 8, unique x 4, accepted_values x 2, not_null on mart columns x 2 |
| **Total** | **38** | |

---

## Setup & Running

### Prerequisites
- Docker Desktop (with WSL2 backend on Windows)
- Python 3.11+ (for local development only)
- uv (`pip install uv`)

### 1. Clone the repository
```bash
git clone https://github.com/declerke/Jumia-Kenya-Web-Scraper.git
cd Jumia-Kenya-Web-Scraper
```

### 2. Local development environment (optional)
```bash
uv venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

uv pip install -r requirements.txt
```

### 3. Build Docker images
```bash
docker-compose build
```

### 4. Start all services
```bash
docker-compose up -d
```

### 5. Wait for initialisation (~60 seconds)
```bash
docker-compose logs -f airflow-webserver
```

### 6. Trigger the pipeline
```bash
docker-compose exec airflow-webserver airflow dags trigger jumia_price_pipeline
```

### 7. Monitor DAG run
```bash
docker-compose exec airflow-webserver airflow dags list-runs -d jumia_price_pipeline
```

Or visit **http://localhost:8080** with credentials admin / admin123

### 8. Verify data
```bash
docker-compose exec postgres psql -U postgres -d jumia_db \
  -c "SELECT category, COUNT(*) FROM raw.product_prices GROUP BY category ORDER BY COUNT(*) DESC;"
```

### 9. Run tests
```bash
docker-compose exec airflow-webserver bash -c "cd /opt/airflow && python -m pytest tests/ -v"
```

### 10. Open Superset dashboards
Visit **http://localhost:8088** with credentials admin / admin123

Add a PostgreSQL database connection:
- Host: `postgres` (internal Docker network name)
- Port: `5432`
- Database: `jumia_db`
- Username: `postgres`
- Password: `postgres`

### 11. Tear down
```bash
docker-compose down -v
```

---

## Sample Output

| product_name | category | current_price_kes | old_price_kes | discount_pct | scrape_date |
|---|---|---|---|---|---|
| Samsung Galaxy A55 5G 8GB/256GB | Smartphones | 47,999 | 59,999 | 20% | 2025-06-03 |
| HP 250 G10 Laptop Core i5 16GB | Computing | 68,500 | 85,000 | 19% | 2025-06-03 |
| Hisense 43" 4K UHD Smart TV | TVs & Audio | 32,999 | 44,999 | 27% | 2025-06-03 |
| Ramtons Front Load Washing Machine | Home Appliances | 44,500 | 55,000 | 19% | 2025-06-03 |
| Omo Washing Powder 2kg | Supermarket | 349 | — | — | 2025-06-03 |

---

## Skills Demonstrated

- **Web scraping** — requests + BeautifulSoup4, pagination handling, CSS selector parsing, rate limiting
- **Apache Airflow 3.0** — DAG authoring, PythonOperator, BashOperator, task dependencies, XCom
- **dbt-postgres** — staging/marts layer architecture, schema tests, model materialisation strategies
- **PostgreSQL** — schema design, UPSERT (ON CONFLICT), window functions, aggregations
- **Apache Superset** — dashboard setup, PostgreSQL connection, chart types for e-commerce analytics
- **Docker and Docker Compose** — multi-service orchestration, health checks, custom Airflow Dockerfile
- **Python testing** — pytest, HTML fixture-based unit tests, edge case coverage
- **GitHub Actions** — CI security scanning with pip-audit, scheduled weekly runs
- **Data engineering patterns** — idempotent pipelines, raw → staging → marts layer separation

---

## Project Stats

| Metric | Value |
|---|---|
| Categories scraped | 5 active (6 configured) |
| Pages per category | 3 |
| Total products in raw table | 794 rows |
| dbt models passing | 4 / 4 |
| dbt tests passing | 15 / 15 |
| pytest passing | 34 / 34 |
| DAG task runtime | ~70s scrape + ~10s dbt |
| Superset accessible | Yes — http://localhost:8088 |

---

## License

MIT License — free to use, modify, and distribute.
