"""Fixtures for simulator tests against a real PostgreSQL.

Set TEST_POSTGRES_DSN to reuse an existing database (CI service container);
otherwise a throwaway postgres:15.6-alpine is started with Testcontainers.
The schema is the real Flyway migration, so tests exercise the same
constraints the application runs against.
"""
import os
import pathlib
from decimal import Decimal

import psycopg  # pyright: ignore[reportMissingImports]
import pytest
from simulator.usecases import (  # pyright: ignore[reportMissingImports]
    catalog,
    customers,
)
from simulator.usecases.customers import (
    AddressInput,  # pyright: ignore[reportMissingImports]
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MIGRATION = REPO_ROOT / "services" / "db" / "migrations" / "V1__oltp_schema.sql"
PLACEHOLDERS = {"debezium_user": "debezium", "debezium_password": "debezium"}
TABLES = "customers, addresses, categories, products, inventory, orders, order_items, payments, shipments"


@pytest.fixture(scope="session")
def postgres_dsn():
    if dsn := os.environ.get("TEST_POSTGRES_DSN"):
        yield dsn
        return
# sourcery skip: dont-import-test-modules
    try:
        from testcontainers.community.postgres import PostgresContainer
    except ImportError:  # testcontainers < 4.9
        from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:15.6-alpine", driver=None) as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def migrated_dsn(postgres_dsn):
    sql = MIGRATION.read_text()
    for key, value in PLACEHOLDERS.items():
        sql = sql.replace("${" + key + "}", value)
    with psycopg.connect(postgres_dsn, autocommit=True) as conn:
        conn.execute("DROP PUBLICATION IF EXISTS shop_pub")
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute(sql)
    return postgres_dsn


@pytest.fixture
def conn(migrated_dsn):
    with psycopg.connect(migrated_dsn, autocommit=True) as c:
        c.execute(f"TRUNCATE {TABLES} CASCADE")
        yield c


@pytest.fixture
def second_conn(migrated_dsn):
    with psycopg.connect(migrated_dsn, autocommit=True) as c:
        yield c


def _address(**overrides) -> AddressInput:
    base = {"street": "Rua Augusta", "number": "100", "city": "São Paulo", "state": "SP", "zip_code": "01305-000"}
    return AddressInput(**base | overrides)


@pytest.fixture
def make_customer(conn):
    counter = iter(range(1_000_000))

    def _make(**overrides):
        n = next(counter)
        kwargs = {
            "full_name": f"Customer {n}",
            "email": f"customer{n}@example.com",
            "phone": f"+55 11 9{n:08d}",
            "document": f"{n:011d}",
            "address": _address(),
        }
        kwargs.update(overrides)
        return customers.register_customer(conn, **kwargs)

    return _make


@pytest.fixture
def make_product(conn):
    counter = iter(range(1_000_000))
    state = {}

    def _make(price="10.00", stock=10, **overrides):
        if "category_id" not in state:
            state["category_id"] = catalog.create_category(conn, "Electronics")
        n = next(counter)
        kwargs = {
            "sku": f"SKU-{n:05d}",
            "name": f"Product {n}",
            "category_id": state["category_id"],
            "price": Decimal(price),
            "initial_stock": stock,
        }
        kwargs.update(overrides)
        return catalog.create_product(conn, **kwargs)

    return _make


def fetch_one(conn, sql, *params):
    return conn.execute(sql, params).fetchone()
