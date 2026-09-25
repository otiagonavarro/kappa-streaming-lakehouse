"""Inventory use cases."""
import psycopg  # pyright: ignore[reportMissingImports]

from ..domain.errors import DomainError, NotFound


def restock(conn: psycopg.Connection, product_id, quantity: int):
    if quantity <= 0:
        raise DomainError(f"restock quantity must be positive, got {quantity}")
    cur = conn.execute(
        "UPDATE inventory SET quantity = quantity + %s, updated_at = now() WHERE product_id = %s",
        (quantity, product_id),
    )
    if cur.rowcount == 0:
        raise NotFound(f"inventory for product {product_id}")


def low_stock_products(conn: psycopg.Connection, threshold: int) -> list:
    rows = conn.execute(
        "SELECT i.product_id FROM inventory i JOIN products p USING (product_id) "
        "WHERE i.quantity < %s AND p.status = 'active' ORDER BY i.product_id",
        (threshold,),
    ).fetchall()
    return [product_id for (product_id,) in rows]
