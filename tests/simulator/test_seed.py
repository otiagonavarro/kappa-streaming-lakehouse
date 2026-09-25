import random

from conftest import fetch_one
from simulator.seed import seed_if_empty


def counts(conn):
    return fetch_one(
        conn,
        "SELECT (SELECT count(*) FROM categories), (SELECT count(*) FROM products), "
        "(SELECT count(*) FROM inventory), (SELECT count(*) FROM customers), "
        "(SELECT count(*) FROM addresses WHERE is_primary)",
    )


def test_seed_populates_an_empty_database(conn):
    assert seed_if_empty(conn, random.Random(1), customers=20) is True
    categories, products, inventory, customers, primary_addresses = counts(conn)
    assert categories >= 10
    assert products == inventory >= 50
    assert customers == primary_addresses == 20


def test_seed_is_a_no_op_on_a_populated_database(conn):
    seed_if_empty(conn, random.Random(1), customers=5)
    before = counts(conn)
    assert seed_if_empty(conn, random.Random(2), customers=5) is False
    assert counts(conn) == before
