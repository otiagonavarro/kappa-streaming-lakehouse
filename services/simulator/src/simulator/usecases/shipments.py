"""Shipment use cases."""
import secrets

import psycopg  # pyright: ignore[reportMissingImports]

from ..domain.order_state import OrderStatus
from .orders import transition


def ship_order(conn: psycopg.Connection, order_id, carrier: str):
    with conn.transaction():
        transition(conn, order_id, OrderStatus.SHIPPED)
        (shipment_id,) = conn.execute(
            "INSERT INTO shipments (order_id, carrier, tracking_code) VALUES (%s, %s, %s) RETURNING shipment_id",
            (order_id, carrier, f"BR{secrets.token_hex(5).upper()}"),
        ).fetchone()
    return shipment_id


def deliver_order(conn: psycopg.Connection, order_id):
    with conn.transaction():
        transition(conn, order_id, OrderStatus.DELIVERED)
        conn.execute("UPDATE shipments SET delivered_at = now() WHERE order_id = %s", (order_id,))
