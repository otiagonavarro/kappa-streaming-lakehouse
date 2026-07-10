import uuid
import random
from datetime import datetime, timezone
from faker import Faker

from .entities import CategoryPool, ProductPool, UserPool


class EventGenerator:
    EVENT_TYPES = ["page_view", "add_to_cart", "purchase"]
    WEIGHTS = [0.70, 0.20, 0.10]

    def __init__(self, seed: int | None = None):
        self._fake = Faker()
        self._rng = random.Random(seed)
        if seed is not None:
            Faker.seed(seed)

        self._categories = CategoryPool()
        self._products = ProductPool(self._rng, self._categories, seed)
        self._users = UserPool(self._rng, seed=seed)

        self._user_ids = [u["user_id"] for u in self._users.all()]
        self._product_ids = [p["product_id"] for p in self._products.all()]
        self._sessions: dict[str, str] = {}
        self._order_counter = 0

    def _get_or_create_session(self, user_id: str) -> str:
        if user_id not in self._sessions or self._rng.random() < 0.05:
            self._sessions[user_id] = str(uuid.UUID(int=self._rng.getrandbits(128)))
        return self._sessions[user_id]

    def _next_order_id(self) -> str:
        self._order_counter += 1
        return f"ORD-{self._order_counter:06d}"

    def generate(self) -> dict:
        event_type = self._rng.choices(self.EVENT_TYPES, weights=self.WEIGHTS, k=1)[0]
        user_id = self._rng.choice(self._user_ids)
        session_id = self._get_or_create_session(user_id)
        product_id = self._rng.choice(self._product_ids)

        event: dict = {
            "event_id": str(uuid.UUID(int=self._rng.getrandbits(128))),
            "event_type": event_type,
            "user_id": user_id,
            "session_id": session_id,
            "product_id": product_id,
            "timestamp": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S.") + f"{datetime.now(tz=timezone.utc).microsecond // 1000:03d}",
            "metadata": {},
        }

        if event_type == "page_view":
            event["metadata"] = {
                "page": self._fake.uri_path(),
                "referrer": self._fake.uri() if self._rng.random() > 0.4 else None,
            }
        elif event_type == "add_to_cart":
            event["metadata"] = {
                "quantity": self._rng.randint(1, 5),
                "price": self._products.get_price(product_id),
            }
        elif event_type == "purchase":
            order_id = self._next_order_id()
            quantity = self._rng.randint(1, 4)
            unit_price = self._products.get_price(product_id)
            total = round(unit_price * quantity, 2)
            event["metadata"] = {
                "order_id": order_id,
                "total": total,
                "items": quantity,
            }

        return event

    def generate_entity_snapshots(self) -> list[dict]:
        """Return initial snapshots of all entities for the entity-updates topic."""
        snapshots: list[dict] = []
        now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S.000")

        for cat in self._categories.all():
            snapshots.append({**cat, "entity_type": "category", "timestamp": now})

        for user in self._users.all():
            snapshots.append({**user, "entity_type": "user", "updated_at": now, "timestamp": now})

        for product in self._products.all():
            snapshots.append({**product, "entity_type": "product", "timestamp": now})

        return snapshots

    def generate_entity_update(self) -> dict | None:
        """Generate a random entity update (SCD Type 1 style). ~5% chance per call."""
        if self._rng.random() > 0.05:
            return None

        now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S.000")
        entity_type = self._rng.choice(["user", "product"])

        if entity_type == "user":
            user = self._rng.choice(self._users.all())
            field = self._rng.choice(["city", "status", "email"])
            if field == "city":
                user["user_city"] = self._fake.city()
            elif field == "status":
                user["user_status"] = "inactive" if user["user_status"] == "active" else "active"
            elif field == "email":
                user["user_email"] = self._fake.ascii_free_email()
            return {**user, "entity_type": "user", "updated_at": now, "timestamp": now}

        else:
            product = self._rng.choice(self._products.all())
            field = self._rng.choice(["price", "status"])
            if field == "price":
                product["price"] = round(self._rng.uniform(9.99, 499.99), 2)
            elif field == "status":
                product["product_status"] = "inactive" if product["product_status"] == "active" else "active"
            return {**product, "entity_type": "product", "timestamp": now}

    def generate_order(self, user_id: str, product_id: str) -> dict:
        """Generate a structured order entity for the entity-updates topic."""
        now = datetime.now(tz=timezone.utc)
        order_id = self._next_order_id()
        quantity = self._rng.randint(1, 4)
        unit_price = self._products.get_price(product_id)
        total = round(unit_price * quantity, 2)

        return {
            "entity_type": "order",
            "order_id": order_id,
            "order_user_id": user_id,
            "order_total": total,
            "order_status": "completed",
            "order_created_at": now.strftime("%Y-%m-%d %H:%M:%S.000"),
            "order_date": now.date().isoformat(),
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S.000"),
        }

    def generate_order_item(self, order_id: str, product_id: str, quantity: int) -> dict:
        """Generate an order item entity for the entity-updates topic."""
        now = datetime.now(tz=timezone.utc)
        unit_price = self._products.get_price(product_id)
        line_total = round(unit_price * quantity, 2)

        return {
            "entity_type": "order_item",
            "order_item_id": f"OI-{uuid.uuid4().hex[:12]}",
            "order_item_order_id": order_id,
            "product_id": product_id,
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": line_total,
            "order_date": now.date().isoformat(),
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S.000"),
        }
