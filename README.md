# 🛒 Jumia Kenya Web Scraper: E-Commerce Price Intelligence Pipeline

**Jumia Kenya Web Scraper** is a production-grade e-commerce price intelligence pipeline that scrapes product listings across 5 active Jumia Kenya categories daily, transforms raw scraped data through a 3-layer dbt model architecture (staging → fact → marts), and surfaces interactive price and discount analytics via a 5-chart Apache Superset dashboard — all orchestrated by Apache Airflow 3.0 running in Docker. The pipeline captures 766 unique product records per daily run using a shared HTTP session with respectful rate limiting, batch-upserts all rows into PostgreSQL in a single network round-trip, and validates data integrity with 15 dbt schema tests and 34 pytest unit tests before the summary task reads its results directly from Airflow XCom with zero additional DB queries.

| Metric | Value |
|--------|-------|
| Products scraped | 766 (5 active categories × 3 pages) |
| Airflow tasks | 4 (scrape → dbt run → dbt test → log summary) |
| dbt models | 4 (1 staging · 1 fact · 2 marts) |
| dbt tests | 15 (all passing) |
| pytest tests | 34 (all passing) |
| Dashboard charts | 5 (Superset) |
| Pipeline runtime | 125s end-to-end |
| Cost to run | $0 — open web data + local stack only |

---

## 🎯 Project Goal

E-commerce pricing on Jumia Kenya shifts daily. Promotions appear and disappear, discount percentages change between page refreshes, and category-level trends are invisible unless data is captured and aggregated systematically over time. A data engineer or analyst supporting a retailer, price comparison service, or market research firm needs a reliable automated system that scrapes, stores, and transforms this data into analytical tables they can query — not a one-off script that produces a CSV.

This pipeline demonstrates the full production data engineering stack applied to Kenya's largest e-commerce platform: automated daily ingestion with idempotent UPSERT logic that survives re-triggers without creating duplicate rows, a dbt transformation layer that cleans price strings, extracts brand names from unstructured product titles, computes discount flags, and pre-aggregates the metrics that analysts actually query, and a Superset dashboard that lets a business user answer questions like "which category offers the deepest discounts today?" and "what is the price range for Smartphones vs TVs?" without writing SQL.

---

## 🧬 System Architecture

1. **Scraping — requests + BeautifulSoup4** — `scraper/jumia_scraper.py` opens a single `requests.Session` shared across all 6 configured categories; for each category it fetches 3 paginated pages (URLs: `/{category}/` for page 1, `/{category}/?page=N` for pages 2–3), parses each HTML response with BeautifulSoup4 using CSS selectors (`article.prd`, `h3.name`, `div.prc`, `div.old`, `div.bdg._dsct`, `a.core`), applies a 2–4 second random sleep between pages to respect Jumia's server load, and returns a list of product dicts per category. The session is shared — not created per category — so all 18 page fetches (6 categories × 3 pages) reuse the same TCP connection pool and avoid repeated TLS handshakes.

2. **Raw storage — PostgreSQL 15** — All scraped product records land in `raw.product_prices` via a single `psycopg2.extras.execute_values` call per category — one INSERT statement for all rows rather than one per row. The UPSERT conflict target is `(product_url, scrape_date)`, which makes every daily run idempotent: re-triggering the DAG on the same calendar date updates prices rather than creating duplicates. Products that appear on multiple Jumia pages with the same URL are deduplicated in Python before the batch INSERT to avoid the `CardinalityViolation` error that PostgreSQL raises when a multi-row INSERT targets the same conflict key twice in the same statement.

3. **dbt transformation — staging → fact → marts** — Four dbt models run in dependency order via `dbt run`: `stg_jumia_products` (view) casts numeric columns, replaces zero-value `old_price_kes` with NULL, and extracts brand names from unstructured product titles using a 55-brand lookup list covering all major consumer electronics, home appliance, and FMCG brands sold in Kenya; `fct_product_prices` (table) adds `has_discount` boolean flag, `price_delta_kes` (savings in KES when old price is available), and `days_since_scraped` for data freshness tracking; `mart_category_summary` (table) aggregates avg/min/max price, average discount percentage, discounted product count, and percentage of discounted products per category per scrape date; `mart_discount_leaders` (table) identifies the top 20 most-discounted products per category from the most recent scrape using a window function — the Superset "Top Discount Leaders Today" chart reads from this mart directly.

4. **Superset dashboards** — A 5-chart dashboard titled "Jumia Kenya Price Intelligence" connects to `jumia_db` via PostgreSQL and queries the `raw`, `public_marts`, and `public_staging` schemas directly. Charts cover product coverage by category, average listed price, average discount percentage (pie), share of discounted products, and a ranked table of the top discount deals. The dashboard reflects the most recent daily scrape at any given time.

5. **Airflow 3.0 orchestration** — The `jumia_price_pipeline` DAG runs on a `@daily` schedule with `catchup=False`. Four tasks run in a strict linear dependency chain: `scrape_all_categories` (PythonOperator, ~55s) → `run_dbt_models` (BashOperator, ~7s) → `run_dbt_tests` (BashOperator, ~7s) → `log_summary` (PythonOperator, <1s). The summary task pushes its per-category row counts to XCom in the scrape task, then the log task pulls them from XCom — no additional database connection is opened in the final task. The Docker stack runs Airflow 3.0's required multi-process layout: api-server, scheduler, and dag-processor as separate services.

---

## 🛠️ Technical Stack

| **Layer** | **Tool** | **Version** |
|---|---|---|
| Orchestration | Apache Airflow (LocalExecutor) | 3.0 |
| Web scraping | Python requests + BeautifulSoup4 | 2.33.0 / 4.12.3 |
| Raw storage | PostgreSQL | 15 |
| Transformation | dbt-postgres | 1.8.2 |
| Dashboards | Apache Superset | latest |
| Containerisation | Docker Compose (7 services) | — |
| Testing | pytest | 9.0.3 |
| Security scanning | pip-audit (GitHub Actions) | weekly |
| Language | Python | 3.11 / 3.12 |

---

## 📊 Performance & Results

- **766 unique product records** ingested per daily run across 5 active categories: Computing (185), TVs & Audio (171), Men's Fashion (146), Smartphones (144), Home Appliances (120)
- **Supermarket category** returns 0 products — Jumia applies bot-detection on their grocery pages; the scraper handles this gracefully with a zero-count result rather than failing
- **Full 4-task pipeline** completes in **125 seconds** end-to-end: scrape 54.6s + dbt run 7.25s + dbt test 7.38s + log summary 0.19s
- **Discount coverage is extremely high**: Smartphones 97.9% discounted, Men's Fashion ~100%, TVs & Audio ~99%, Computing ~91%, Home Appliances ~90% — Jumia displays most products with a "was / now" price structure
- **Average discount depth by category**: Computing leads at 47.3% average discount; Men's Fashion and TVs & Audio follow at approximately 47% and 37% respectively
- **Batch UPSERT efficiency**: all rows per category sent in a single `execute_values` INSERT rather than N individual round-trips; deduplication on `product_url` within each batch prevents `CardinalityViolation` when Jumia lists the same product on multiple pages
- **dbt test suite** (15 tests) passes in under 10 seconds; `not_null` + `unique` on all primary keys, `accepted_values` on the 5 valid category strings, `not_null` on all mart aggregation columns

---

## 📸 Dashboard

### Jumia Kenya Price Intelligence — Full Dashboard

![](<assets/jumia kenya price intelligence.png>)

*Five-chart Superset dashboard reading live from the `jumia_db` PostgreSQL database. Left column shows Share of Discounted Products (bar), Average Listed Price KES (bar), and Product Coverage by Category (bar). Right side shows Average Discount by Category (pie) and the Top Discount Leaders Today ranked table. All charts update on each daily DAG run.*

### Product Coverage by Category

![](<assets/product coverage by category.png>)

*Bar chart showing unique product count per category from `mart_category_summary`. Computing leads with 185 products; Home Appliances is smallest at 120. Supermarket shows 0 — Jumia's grocery section triggers anti-bot detection at the scraping layer.*

### Average Discount by Category (Pie)

![](<assets/average discount by category.png>)

*Pie chart of average discount percentage from `mart_category_summary.avg_discount_pct`. Computing carries the deepest average discount at 47.34% (23.9% of the pie), reflecting Jumia's aggressive electronics promotions. All five categories show average discounts between 30–47%.*

### Average Listed Price (KES)

![](<assets/average listed price.png>)

*Bar chart of `AVG(avg_price_kes)` per category. Home Appliances shows an outlier-inflated average driven by industrial-grade equipment in the category mix. Men's Fashion averages 1.29M KES — Jumia Kenya's fashion section includes luxury and imported brand items priced in USD equivalents.*

### Share of Discounted Products (%)

![](<assets/share of discounted products.png>)

*Bar chart of `pct_discounted` from `mart_category_summary` — the percentage of products in each category carrying an active discount badge. Smartphones lead at 97.9%; all five categories exceed 90%, confirming that Jumia's "was / now" pricing model applies to virtually every listing.*

### Top Discount Leaders Today

![](<assets/top discount leaders today.png>)

*Table reading from `mart_discount_leaders` — the top 20 discounted products per category, ranked by `discount_pct DESC`, filtered to the most recent `scrape_date`. Men's Fashion dominates the deepest discount positions; Computing (mice, monitors, accessories) and Smartphones also feature prominently.*

### Airflow DAG — 4/4 Success

![Airflow DAG run](assets/airflow_dag_success.png)

*All 4 tasks completing successfully: `scrape_all_categories` (PythonOperator, 54.6s) → `run_dbt_models` (BashOperator, 7.25s) → `run_dbt_tests` (BashOperator, 7.38s) → `log_summary` (PythonOperator, 0.19s). Total run 124.97s.*

---

## 📦 Categories Scraped

| Category | URL | Products (2026-06-04) | Avg Discount |
|---|---|---|---|
| Computing | `/computing/` | 185 | 47.3% |
| TVs & Audio | `/televisions/` | 171 | 36.6% |
| Men's Fashion | `/men-clothing/` | 146 | 46.8% |
| Smartphones | `/smartphones/` | 144 | 30.9% |
| Home Appliances | `/home-appliances/` | 120 | 36.4% |
| Supermarket | `/supermarket/` | 0 | — (bot-protected) |

---

## 🧠 Key Design Decisions

- **Single `requests.Session` shared across all 6 categories** — the original implementation created a new `requests.Session()` at the top of `scrape_category()`, meaning each category call discarded the previous session's connection pool and performed a fresh DNS lookup and TLS handshake against `www.jumia.co.ke`. Moving the session to `run_all_scrapers()` as a context manager (`with requests.Session() as session:`) and passing it into `scrape_category()` as an optional parameter means all 18 page fetches (6 categories × 3 pages) share one persistent connection — the server's keep-alive response to the first request is honoured for all subsequent ones. The parameter is optional (`session: Optional[requests.Session] = None`) so `scrape_category()` can still be called standalone in tests without a session argument.

- **`execute_values` batch UPSERT instead of `executemany`** — psycopg2's `executemany` is a Python-level loop: it sends one INSERT statement per row, meaning 185 products from Computing generate 185 network packets to the database. `psycopg2.extras.execute_values` batches all rows into a single multi-value INSERT with `VALUES %s` substitution, cutting round-trips from N to 1 per category. For 766 products across 5 categories, this reduces total INSERT round-trips from 766 to 5. The batch size is capped at `page_size=500` to avoid exceeding PostgreSQL's query size limits. Because `execute_values` sends all rows in one statement, a prerequisite is that the batch contains no duplicate conflict keys — Jumia occasionally lists the same product URL on multiple pagination pages, which would cause a `CardinalityViolation`. A Python deduplication pass (`{p["product_url"]: p for p in products}`) removes duplicates before building the values list.

- **Inline UNIQUE constraint in `CREATE TABLE IF NOT EXISTS`** — the original `ensure_schema()` used a `DO $$ BEGIN IF NOT EXISTS ... ALTER TABLE ADD CONSTRAINT ... END IF; END $$;` anonymous PL/pgSQL block to add the `(product_url, scrape_date)` uniqueness constraint after the table was created. This 12-line block exists only because `ALTER TABLE ... ADD CONSTRAINT IF NOT EXISTS` is not valid PostgreSQL syntax. The cleaner alternative is to declare `CONSTRAINT uq_product_url_scrape_date UNIQUE (product_url, scrape_date)` inline in the `CREATE TABLE IF NOT EXISTS` definition — on first run, the table is created with the constraint in place; on subsequent runs, the entire `CREATE TABLE IF NOT EXISTS` is a no-op. No PL/pgSQL block needed.

- **XCom for `log_summary` instead of a second DB query** — the original `log_summary_fn` task opened its own `psycopg2` connection, ran `SELECT category, COUNT(*) FROM raw.product_prices GROUP BY category`, fetched the rows, and iterated them twice (once to log, once to build the return dict). The scrape task already computed per-category row counts as a natural output of `upsert_products()` and pushed them to XCom. The summary task can pull the same dict with `context["ti"].xcom_pull(task_ids="scrape_all_categories", key="scrape_results")` — no connection opened, no SQL executed, single-pass iteration for both logging and return value. The `log_summary` task now completes in 0.19 seconds.

- **requests + BeautifulSoup4 over Playwright** — Jumia Kenya's product listing pages are server-side rendered: the HTML returned by a standard GET request contains the complete product card markup. No JavaScript execution is needed to see product names, prices, or discount badges. Playwright would add ~200–400 MB of browser binary, require a browser launch per session, and add 3–8 seconds of startup overhead per category with no benefit on this target. requests + BeautifulSoup4 scrapes a full 3-page category in under 15 seconds including rate-limiting sleep; the same Playwright approach would take 30–50 seconds per category.

- **Brand extraction in `stg_jumia_products` rather than application code** — Jumia product names are unstructured strings like "Samsung Galaxy A55 5G 8GB/256GB Dual SIM Blue". Extracting the brand ("Samsung") is a transformation concern, not a scraping concern — the raw table should store what Jumia actually returns, and the staging model applies business logic. The extraction uses a 55-brand lookup list covering Kenyan consumer electronics (Samsung, Tecno, Infinix, Itel), home appliances (Ramtons, Bruhm, Nasco, Von), and FMCG brands (Unilever, Nestlé, Colgate, Dettol). Placing this logic in dbt means the brand list can be updated without touching scraper code, and the lookup is auditable via `dbt docs generate`.

- **`mart_discount_leaders` scoped to `MAX(scrape_date)` only** — the mart filters to `scrape_date = (SELECT MAX(scrape_date) FROM fct_product_prices)` before running the `ROW_NUMBER() OVER (PARTITION BY category ORDER BY discount_pct DESC)` ranking. Without this filter, a product that had a 90% discount last week but only a 20% discount today would still appear as a "top deal" in the mart because its historical row has the highest discount. Restricting to the latest scrape date ensures the discount leaderboard reflects today's Jumia prices, not historical ones.

---

## 📂 Project Structure

```text
Jumia-Kenya-Web-Scraper/
├── dags/
│   └── jumia_pipeline.py               # Airflow DAG — 4 tasks, @daily, XCom summary
├── scraper/
│   ├── jumia_scraper.py                # Core scraper — shared session, execute_values batch upsert, dedup
│   ├── utils.py                        # parse_price, parse_discount, build_full_url
│   └── __init__.py
├── dbt/
│   ├── models/
│   │   ├── staging/
│   │   │   └── stg_jumia_products.sql  # Type cast, zero→NULL old_price, 55-brand extraction
│   │   ├── marts/
│   │   │   ├── fct_product_prices.sql  # has_discount flag, price_delta_kes, days_since_scraped
│   │   │   ├── mart_category_summary.sql  # avg/min/max price, avg discount, pct_discounted per day
│   │   │   └── mart_discount_leaders.sql  # Top 20 by discount per category, MAX(scrape_date) scoped
│   │   └── schema.yml                  # Source declarations + 15 dbt tests
│   ├── dbt_project.yml
│   └── profiles.yml                    # PostgreSQL connection from POSTGRES_* env vars
├── tests/
│   ├── test_scraper.py                 # 10 tests: HTML card parsing, price filtering, URL building
│   └── test_utils.py                   # 24 tests: KSh parsing, discount parsing, URL normalisation
├── assets/                             # Dashboard screenshots (7 images)
├── Dockerfile                          # Airflow 3.0 image with requests, bs4, dbt-postgres, psycopg2
├── docker-compose.yml                  # 7 services: 2× postgres, init, api-server, scheduler,
│                                       #   dag-processor, superset
├── passwords.json                      # Airflow 3.0 SimpleAuthManager credentials
├── requirements.txt                    # Local dev deps — uv venv .venv && uv pip install -r
├── .env.example                        # POSTGRES_HOST/PORT/DB/USER/PASSWORD
└── .gitignore                          # .env, __pycache__, dbt/target/, .venv/
```

---

## ⚙️ Installation & Setup

### Prerequisites

- Docker Desktop (WSL2 backend on Windows)
- Git

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/declerke/Jumia-Kenya-Web-Scraper.git
   cd Jumia-Kenya-Web-Scraper
   ```

2. **Build and start all services**
   ```bash
   docker compose up -d --build
   ```
   First build installs requests, BeautifulSoup4, dbt-postgres, and psycopg2 into the Airflow image (~2 minutes).

3. **Wait for initialisation** (~60 seconds)
   ```bash
   docker compose logs -f airflow-webserver
   # Wait until the healthcheck passes
   ```

4. **Trigger the pipeline**
   ```bash
   docker compose exec airflow-webserver airflow dags trigger jumia_price_pipeline
   ```

5. **Monitor the run**
   ```bash
   docker compose exec airflow-webserver airflow dags list-runs -d jumia_price_pipeline
   ```

6. **Access services**

   | Service | URL | Credentials |
   |---------|-----|-------------|
   | Airflow | http://localhost:8080 | admin / admin |
   | Superset | http://localhost:8088 | admin / admin123 |
   | PostgreSQL (app) | localhost:5435 | postgres / postgres / jumia_db |
   | PostgreSQL (Airflow) | localhost:5436 | airflow / airflow / airflow |

7. **Add Superset database connection** (first run only)

   In Superset → Settings → Database Connections → + Database:
   - Database type: PostgreSQL
   - SQLAlchemy URI: `postgresql://postgres:postgres@postgres:5432/jumia_db`

8. **Run tests locally** (optional)
   ```bash
   uv venv .venv && uv pip install -r requirements.txt
   python -m pytest tests/ -v
   ```

9. **Verify data**
   ```bash
   docker compose exec postgres psql -U postgres -d jumia_db \
     -c "SELECT category, COUNT(*) FROM raw.product_prices GROUP BY category ORDER BY COUNT(*) DESC;"
   ```

10. **Tear down**
    ```bash
    docker compose down -v
    ```

---

## 🗄️ dbt Models

| Model | Layer | Type | Description |
|-------|-------|------|-------------|
| `stg_jumia_products` | Staging | View | Casts `current_price_kes` and `old_price_kes` to `NUMERIC(12,2)`; replaces `old_price_kes = 0` with NULL; extracts `brand` from the first token of `product_name` using a 55-brand Kenya-market lookup list; filters out rows where `current_price_kes IS NULL` |
| `fct_product_prices` | Mart | Table | Core fact table — one row per product per `scrape_date`; adds `has_discount` boolean (`discount_pct > 0`), `price_delta_kes` (savings amount when old price exceeds current price), and `days_since_scraped` for data freshness monitoring |
| `mart_category_summary` | Mart | Table | Aggregates `avg_price_kes`, `min_price_kes`, `max_price_kes`, `avg_discount_pct` (among discounted products only), `discounted_count`, and `pct_discounted` per category per scrape date; powers the four category-level Superset bar and pie charts |
| `mart_discount_leaders` | Mart | Table | Top 20 products by `discount_pct DESC` per category, restricted to `MAX(scrape_date)` via a subquery to ensure the leaderboard reflects today's prices only; ranked using `ROW_NUMBER() OVER (PARTITION BY category ORDER BY discount_pct DESC, price_delta_kes DESC)`; powers the Top Discount Leaders Today table in Superset |

**15 dbt tests — 15/15 PASS:**
- Staging: `not_null` + `unique` on `product_id`; `not_null` on `current_price_kes`; `not_null` + `accepted_values` on `category` (5 values: Smartphones, Computing, TVs & Audio, Home Appliances, Men's Fashion)
- Fact: `not_null` + `unique` on `product_id`; `not_null` on `current_price_kes`, `category`, `scrape_date`
- `mart_category_summary`: `not_null` on `category`, `scrape_date`, `product_count`
- `mart_discount_leaders`: `not_null` on `category`, `discount_pct`

---

## 🎓 Skills Demonstrated

- **Web scraping at scale** — requests + BeautifulSoup4 with CSS selector parsing (`article.prd`, `h3.name`, `div.prc`, `div.bdg._dsct`); shared HTTP session across all category fetches; random rate-limiting sleep (2–4s) to avoid triggering anti-bot detection; robust price string parsing handling `KSh`, `KES`, `ksh` prefix variants, comma thousand-separators, and decimal prices

- **Apache Airflow 3.0 DAG design** — 4-task linear pipeline with `PythonOperator` and `BashOperator`; `@daily` schedule with `catchup=False`; XCom push/pull to eliminate redundant DB queries between tasks; Airflow 3.0 multi-process architecture (api-server, scheduler, dag-processor as separate services); SimpleAuthManager for zero-config authentication

- **PostgreSQL engineering** — idempotent UPSERT using `ON CONFLICT (product_url, scrape_date) DO UPDATE SET`; batch insert with `psycopg2.extras.execute_values` reducing N round-trips to 1 per category; Python-level deduplication before batch insert to prevent `CardinalityViolation`; inline `CONSTRAINT ... UNIQUE` in `CREATE TABLE IF NOT EXISTS` for clean idempotent schema management

- **dbt-postgres transformation** — 3-layer model architecture (staging → fact → mart); source declarations with `schema: raw`; computed columns (`has_discount`, `price_delta_kes`, `days_since_scraped`); window function in `mart_discount_leaders` (`ROW_NUMBER() OVER (PARTITION BY category ORDER BY discount_pct DESC)`); `MAX(scrape_date)` subquery filter to scope leaderboard to the latest run; 15 schema tests including `accepted_values` on all 5 Jumia category strings

- **Apache Superset** — PostgreSQL database connection via SQLAlchemy URI; 5 chart types (bar, pie, table) built from dbt mart tables; full dashboard layout with cross-chart filtering; SQL Lab for ad-hoc analysis across all schemas

- **Python testing** — 34 pytest unit tests with static HTML fixture builders (`make_product_card`, `make_page_html`) for isolated parsing logic tests; parametric edge cases covering NULL prices, zero discounts, absolute vs relative URLs, KSh/KES/ksh prefix variants, whitespace, and empty strings; no live HTTP calls in any test

- **Docker Compose multi-service orchestration** — 7-service stack with two independent PostgreSQL instances (app data and Airflow metadata on different host ports); custom Airflow Dockerfile installing project deps as `USER airflow` per Airflow 3 container conventions; `service_healthy` dependency conditions using `pg_isready` health checks; named volumes for data persistence across restarts

- **GitHub Actions CI security scanning** — `pip-audit --local` pattern (install-first, then audit installed packages) to handle complex dependency trees that pip-audit's internal resolver cannot solve; `--ignore-vuln GHSA-w75w-9qv4-j5xj` with inline comment documenting the unfixable dbt-common CVE (requires dbt-core 1.34+ upgrade which breaks adapter compatibility); weekly scheduled scan on Mondays
