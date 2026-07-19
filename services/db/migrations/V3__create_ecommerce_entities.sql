-- E-commerce entity tables (star schema)

CREATE TABLE IF NOT EXISTS categories (
    category_id         TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    parent_category_id  TEXT REFERENCES categories(category_id)
);

CREATE TABLE IF NOT EXISTS users (
    user_id          TEXT        PRIMARY KEY,
    name             TEXT        NOT NULL,
    email            TEXT        NOT NULL,
    city             TEXT        NOT NULL,
    registered_date  DATE        NOT NULL,
    status           TEXT        NOT NULL DEFAULT 'active',
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_city ON users (city);
CREATE INDEX IF NOT EXISTS idx_users_status ON users (status);
CREATE INDEX IF NOT EXISTS idx_users_registered_date ON users (registered_date);

CREATE TABLE IF NOT EXISTS products (
    product_id    TEXT           PRIMARY KEY,
    name          TEXT           NOT NULL,
    category_id   TEXT           NOT NULL REFERENCES categories(category_id),
    price         NUMERIC(10,2)  NOT NULL,
    status        TEXT           NOT NULL DEFAULT 'active',
    created_at    TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products (category_id);
CREATE INDEX IF NOT EXISTS idx_products_status ON products (status);

CREATE TABLE IF NOT EXISTS orders (
    order_id    TEXT           PRIMARY KEY,
    user_id     TEXT           NOT NULL REFERENCES users(user_id),
    total       NUMERIC(10,2)  NOT NULL,
    status      TEXT           NOT NULL DEFAULT 'completed',
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    order_date  DATE           NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders (user_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_date ON orders (order_date);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id  TEXT           PRIMARY KEY,
    order_id       TEXT           NOT NULL REFERENCES orders(order_id),
    product_id     TEXT           NOT NULL REFERENCES products(product_id),
    quantity       INT            NOT NULL,
    unit_price     NUMERIC(10,2)  NOT NULL,
    line_total     NUMERIC(10,2)  NOT NULL,
    order_date     DATE           NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items (order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items (product_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order_date ON order_items (order_date);
