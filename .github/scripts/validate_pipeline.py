"""Check the Jumia Airflow DAG imports and invokes the isolated dbt CLI."""

from dags.jumia_pipeline import dag


assert dag.dag_id == "jumia_price_pipeline"
assert {task.task_id for task in dag.tasks} == {
    "scrape_all_categories",
    "run_dbt_models",
    "run_dbt_tests",
    "log_summary",
}
assert all(
    "/opt/airflow/dbt-venv/bin/dbt" in dag.get_task(task_id).bash_command
    for task_id in ("run_dbt_models", "run_dbt_tests")
)

print("DAG import and dbt executable check passed")
