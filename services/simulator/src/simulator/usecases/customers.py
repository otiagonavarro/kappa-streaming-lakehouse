"""Customer use cases. Each function is one transaction."""
from dataclasses import dataclass

import psycopg  # pyright: ignore[reportMissingImports]
from psycopg import errors as pg_errors  # pyright: ignore[reportMissingImports]

from ..domain.errors import DomainError, NotFound


@dataclass(frozen=True)
class AddressInput:
    street: str
    number: str
    city: str
    state: str
    zip_code: str


def register_customer(
    conn: psycopg.Connection,
    *,
    full_name: str,
    email: str,
    phone: str,
    document: str,
    address: AddressInput,
):
    try:
        with conn.transaction():
            (customer_id,) = conn.execute(
                "INSERT INTO customers (full_name, email, phone, document) VALUES (%s, %s, %s, %s) "
                "RETURNING customer_id",
                (full_name, email, phone, document),
            ).fetchone()
            _insert_address(conn, customer_id, address, is_primary=True)
    except pg_errors.UniqueViolation as exc:
        raise DomainError(f"email already registered: {email}") from exc
    return customer_id


def update_customer_contact(conn: psycopg.Connection, customer_id, *, email: str | None = None, phone: str | None = None):
    with conn.transaction():
        _lock_active_customer(conn, customer_id)
        conn.execute(
            "UPDATE customers SET email = coalesce(%s, email), phone = coalesce(%s, phone), updated_at = now() "
            "WHERE customer_id = %s",
            (email, phone, customer_id),
        )


def add_address(conn: psycopg.Connection, customer_id, address: AddressInput):
    with conn.transaction():
        _lock_active_customer(conn, customer_id)
        return _insert_address(conn, customer_id, address, is_primary=False)


def set_primary_address(conn: psycopg.Connection, customer_id, address_id):
    with conn.transaction():
        _lock_active_customer(conn, customer_id)
        owned = conn.execute(
            "SELECT 1 FROM addresses WHERE address_id = %s AND customer_id = %s", (address_id, customer_id)
        ).fetchone()
        if owned is None:
            raise NotFound(f"address {address_id} of customer {customer_id}")
        conn.execute(
            "UPDATE addresses SET is_primary = false, updated_at = now() WHERE customer_id = %s AND is_primary",
            (customer_id,),
        )
        conn.execute(
            "UPDATE addresses SET is_primary = true, updated_at = now() WHERE address_id = %s", (address_id,)
        )


def forget_customer(conn: psycopg.Connection, customer_id):
    """LGPD erasure: null every PII column and soft-delete. City/state stay (analytical, not identifying)."""
    with conn.transaction():
        _lock_active_customer(conn, customer_id)
        conn.execute(
            "UPDATE customers SET full_name = NULL, email = NULL, phone = NULL, document = NULL, "
            "status = 'deleted', updated_at = now() WHERE customer_id = %s",
            (customer_id,),
        )
        conn.execute(
            "UPDATE addresses SET street = NULL, number = NULL, zip_code = NULL, updated_at = now() "
            "WHERE customer_id = %s",
            (customer_id,),
        )


def _insert_address(conn, customer_id, address: AddressInput, *, is_primary: bool):
    (address_id,) = conn.execute(
        "INSERT INTO addresses (customer_id, street, number, city, state, zip_code, is_primary) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING address_id",
        (customer_id, address.street, address.number, address.city, address.state, address.zip_code, is_primary),
    ).fetchone()
    return address_id


def _lock_active_customer(conn, customer_id) -> None:
    row = conn.execute("SELECT status FROM customers WHERE customer_id = %s FOR UPDATE", (customer_id,)).fetchone()
    if row is None:
        raise NotFound(f"customer {customer_id}")
    if row[0] == "deleted":
        raise DomainError(f"customer {customer_id} is deleted")
