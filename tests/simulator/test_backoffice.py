import random

from conftest import fetch_one
from simulator.config import SimConfig
from simulator.seed import seed_if_empty
from simulator.traffic.backoffice import Backoffice


def test_restocks_products_below_threshold(conn, make_product):
    low = make_product(stock=1)
    Backoffice(conn, SimConfig(low_stock_threshold=5, restock_quantity=20), random.Random(0), rates={}).tick()
    assert fetch_one(conn, "SELECT quantity FROM inventory WHERE product_id = %s", low) == (21,)


def test_every_churn_action_runs_against_real_data(conn):
    seed_if_empty(conn, random.Random(1), customers=10)
    office = Backoffice(conn, SimConfig(), random.Random(3), rates={name: 1.0 for name in Backoffice.ACTIONS})

    done = office.tick()

    assert set(done) == set(Backoffice.ACTIONS)
    assert fetch_one(conn, "SELECT count(*) FROM customers WHERE status = 'deleted'") == (1,)
    assert fetch_one(conn, "SELECT count(*) FROM products WHERE status = 'discontinued'") == (1,)
    assert fetch_one(conn, "SELECT count(*) FROM addresses")[0] == 11
