from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from .db import Base, engine

logger = logging.getLogger("sparkflow.migrations")

SCHEMA_LOCK = "sparkflow:schema-migrations"
SCHEMA_VERSION_TABLE = "sparkflow_schema_migrations"


def _columns(connection: Connection, table: str) -> dict[str, dict]:
    return {str(column["name"]): column for column in inspect(connection).get_columns(table)}


def _add_column(connection: Connection, table: str, column: str, definition: str) -> None:
    if column not in _columns(connection, table):
        connection.execute(text(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}"))
        logger.info("schema.add_column table=%s column=%s", table, column)


def _ensure_base_tables(connection: Connection) -> None:
    Base.metadata.create_all(connection)


def _ensure_account_inspection(connection: Connection) -> None:
    _add_column(connection, "accounts", "inspection_status", "varchar(16) NULL")
    _add_column(connection, "accounts", "inspection_message", "varchar(255) NULL")
    _add_column(connection, "accounts", "checked_at", "datetime(3) NULL")
    _add_column(connection, "accounts", "friends", "json NULL")


def _ensure_plan_permissions(connection: Connection) -> None:
    _add_column(connection, "plans", "plugin_permissions", "json NULL")
    _add_column(connection, "plans", "permissions", "json NULL")


def _ensure_order_fields(connection: Connection) -> None:
    _add_column(connection, "orders", "months", "int NULL")
    connection.execute(text(
        "UPDATE `orders` SET `months` = CASE `cycle` "
        "WHEN 'monthly' THEN 1 WHEN 'quarterly' THEN 3 WHEN 'yearly' THEN 12 "
        "ELSE NULL END WHERE `months` IS NULL",
    ))
    unknown = connection.execute(text(
        "SELECT COUNT(*) FROM `orders` WHERE `months` IS NULL",
    )).scalar_one()
    if int(unknown) > 0:
        raise RuntimeError("orders contains an unknown cycle; automatic migration stopped")
    column = _columns(connection, "orders").get("months")
    if column and column.get("nullable"):
        connection.execute(text("ALTER TABLE `orders` MODIFY COLUMN `months` int NOT NULL"))
    _add_column(connection, "orders", "payment_config_encrypted", "text NULL")


def _ensure_task_plugin_fields(connection: Connection) -> None:
    _add_column(connection, "tasks", "plugin_id", "varchar(80) NOT NULL DEFAULT 'douyin_streak'")
    _add_column(connection, "tasks", "plugin_config", "json NULL")
    column = _columns(connection, "tasks").get("account_id")
    if column and column.get("nullable") is False:
        connection.execute(text("ALTER TABLE `tasks` MODIFY COLUMN `account_id` varchar(36) NULL"))


def _ensure_run_events(connection: Connection) -> None:
    # Base.metadata.create_all handles this table on fresh installations.
    Base.metadata.create_all(connection, tables=[Base.metadata.tables["run_events"]])


Migration = tuple[str, Callable[[Connection], None]]
MIGRATIONS: tuple[Migration, ...] = (
    ("0000_base_schema", _ensure_base_tables),
    ("0001_run_indexes", _ensure_base_tables),
    ("0002_platform_tables", _ensure_base_tables),
    ("0003_announcement_reads", _ensure_base_tables),
    ("0004_plugin_permissions", _ensure_plan_permissions),
    ("0005_account_inspection", _ensure_account_inspection),
    ("0006_plan_permissions", _ensure_plan_permissions),
    ("0007_run_events", _ensure_run_events),
    ("0008_payment_config", _ensure_order_fields),
    ("0009_plugin_tasks", _ensure_task_plugin_fields),
)


def ensure_schema() -> None:
    """Run all known schema versions before API or Worker serves traffic."""
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
        return

    with engine.connect() as connection:
        lock = connection.execute(
            text("SELECT GET_LOCK(:name, :timeout)"),
            {"name": SCHEMA_LOCK, "timeout": 60},
        ).scalar()
        if int(lock or 0) != 1:
            raise RuntimeError("could not acquire database migration lock within 60 seconds")
        try:
            connection.execute(text(f"""
                CREATE TABLE IF NOT EXISTS `{SCHEMA_VERSION_TABLE}` (
                    `version` varchar(64) NOT NULL,
                    `applied_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
                    PRIMARY KEY (`version`)
                )
            """))
            applied = {
                str(row[0])
                for row in connection.execute(
                    text(f"SELECT `version` FROM `{SCHEMA_VERSION_TABLE}`"),
                ).all()
            }
            for version, migration in MIGRATIONS:
                if version in applied:
                    continue
                logger.info("schema.migrate version=%s", version)
                migration(connection)
                connection.execute(
                    text(f"INSERT INTO `{SCHEMA_VERSION_TABLE}` (`version`) VALUES (:version)"),
                    {"version": version},
                )
                connection.commit()
        finally:
            connection.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": SCHEMA_LOCK})
