import uuid
import random
from datetime import datetime, timezone
from faker import Faker


class EventGenerator:
    EVENT_TYPES = ["page_view", "add_to_cart", "purchase"]
    # Realistic funnel weights: most events are page views
    WEIGHTS = [0.70, 0.20, 0.10]

    def __init__(self, seed: int | None = None):
        self._fake = Faker()
        self._rng = random.Random(seed)
        if seed is not None:
            Faker.seed(seed)

        # Pre-generate a pool of user/product IDs for realism
        self._users = [f"U{self._rng.randint(1000, 9999)}" for _ in range(200)]
        self._products = [f"P{self._rng.randint(100, 599)}" for _ in range(50)]
        self._sessions: dict[str, str] = {}  # user_id -> session_id

    def _get_or_create_session(self, user_id: str) -> str:
        if user_id not in self._sessions or self._rng.random() < 0.05:
            self._sessions[user_id] = str(uuid.UUID(int=self._rng.getrandbits(128)))
        return self._sessions[user_id]

    def generate(self) -> dict:
        event_type = self._rng.choices(self.EVENT_TYPES, weights=self.WEIGHTS, k=1)[0]
        user_id = self._rng.choice(self._users)
        session_id = self._get_or_create_session(user_id)
        product_id = self._rng.choice(self._products)

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
                "price": round(self._rng.uniform(9.99, 499.99), 2),
            }
        elif event_type == "purchase":
            event["metadata"] = {
                "order_id": str(uuid.UUID(int=self._rng.getrandbits(128))),
                "total": round(self._rng.uniform(19.99, 999.99), 2),
                "items": self._rng.randint(1, 8),
            }

        return event
