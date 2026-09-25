"""Create/update the dedicated Grafana reader using the project's database admin."""

import os

import psycopg2
from psycopg2 import sql

from src.config.settings import settings


def main() -> None:
    password = os.getenv("GRAFANA_DB_PASSWORD")
    if not password:
        raise SystemExit("Añade GRAFANA_DB_PASSWORD a .env antes de ejecutar setup-dashboard")
    connection = psycopg2.connect(settings.database.url, connect_timeout=10)
    try:
        with connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = 'trading_grafana'")
            if cursor.fetchone() is None:
                cursor.execute("CREATE ROLE trading_grafana LOGIN")
            cursor.execute(
                sql.SQL("ALTER ROLE trading_grafana PASSWORD {}").format(sql.Literal(password))
            )
            cursor.execute("GRANT USAGE ON SCHEMA public TO trading_grafana")
            cursor.execute("GRANT SELECT ON public.ohlcv TO trading_grafana")
    finally:
        connection.close()
    print("Usuario trading_grafana preparado (lectura de ohlcv). Ejecuta make up.")


if __name__ == "__main__":
    main()
