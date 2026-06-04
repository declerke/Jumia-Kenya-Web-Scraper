"""
Airflow DAG: jumia_price_pipeline

Orchestrates the full Jumia Kenya price intelligence pipeline:
  1. scrape_all_categories  — scrape 6 categories, UPSERT to PostgreSQL
  2. run_dbt_models         — transform raw data through staging + marts
  3. run_dbt_tests          — validate all dbt model tests
  4. log_summary            — log per-category product counts
"""

import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default arguments
# ---------------------------------------------------------------------------

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# ---------------------------------------------------------------------------
# Task callables
# ---------------------------------------------------------------------------

def scrape_all_categories_fn(**context):
    """Scrape all Jumia Kenya categories and UPSERT to raw.product_prices."""
    from scraper.jumia_scraper import run_all_scrapers

    results = run_all_scrapers(pages_per_category=3)

    total = sum(results.values())
    logger.info("Scrape complete. Total rows upserted: %d", total)
    logger.info("Per-category counts: %s", results)

    # Push to XCom so downstream tasks can read it
    context["ti"].xcom_push(key="scrape_results", value=results)
    return results


def log_summary_fn(**context):
    """Log per-category scrape counts from the upstream XCom result."""
    results = context["ti"].xcom_pull(task_ids="scrape_all_categories", key="scrape_results") or {}

    logger.info("=== Product counts by category ===")
    total = 0
    for category, count in sorted(results.items(), key=lambda x: x[1], reverse=True):
        logger.info("  %-25s %d products", category, count)
        total += count
    logger.info("  %-25s %d products", "TOTAL", total)

    return results


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

with DAG(
    dag_id="jumia_price_pipeline",
    default_args=default_args,
    description="Scrape Jumia Kenya prices, transform with dbt, validate.",
    schedule="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["jumia", "ecommerce", "kenya", "scraping"],
) as dag:

    scrape_task = PythonOperator(
        task_id="scrape_all_categories",
        python_callable=scrape_all_categories_fn,
    )

    dbt_run_task = BashOperator(
        task_id="run_dbt_models",
        bash_command=(
            "cd /opt/airflow && "
            "dbt run "
            "--project-dir /opt/airflow/dbt "
            "--profiles-dir /opt/airflow/dbt "
            "--no-version-check"
        ),
    )

    dbt_test_task = BashOperator(
        task_id="run_dbt_tests",
        bash_command=(
            "cd /opt/airflow && "
            "dbt test "
            "--project-dir /opt/airflow/dbt "
            "--profiles-dir /opt/airflow/dbt "
            "--no-version-check"
        ),
    )

    log_summary_task = PythonOperator(
        task_id="log_summary",
        python_callable=log_summary_fn,
    )

    # Task dependencies: linear pipeline
    scrape_task >> dbt_run_task >> dbt_test_task >> log_summary_task
