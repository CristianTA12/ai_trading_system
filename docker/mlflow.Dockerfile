FROM ghcr.io/mlflow/mlflow:v2.19.0

# The upstream image does not include the PostgreSQL driver.
RUN pip install --no-cache-dir psycopg2-binary==2.9.10
