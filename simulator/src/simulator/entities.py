"""E-commerce entity pools for realistic simulation.

Provides deterministic, pre-generated pools of users, products, and categories
with realistic metadata (names, emails, cities, prices, etc.).
"""
import random
from datetime import datetime, timedelta, timezone
from faker import Faker  # type: ignore


CATEGORIES = [
    ("CAT01", "Electronics", None),
    ("CAT02", "Books", None),
    ("CAT03", "Clothing", None),
    ("CAT04", "Home & Kitchen", None),
    ("CAT05", "Sports & Outdoors", None),
    ("CAT06", "Toys & Games", None),
    ("CAT07", "Health & Beauty", None),
    ("CAT08", "Automotive", None),
    ("CAT09", "Grocery", None),
    ("CAT10", "Music", None),
]

# Subcategories for richer hierarchy
SUBCATEGORIES = {
    "CAT01": [("CAT0101", "Smartphones"), ("CAT0102", "Laptops"), ("CAT0103", "Audio")],
    "CAT02": [("CAT0201", "Fiction"), ("CAT0202", "Non-Fiction"), ("CAT0203", "Technical")],
    "CAT03": [("CAT0301", "Men"), ("CAT0302", "Women"), ("CAT0303", "Kids")],
    "CAT04": [("CAT0401", "Furniture"), ("CAT0402", "Appliances"), ("CAT0403", "Decor")],
    "CAT05": [("CAT0501", "Gym Equipment"), ("CAT0502", "Camping"), ("CAT0503", "Team Sports")],
}


class CategoryPool:
    """Fixed set of product categories with hierarchy."""

    def __init__(self):
        self._categories: list[dict] = []
        self._categories.extend(
            {
                "category_id": cat_id,
                "cat_name": name,
                "parent_category_id": parent_id,
            }
            for cat_id, name, parent_id in CATEGORIES
        )
        for parent_id, subs in SUBCATEGORIES.items():
            self._categories.extend(
                {
                    "category_id": cat_id,
                    "cat_name": name,
                    "parent_category_id": parent_id,
                }
                for cat_id, name in subs
            )

    def all(self) -> list[dict]:
        return list(self._categories)

    def root_ids(self) -> list[str]:
        return [c["category_id"] for c in self._categories if c["parent_category_id"] is None]


class ProductPool:
    """Pre-generated product catalog with realistic names and prices."""

    PRODUCT_NAMES = [
        "Wireless Bluetooth Headphones", "USB-C Charging Cable 6ft", "Mechanical Keyboard RGB",
        "Ergonomic Mouse Pad", "4K Webcam HD", "Portable SSD 1TB", "Laptop Stand Adjustable",
        "Noise Cancelling Earbuds", "Smart Watch Fitness", "Power Bank 20000mAh",
        "LED Desk Lamp", "Monitor Light Bar", "Cable Management Kit", "Webcam Tripod Mount",
        "Bluetooth Speaker Mini", "Phone Case Premium", "Screen Protector Pack",
        "Desk Organizer Wood", "Wireless Charger Pad", "HDMI Cable 4K 10ft",
        "Java Programming Handbook", "Data Engineering Guide", "Python Cookbook 3rd Ed",
        "System Design Interview", "Clean Architecture Manual", "SQL Deep Dive",
        "Kubernetes in Action", "Flink Stream Processing", "Cloud Native Patterns",
        "Machine Learning Ops",
        "Cotton T-Shirt Classic", "Denim Jacket Vintage", "Running Shoes Pro",
        "Wool Sweater Premium", "Hiking Boots Waterproof", "Yoga Pants Flex",
        "Rain Jacket Lightweight", "Baseball Cap Classic", "Swim Goggles Pro",
        "Cycling Jersey Aero",
        "Cast Iron Skillet 12in", "French Oven 6Qt", "Knife Set 8pc",
        "Coffee Maker Programmable", "Blender High Speed", "Air Fryer XL",
        "Bamboo Cutting Board", "Insulated Tumbler 30oz", "Silicone Baking Mat",
        "Espresso Machine Compact",
        "Yoga Mat Premium", "Resistance Bands Set", "Dumbbells Adjustable",
        "Camping Tent 4-Person", "Sleeping Bag Ultralight", "Hiking Backpack 40L",
        "Soccer Ball Official", "Tennis Racket Carbon", "Jump Rope Speed",
        "Foam Roller Recovery",
    ]

    def __init__(self, rng: random.Random, category_pool: CategoryPool, seed: int | None = None):
        self._rng = rng
        self._category_pool = category_pool
        self._products: list[dict] = []
        root_cats = category_pool.root_ids()

        for i, name in enumerate(self.PRODUCT_NAMES):
            product_id = f"P{100 + i}"
            category_id = root_cats[i % len(root_cats)]
            price = round(rng.uniform(9.99, 499.99), 2)
            created_days_ago = rng.randint(1, 365)
            created_at = datetime.now(tz=timezone.utc) - timedelta(days=created_days_ago)

            self._products.append({
                "product_id": product_id,
                "product_name": name,
                "category_id": category_id,
                "price": price,
                "product_status": "active",
                "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S.000"),
            })

    def all(self) -> list[dict]:
        return list(self._products)

    def random_id(self) -> str:
        return self._rng.choice(self._products)["product_id"]

    def get_price(self, product_id: str) -> float:
        return next(
            (p["price"] for p in self._products if p["product_id"] == product_id),
            9.99,
        )


class UserPool:
    """Pre-generated user profiles with realistic demographics."""

    def __init__(self, rng: random.Random, count: int = 200, seed: int | None = None):
        self._rng = rng
        fake = Faker()
        if seed is not None:
            Faker.seed(seed)

        self._users: list[dict] = []
        cities = [
            "São Paulo", "Rio de Janeiro", "Belo Horizonte", "Curitiba", "Porto Alegre",
            "Salvador", "Brasília", "Fortaleza", "Recife", "Manaus",
            "New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
            "London", "Berlin", "Paris", "Tokyo", "Sydney",
        ]

        for i in range(count):
            user_id = f"U{1000 + i}"
            registered_days_ago = rng.randint(1, 730)
            registered_date = (datetime.now(tz=timezone.utc) - timedelta(days=registered_days_ago)).date()

            self._users.append({
                "user_id": user_id,
                "user_name": fake.name(),
                "user_email": fake.ascii_free_email(),
                "user_city": rng.choice(cities),
                "registered_date": registered_date.isoformat(),
                "user_status": "active",
            })

    def all(self) -> list[dict]:
        return list(self._users)

    def random_id(self) -> str:
        return self._rng.choice(self._users)["user_id"]
