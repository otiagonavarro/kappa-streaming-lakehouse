from decimal import Decimal

import pytest
from conftest import fetch_one
from simulator.domain.errors import DomainError  # pyright: ignore[reportMissingImports]
from simulator.usecases import (  # pyright: ignore[reportMissingImports]
    catalog,
    inventory,
)


def test_create_product_creates_inventory(conn, make_product):
    product_id = make_product(stock=7)
    assert fetch_one(conn, "SELECT quantity FROM inventory WHERE product_id = %s", product_id) == (7,)


def test_change_price(conn, make_product):
    product_id = make_product(price="10.00")
    catalog.change_price(conn, product_id, Decimal("12.50"))
    assert fetch_one(conn, "SELECT price FROM products WHERE product_id = %s", product_id) == (Decimal("12.50"),)


def test_change_price_rejects_non_positive(conn, make_product):
    product_id = make_product()
    with pytest.raises(DomainError):
        catalog.change_price(conn, product_id, Decimal(0))


def test_discontinue_product(conn, make_product):
    product_id = make_product()
    catalog.discontinue_product(conn, product_id)
    assert fetch_one(conn, "SELECT status FROM products WHERE product_id = %s", product_id) == ("discontinued",)


def test_restock_and_low_stock(conn, make_product):
    low = make_product(stock=2)
    high = make_product(stock=50)

    assert inventory.low_stock_products(conn, threshold=5) == [low]

    inventory.restock(conn, low, 10)
    assert fetch_one(conn, "SELECT quantity FROM inventory WHERE product_id = %s", low) == (12,)
    assert inventory.low_stock_products(conn, threshold=5) == []
    assert high
