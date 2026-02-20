import os
import pymysql
from pymysql.err import OperationalError, ProgrammingError

from app import create_app, init_db


def get_env(name, default):
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def create_database_if_missing():
    host = get_env("DB_HOST", "localhost")
    port = int(get_env("DB_PORT", "3306"))
    user = get_env("DB_USER", "root")
    password = get_env("DB_PASSWORD", "")
    db_name = get_env("DB_NAME", "eventflow_db")

    connection = pymysql.connect(
        host=host,
        user=user,
        password=password,
        port=port,
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        connection.close()

def apply_schema_file():
    host = get_env("DB_HOST", "localhost")
    port = int(get_env("DB_PORT", "3306"))
    user = get_env("DB_USER", "root")
    password = get_env("DB_PASSWORD", "")
    db_name = get_env("DB_NAME", "eventflow_db")

    schema_path = os.path.join(os.path.dirname(__file__), "mysql_schema.sql")
    if not os.path.exists(schema_path):
        return

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    connection = pymysql.connect(
        host=host,
        user=user,
        password=password,
        port=port,
        database=db_name,
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            for statement in schema_sql.split(";"):
                sql = statement.strip()
                if sql:
                    cursor.execute(sql)
    finally:
        connection.close()

def apply_incremental_alters():
    host = get_env("DB_HOST", "localhost")
    port = int(get_env("DB_PORT", "3306"))
    user = get_env("DB_USER", "root")
    password = get_env("DB_PASSWORD", "")
    db_name = get_env("DB_NAME", "eventflow_db")

    alters = [
        "ALTER TABLE events ADD COLUMN created_by_admin_id INT NULL",
        "ALTER TABLE events ADD COLUMN default_currency VARCHAR(10) NOT NULL DEFAULT 'USD'",
        "ALTER TABLE events ADD COLUMN currency_options VARCHAR(120) NOT NULL DEFAULT 'USD'",
        "ALTER TABLE events ADD COLUMN mpesa_number VARCHAR(40)",
        "ALTER TABLE events ADD COLUMN paypal_account VARCHAR(120)",
        "ALTER TABLE events ADD COLUMN zelle_account VARCHAR(120)",
        "ALTER TABLE events ADD COLUMN card_instructions VARCHAR(255)",
        "UPDATE events SET created_by_admin_id = (SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1) WHERE created_by_admin_id IS NULL",
        "ALTER TABLE events MODIFY COLUMN created_by_admin_id INT NOT NULL",
        "ALTER TABLE events ADD INDEX idx_events_admin_owner (created_by_admin_id)",
        "ALTER TABLE events ADD CONSTRAINT fk_events_admin_owner FOREIGN KEY (created_by_admin_id) REFERENCES users(id)",
        "ALTER TABLE payments ADD COLUMN currency VARCHAR(10) NOT NULL DEFAULT 'USD'",
        "ALTER TABLE payments ADD COLUMN pay_to VARCHAR(255)"
    ]

    connection = pymysql.connect(
        host=host,
        user=user,
        password=password,
        port=port,
        database=db_name,
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            for sql in alters:
                try:
                    cursor.execute(sql)
                except (OperationalError, ProgrammingError) as e:
                    # 1060: Duplicate column name
                    # 1061: Duplicate key name
                    # 1826: Duplicate foreign key constraint name
                    if getattr(e, "args", [None])[0] not in (1060, 1061, 1826):
                        raise
    finally:
        connection.close()


if __name__ == "__main__":
    create_database_if_missing()
    apply_schema_file()
    apply_incremental_alters()
    app = create_app("mysql")
    init_db(app)
    print("MySQL setup complete.")
