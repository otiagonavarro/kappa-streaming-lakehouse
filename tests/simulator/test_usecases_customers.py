import pytest
from conftest import _address, fetch_one
from simulator.domain.errors import (  # pyright: ignore[reportMissingImports]
    DomainError,
    NotFound,
)
from simulator.usecases import customers  # pyright: ignore[reportMissingImports]


def test_register_creates_customer_with_primary_address(conn, make_customer):
    customer_id = make_customer(email="ana@example.com")

    assert fetch_one(conn, "SELECT email, status FROM customers WHERE customer_id = %s", customer_id) == (
        "ana@example.com",
        "active",
    )
    assert fetch_one(conn, "SELECT count(*), bool_and(is_primary) FROM addresses WHERE customer_id = %s", customer_id) == (
        1,
        True,
    )


def test_register_rejects_duplicate_email_case_insensitively(conn, make_customer):
    make_customer(email="ana@example.com")
    with pytest.raises(DomainError):
        make_customer(email="ANA@example.com")
    assert fetch_one(conn, "SELECT count(*) FROM customers")[0] == 1


def test_set_primary_address_moves_the_flag(conn, make_customer):
    customer_id = make_customer()
    new_address = customers.add_address(conn, customer_id, _address(city="Recife", state="PE"))

    customers.set_primary_address(conn, customer_id, new_address)

    rows = conn.execute(
        "SELECT city FROM addresses WHERE customer_id = %s AND is_primary", (customer_id,)
    ).fetchall()
    assert rows == [("Recife",)]


def test_update_contact_changes_only_given_fields(conn, make_customer):
    customer_id = make_customer(email="old@example.com", phone="+55 11 1")
    customers.update_customer_contact(conn, customer_id, email="new@example.com")

    assert fetch_one(conn, "SELECT email, phone FROM customers WHERE customer_id = %s", customer_id) == (
        "new@example.com",
        "+55 11 1",
    )


def test_forget_customer_nulls_pii_and_keeps_analytical_fields(conn, make_customer):
    customer_id = make_customer()
    customers.forget_customer(conn, customer_id)

    assert fetch_one(
        conn, "SELECT full_name, email, phone, document, status FROM customers WHERE customer_id = %s", customer_id
    ) == (None, None, None, None, "deleted")
    assert fetch_one(
        conn, "SELECT street, number, zip_code, city, state FROM addresses WHERE customer_id = %s", customer_id
    ) == (None, None, None, "São Paulo", "SP")


def test_forget_unknown_customer_raises(conn):
    with pytest.raises(NotFound):
        customers.forget_customer(conn, "00000000-0000-0000-0000-000000000000")
