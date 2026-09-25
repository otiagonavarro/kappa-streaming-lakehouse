"""First-boot catalog and customer base, created through the same use cases as live traffic,
so every row reaches the WAL as an ordinary insert."""
import random
from decimal import Decimal

import psycopg  # pyright: ignore[reportMissingImports]
from faker import Faker

from .usecases import catalog, customers
from .usecases.customers import AddressInput

CATEGORIES = {
    "Electronics": ["Smartphones", "Laptops", "Audio"],
    "Books": ["Fiction", "Non-Fiction", "Technical"],
    "Clothing": ["Men", "Women", "Kids"],
    "Home & Kitchen": ["Kitchenware", "Appliances", "Decor"],
    "Sports & Outdoors": ["Gym Equipment", "Camping", "Team Sports"],
}

PRODUCTS = {
    "Audio": ["Wireless Bluetooth Headphones", "Noise Cancelling Earbuds", "Bluetooth Speaker Mini", "Monitor Light Bar"],
    "Smartphones": ["Phone Case Premium", "Screen Protector Pack", "Wireless Charger Pad", "Power Bank 20000mAh",
                    "USB-C Charging Cable 6ft"],
    "Laptops": ["Mechanical Keyboard RGB", "Ergonomic Mouse Pad", "4K Webcam HD", "Portable SSD 1TB",
                "Laptop Stand Adjustable", "HDMI Cable 4K 10ft", "Smart Watch Fitness"],
    "Technical": ["Java Programming Handbook", "Data Engineering Guide", "Python Cookbook 3rd Ed",
                  "System Design Interview", "Clean Architecture Manual", "SQL Deep Dive", "Kubernetes in Action",
                  "Flink Stream Processing", "Cloud Native Patterns", "Machine Learning Ops"],
    "Fiction": ["Dom Casmurro", "Grande Sertão: Veredas", "O Cortiço"],
    "Men": ["Cotton T-Shirt Classic", "Denim Jacket Vintage", "Wool Sweater Premium", "Baseball Cap Classic"],
    "Women": ["Yoga Pants Flex", "Rain Jacket Lightweight", "Running Shoes Pro"],
    "Kids": ["Hiking Boots Waterproof", "Swim Goggles Pro"],
    "Appliances": ["Coffee Maker Programmable", "Blender High Speed", "Air Fryer XL", "Espresso Machine Compact"],
    "Decor": ["LED Desk Lamp", "Desk Organizer Wood", "Cable Management Kit"],
    "Kitchenware": ["Cast Iron Skillet 12in", "French Oven 6Qt", "Knife Set 8pc", "Bamboo Cutting Board",
                  "Insulated Tumbler 30oz", "Silicone Baking Mat"],
    "Gym Equipment": ["Yoga Mat Premium", "Resistance Bands Set", "Dumbbells Adjustable", "Foam Roller Recovery",
                      "Jump Rope Speed"],
    "Camping": ["Camping Tent 4-Person", "Sleeping Bag Ultralight", "Hiking Backpack 40L"],
    "Team Sports": ["Soccer Ball Official", "Tennis Racket Carbon", "Cycling Jersey Aero"],
}

# Real cities, weighted roughly by population, so geography dimensions look plausible.
CITIES = [
    ("São Paulo", "SP", 12), ("Rio de Janeiro", "RJ", 7), ("Belo Horizonte", "MG", 3), ("Brasília", "DF", 3),
    ("Salvador", "BA", 3), ("Fortaleza", "CE", 3), ("Curitiba", "PR", 2), ("Recife", "PE", 2),
    ("Porto Alegre", "RS", 2), ("Manaus", "AM", 2), ("Campinas", "SP", 1), ("Florianópolis", "SC", 1),
]


def seed_if_empty(conn: psycopg.Connection, rng: random.Random, customers: int = 200) -> bool:
    """Seed catalog and customers in one transaction. Returns False when data already exists."""
    if conn.execute("SELECT EXISTS (SELECT 1 FROM categories)").fetchone()[0]:
        return False
    fake = new_faker(rng)
    with conn.transaction():
        sub_ids = {}
        for root, subs in CATEGORIES.items():
            root_id = catalog.create_category(conn, root)
            for sub in subs:
                sub_ids[sub] = catalog.create_category(conn, sub, root_id)
        n = 0
        for sub, names in PRODUCTS.items():
            for name in names:
                n += 1
                catalog.create_product(
                    conn,
                    sku=f"SKU-{n:05d}",
                    name=name,
                    category_id=sub_ids[sub],
                    price=Decimal(str(round(rng.uniform(9.99, 499.99), 2))),
                    initial_stock=rng.randint(80, 300),
                )
        for _ in range(customers):
            register_random_customer(conn, fake, rng)
    return True


def new_faker(rng: random.Random) -> Faker:
    fake = Faker("pt_BR")
    fake.seed_instance(rng.random())
    return fake


def random_address(fake: Faker, rng: random.Random) -> AddressInput:
    city, state, _ = rng.choices(CITIES, weights=[w for *_, w in CITIES])[0]
    return AddressInput(
        street=fake.street_name(), number=fake.building_number(), city=city, state=state, zip_code=fake.postcode()
    )


def register_random_customer(conn: psycopg.Connection, fake: Faker, rng: random.Random):
    name = fake.name()
    return customers.register_customer(
        conn,
        full_name=name,
        email=f"{fake.user_name()}.{rng.randrange(10**6):06d}@{fake.free_email_domain()}",
        phone=fake.cellphone_number(),
        document=fake.cpf(),
        address=random_address(fake, rng),
    )
