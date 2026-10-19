FROM apache/airflow:3.0.0

USER airflow

# Install Python dependencies as the airflow user.
# Airflow 3.0 uses an internal virtual environment — plain pip install
# targets the correct site-packages path.
RUN pip install --no-cache-dir \
    requests==2.33.0 \
    beautifulsoup4==4.12.3 \
    psycopg2-binary==2.9.9 \
    pandas==2.2.2 \
    pytest==9.0.3

# Keep dbt's adapter dependency graph separate from Airflow's constrained runtime.
RUN python -m venv /opt/airflow/dbt-venv \
    && /opt/airflow/dbt-venv/bin/python -m pip install --no-cache-dir \
        dbt-core==1.11.16 \
        dbt-postgres==1.11.0
