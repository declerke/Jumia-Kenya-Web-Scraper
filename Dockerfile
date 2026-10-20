FROM apache/airflow:slim-3.3.2-python3.12

USER airflow

# Keep the Python packaging tools current in both Airflow and the dbt venv.
RUN python -m pip install --no-cache-dir --upgrade \
    pip==26.2.1 \
    setuptools==83.0.0 \
    uv==0.13.2

# Install Airflow's standard operators against the constraints shipped with this
# Airflow release. Pin Airflow on every subsequent pip install so it cannot drift.
RUN pip install --no-cache-dir --constraint "${HOME}/constraints.txt" \
    apache-airflow==3.3.2 \
    apache-airflow-providers-standard==1.19.0

# Install the scraper and test dependencies in the Airflow runtime environment.
RUN pip install --no-cache-dir \
    apache-airflow==3.3.2 \
    requests==2.33.0 \
    beautifulsoup4==4.12.3 \
    psycopg2-binary==2.9.9 \
    urllib3==2.8.0 \
    PyJWT==2.15.0 \
    pandas==2.1.4 \
    pytest==9.0.3

# Keep dbt's adapter dependency graph separate from Airflow's constrained runtime.
RUN python -m venv /opt/airflow/dbt-venv \
    && /opt/airflow/dbt-venv/bin/python -m pip install --no-cache-dir --upgrade \
        pip==26.2.1 \
        setuptools==83.0.0 \
    && /opt/airflow/dbt-venv/bin/python -m pip install --no-cache-dir \
        dbt-core==1.11.16 \
        dbt-postgres==1.11.0 \
        sqlparse==0.6.0
