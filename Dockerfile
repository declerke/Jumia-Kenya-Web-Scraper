FROM apache/airflow:3.0.0

USER airflow

# Install Python dependencies as the airflow user.
# Airflow 3.0 uses an internal virtual environment — plain pip install
# targets the correct site-packages path.
RUN pip install --no-cache-dir \
    requests==2.31.0 \
    beautifulsoup4==4.12.3 \
    psycopg2-binary==2.9.9 \
    "dbt-core==1.8.7" \
    "dbt-postgres==1.8.2" \
    pandas==2.2.2 \
    pytest==8.2.0
