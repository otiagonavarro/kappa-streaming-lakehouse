"""Back-office activity: the slow churn of catalog and customer data that makes
slowly-changing dimensions (SCD2) meaningful downstream."""

import contextlib
import random
from decimal import Decimal

import psycopg  # pyright: ignore[reportMissingImports]
from psycopg import sql  # pyright: ignore[reportMissingImports]

from ..config import SimConfig
from ..domain.errors import DomainError
from ..seed import new_faker, random_address
from ..usecases import catalog, customers, inventory

# Default probability of each action per tick (1 tick ≈ 1 s).
DEFAULT_RATES = {
    "change_price": 0.05,
    "discontinue_product": 0.002,
    "launch_product": 0.004,
    "update_contact": 0.03,
    "move_address": 0.02,
    "forget_customer": 0.002,
}


class Backoffice:
    ACTIONS = tuple(DEFAULT_RATES)

    def __init__(self, conn: psycopg.Connection, cfg: SimConfig, rng: random.Random, rates: dict | None = None):
        self._conn = conn
        self._cfg = cfg
        self._rng = rng
        self._rates = DEFAULT_RATES if rates is None else rates
        self._fake = new_faker(rng)

    def tick(self) -> list[str]:
        for product_id in inventory.low_stock_products(self._conn, self._cfg.low_stock_threshold):
            inventory.restock(self._conn, product_id, self._cfg.restock_quantity)
        done = []
        for action in self.ACTIONS:
            if self._rng.random() < self._rates.get(action, 0.0):
                # e.g. the picked row changed meanwhile; try again next tick
                with contextlib.suppress(DomainError):
                    getattr(self, f"_{action}")()
                    done.append(action)
        return done

    def _change_price(self):
        product_id, price = self._pick("SELECT product_id, price FROM products WHERE status = 'active'")
        factor = Decimal(str(self._rng.uniform(0.85, 1.15)))
        catalog.change_price(self._conn, product_id, max(Decimal("1.00"), (price * factor).quantize(Decimal("0.01"))))

    def _discontinue_product(self):
        (product_id,) = self._pick("SELECT product_id FROM products WHERE status = 'active'")
        catalog.discontinue_product(self._conn, product_id)

    def _launch_product(self):
        (category_id,) = self._pick("SELECT category_id FROM categories WHERE parent_id IS NOT NULL")
        catalog.create_product(
            self._conn,
            sku=f"NEW-{self._rng.randrange(16**8):08X}",
            name=f"{self._fake.word().title()} {self._fake.word().title()} Edition",
            category_id=category_id,
            price=Decimal(str(round(self._rng.uniform(9.99, 499.99), 2))),
            initial_stock=self._rng.randint(50, 200),
        )

    def _update_contact(self):
        (customer_id,) = self._pick("SELECT customer_id FROM customers WHERE status = 'active'")
        customers.update_customer_contact(self._conn, customer_id, phone=self._fake.cellphone_number())

    def _move_address(self):
        (customer_id,) = self._pick("SELECT customer_id FROM customers WHERE status = 'active'")
        address_id = customers.add_address(self._conn, customer_id, random_address(self._fake, self._rng))
        customers.set_primary_address(self._conn, customer_id, address_id)

    def _forget_customer(self):
        (customer_id,) = self._pick("SELECT customer_id FROM customers WHERE status = 'active'")
        customers.forget_customer(self._conn, customer_id)

    def _pick(self, query: str) -> tuple:
        """Random row of an internal, constant query (never user input)."""
        row = self._conn.execute(sql.SQL("{} ORDER BY random() LIMIT 1").format(sql.SQL(query))).fetchone()
        if row is None:
            raise DomainError("nothing to pick")
        return row
