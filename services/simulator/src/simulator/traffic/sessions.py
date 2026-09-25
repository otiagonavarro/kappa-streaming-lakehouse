"""Storefront traffic: visitor sessions that emit clickstream and, at checkout, call the
order use case with the same session_id. Sessions live in memory only: like real browser
sessions, they may be lost on restart, while orders are durable in Postgres."""
import random
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

import psycopg  # pyright: ignore[reportMissingImports]

from ..config import SimConfig
from ..domain.errors import DomainError
from ..seed import new_faker, register_random_customer
from ..usecases import orders

DEVICES = [
    ("mobile", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148", 0.6),
    ("desktop", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36", 0.3),
    ("tablet", "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148", 0.1),
]
REFERRERS = [None, None, "https://www.google.com/", "https://www.instagram.com/", "https://t.co/", "newsletter"]
CENTS = Decimal("0.01")
FAR_FUTURE_MS = 4102444800000  # 2100-01-01, used to inject invalid timestamps


@dataclass
class Session:
    session_id: uuid.UUID
    anonymous_id: uuid.UUID
    customer_id: uuid.UUID | None
    device_type: str
    user_agent: str
    steps_left: int
    will_checkout: bool
    referrer: str | None
    cart: dict = field(default_factory=dict)
    done: bool = False


class TrafficGenerator:
    EVENT_TYPES = ("page_view", "add_to_cart", "remove_from_cart", "begin_checkout")

    def __init__(self, conn: psycopg.Connection, cfg: SimConfig, rng: random.Random, emit: Callable[[dict], None]):
        self._conn = conn
        self._cfg = cfg
        self._rng = rng
        self._emit = emit
        self._fake = new_faker(rng)
        self._sessions: list[Session] = []
        self._products: list[tuple] = []
        self._ticks = 0
        self.stats = {"orders": 0, "abandoned": 0, "stockouts": 0}

    # ── public API ───────────────────────────────────────────────────────────
    def tick(self, seconds: float) -> None:
        """Start new sessions for the elapsed time and advance every active session one step."""
        if self._ticks % 30 == 0:
            self._refresh_catalog()
        self._ticks += 1
        expected = self._cfg.sessions_per_second * seconds
        for _ in range(int(expected) + (self._rng.random() < expected % 1)):
            self.start_session()
        for session in self._sessions:
            self._step(session)
        self._sessions = [s for s in self._sessions if not s.done]

    def start_session(self, anonymous: bool | None = None, will_checkout: bool | None = None) -> Session:
        if not self._products:
            self._refresh_catalog()
        if anonymous is None:
            anonymous = self._rng.random() < self._cfg.anonymous_session_rate
        if will_checkout is None:
            will_checkout = self._rng.random() < 0.25
        device, agent, _ = self._rng.choices(DEVICES, weights=[w for *_, w in DEVICES])[0]
        session = Session(
            session_id=uuid.UUID(int=self._rng.getrandbits(128), version=4),
            anonymous_id=uuid.UUID(int=self._rng.getrandbits(128), version=4),
            customer_id=None if anonymous else self._random_customer(),
            device_type=device,
            user_agent=agent,
            steps_left=self._rng.randint(3, 12),
            will_checkout=will_checkout,
            referrer=self._rng.choice(REFERRERS),
        )
        self._sessions.append(session)
        return session

    def run_to_end(self, session: Session) -> None:
        while not session.done:
            self._step(session)
        self._sessions = [s for s in self._sessions if not s.done]

    # ── session behaviour ────────────────────────────────────────────────────
    def _step(self, s: Session) -> None:
        if s.steps_left > 0:
            s.steps_left -= 1
            self._browse(s)
            return
        if s.will_checkout:
            if not s.cart:
                self._add_to_cart(s, self._rng.choice(self._products))
            self._checkout(s)
        s.done = True

    def _browse(self, s: Session) -> None:
        roll = self._rng.random()
        product = self._rng.choice(self._products)
        if roll < 0.15:
            self._page_view(s, self._rng.choice(["home", "search"]))
        elif roll < 0.30:
            self._page_view(s, "category", category_id=product[1])
        elif roll < 0.80 or (not s.cart and roll < 0.95):
            self._page_view(s, "product", product=product)
            if self._rng.random() < 0.3:
                self._add_to_cart(s, product)
        elif s.cart and roll < 0.90:
            product_id = self._rng.choice(list(s.cart))
            quantity = s.cart.pop(product_id)
            self._event(s, "remove_from_cart", product_id=str(product_id), quantity=quantity)
        else:
            self._page_view(s, "cart")

    def _page_view(self, s: Session, page_type: str, product=None, category_id=None) -> None:
        url = {"home": "/", "search": f"/search?q={self._fake.word()}", "cart": "/cart"}.get(page_type)
        if product is not None:
            url = f"/p/{product[0]}"
            category_id = product[1]
        elif page_type == "category":
            url = f"/c/{category_id}"
        self._event(
            s,
            "page_view",
            page_type=page_type,
            page_url=url,
            referrer=s.referrer,
            category_id=str(category_id) if category_id else None,
            product_id=str(product[0]) if product else None,
        )
        s.referrer = None  # only the landing page carries the external referrer

    def _add_to_cart(self, s: Session, product) -> None:
        product_id, category_id, price = product
        quantity = self._rng.randint(1, 3)
        s.cart[product_id] = s.cart.get(product_id, 0) + quantity
        self._event(
            s,
            "add_to_cart",
            product_id=str(product_id),
            category_id=str(category_id),
            quantity=quantity,
            unit_price=price,
        )

    def _checkout(self, s: Session) -> None:
        if s.customer_id is None:  # login (existing customer) or sign-up: the stitching point
            s.customer_id = self._random_customer() if self._rng.random() < 0.6 else self._sign_up()
        prices = {p[0]: p[2] for p in self._products}
        cart_value = sum((prices.get(pid, Decimal(0)) * q for pid, q in s.cart.items()), Decimal(0))
        self._event(
            s, "begin_checkout", cart_value=cart_value.quantize(CENTS), item_count=sum(s.cart.values())
        )
        if self._rng.random() >= self._cfg.checkout_conversion:
            self.stats["abandoned"] += 1
            return
        try:
            orders.place_order(self._conn, s.customer_id, dict(s.cart), session_id=s.session_id)
            self.stats["orders"] += 1
        except DomainError:
            self.stats["stockouts"] += 1  # out of stock / discontinued meanwhile: the visitor gives up

    # ── helpers ──────────────────────────────────────────────────────────────
    def _event(self, s: Session, event_type: str, **fields) -> None:
        event = {
            "event_id": str(uuid.UUID(int=self._rng.getrandbits(128), version=4)),
            "event_type": event_type,
            "event_ts": int(time.time() * 1000),
            "session_id": str(s.session_id),
            "anonymous_id": str(s.anonymous_id),
            "customer_id": str(s.customer_id) if s.customer_id else None,
            "device_type": s.device_type,
            "user_agent": s.user_agent,
            "page_type": None,
            "page_url": None,
            "referrer": None,
            "category_id": None,
            "product_id": None,
            "quantity": None,
            "unit_price": None,
            "cart_value": None,
            "item_count": None,
        }
        event |= fields
        if self._rng.random() < self._cfg.invalid_event_rate:
            event = self._corrupt(event)
        self._emit(event)

    def _corrupt(self, event: dict) -> dict:
        """Schema-valid but semantically invalid: what silver must quarantine."""
        if self._rng.random() < 0.5:
            return {**event, "event_type": "unknown_event"}
        return {**event, "event_ts": FAR_FUTURE_MS + self._rng.randint(1, 10**9)}

    def _refresh_catalog(self) -> None:
        self._products = self._conn.execute(
            "SELECT product_id, category_id, price FROM products WHERE status = 'active'"
        ).fetchall()
        if not self._products:
            raise RuntimeError("no active products: seed the database first")

    def _random_customer(self):
        row = self._conn.execute(
            "SELECT customer_id FROM customers WHERE status = 'active' ORDER BY random() LIMIT 1"
        ).fetchone()
        return row[0] if row else self._sign_up()

    def _sign_up(self):
        for _ in range(3):
            try:
                return register_random_customer(self._conn, self._fake, self._rng)
            except DomainError:  # e-mail collision: try another identity
                continue
        raise RuntimeError("could not register a new customer")
