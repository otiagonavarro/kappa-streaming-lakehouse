"""Catalog use cases: categories and products."""
from decimal import Decimal

import psycopg  # pyright: ignore[reportMissingImports]
from psycopg import sql

from ..domain.errors import DomainError, NotFound


def create_category(conn: psycopg.Connection, name: str, parent_id=None):
    (category_id,) = conn.execute(
        "INSERT INTO categories (name, parent_id) VALUES (%s, %s) RETURNING category_id", (name, parent_id)
    ).fetchone()
    return category_id


def create_product(
    conn: psycopg.Connection, *, sku: str, name: str, category_id, price: Decimal, initial_stock: int
):
    _ensure_positive(price)
    with conn.transaction():
        (product_id,) = conn.execute(
            "INSERT INTO products (sku, name, category_id, price) VALUES (%s, %s, %s, %s) RETURNING product_id",
            (sku, name, category_id, price),
        ).fetchone()
        conn.execute("INSERT INTO inventory (product_id, quantity) VALUES (%s, %s)", (product_id, initial_stock))
    return product_id


def change_price(conn: psycopg.Connection, product_id, new_price: Decimal):
    _ensure_positive(new_price)
    _update_product(conn, product_id, "price", new_price)


def discontinue_product(conn: psycopg.Connection, product_id):
    _update_product(conn, product_id, "status", "discontinued")


def _update_product(conn, product_id, column: str, value) -> None:
    cur = conn.execute(
        sql.SQL("UPDATE products SET {} = %s, updated_at = now() WHERE product_id = %s").format(sql.Identifier(column)),
        (value, product_id),
    )
    if cur.rowcount == 0:
        raise NotFound(f"product {product_id}")


def _ensure_positive(price: Decimal) -> None:
    if price <= 0:
        raise DomainError(f"price must be positive, got {price}")
