-- OLTP schema of the shop application: the single source of truth for
-- transactional entities. Changes are captured from the WAL by Debezium
-- (ADR-0012); nothing analytical lives in this database.

CREATE TABLE customers (
    customer_id  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name    TEXT,
    email        TEXT,
    phone        TEXT,
    document     TEXT,
    status       TEXT        NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active', 'inactive', 'deleted')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- PII is nulled on erasure (forget_customer), so it is required only while not deleted
    CHECK (status = 'deleted' OR (full_name IS NOT NULL AND email IS NOT NULL))
);

CREATE UNIQUE INDEX customers_email_uq ON customers (lower(email)) WHERE email IS NOT NULL;

CREATE TABLE addresses (
    address_id   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id  UUID        NOT NULL REFERENCES customers (customer_id),
    street       TEXT,
    number       TEXT,
    city         TEXT        NOT NULL,
    state        TEXT        NOT NULL,
    zip_code     TEXT,
    is_primary   BOOLEAN     NOT NULL DEFAULT false,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX addresses_customer_idx ON addresses (customer_id);
CREATE UNIQUE INDEX addresses_one_primary_uq ON addresses (customer_id) WHERE is_primary;

CREATE TABLE categories (
    category_id  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name         TEXT        NOT NULL,
    parent_id    UUID        REFERENCES categories (category_id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (parent_id, name)
);

CREATE TABLE products (
    product_id   UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    sku          TEXT          NOT NULL UNIQUE,
    name         TEXT          NOT NULL,
    category_id  UUID          NOT NULL REFERENCES categories (category_id),
    price        NUMERIC(10,2) NOT NULL CHECK (price > 0),
    status       TEXT          NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active', 'discontinued')),
    created_at   TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX products_category_idx ON products (category_id);

CREATE TABLE inventory (
    product_id   UUID        PRIMARY KEY REFERENCES products (product_id),
    quantity     INT         NOT NULL CHECK (quantity >= 0),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE orders (
    order_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id   UUID          NOT NULL REFERENCES customers (customer_id),
    session_id    UUID,
    status        TEXT          NOT NULL DEFAULT 'created'
                  CHECK (status IN ('created', 'paid', 'shipped', 'delivered', 'cancelled', 'refunded')),
    total         NUMERIC(12,2) NOT NULL CHECK (total >= 0),
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    paid_at       TIMESTAMPTZ,
    shipped_at    TIMESTAMPTZ,
    delivered_at  TIMESTAMPTZ,
    cancelled_at  TIMESTAMPTZ,
    refunded_at   TIMESTAMPTZ,
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX orders_customer_idx ON orders (customer_id);
CREATE INDEX orders_status_idx   ON orders (status, updated_at);

CREATE TABLE order_items (
    order_item_id  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id       UUID          NOT NULL REFERENCES orders (order_id),
    product_id     UUID          NOT NULL REFERENCES products (product_id),
    quantity       INT           NOT NULL CHECK (quantity > 0),
    unit_price     NUMERIC(10,2) NOT NULL CHECK (unit_price > 0),
    line_total     NUMERIC(12,2) NOT NULL CHECK (line_total >= 0)
);

CREATE INDEX order_items_order_idx ON order_items (order_id);

CREATE TABLE payments (
    payment_id  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id    UUID          NOT NULL REFERENCES orders (order_id),
    attempt     INT           NOT NULL CHECK (attempt > 0),
    method      TEXT          NOT NULL CHECK (method IN ('credit_card', 'pix', 'boleto')),
    amount      NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    status      TEXT          NOT NULL CHECK (status IN ('approved', 'declined')),
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (order_id, attempt)
);

CREATE TABLE shipments (
    shipment_id    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id       UUID        NOT NULL UNIQUE REFERENCES orders (order_id),
    carrier        TEXT        NOT NULL,
    tracking_code  TEXT        NOT NULL,
    shipped_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at   TIMESTAMPTZ
);

-- ── CDC ──────────────────────────────────────────────────────────────────────
-- REPLICA IDENTITY DEFAULT (primary key only in `before`) is Postgres' default;
-- it is stated explicitly because downstream relies on it (ADR-0012).
ALTER TABLE customers   REPLICA IDENTITY DEFAULT;
ALTER TABLE addresses   REPLICA IDENTITY DEFAULT;
ALTER TABLE categories  REPLICA IDENTITY DEFAULT;
ALTER TABLE products    REPLICA IDENTITY DEFAULT;
ALTER TABLE inventory   REPLICA IDENTITY DEFAULT;
ALTER TABLE orders      REPLICA IDENTITY DEFAULT;
ALTER TABLE order_items REPLICA IDENTITY DEFAULT;
ALTER TABLE payments    REPLICA IDENTITY DEFAULT;
ALTER TABLE shipments   REPLICA IDENTITY DEFAULT;

CREATE PUBLICATION shop_pub FOR TABLE
    customers, addresses, categories, products, inventory,
    orders, order_items, payments, shipments;

-- Dedicated, least-privilege user for Debezium: replication + read-only snapshot.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${debezium_user}') THEN
        CREATE ROLE ${debezium_user} WITH LOGIN REPLICATION PASSWORD '${debezium_password}';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO ${debezium_user};
GRANT SELECT ON
    customers, addresses, categories, products, inventory,
    orders, order_items, payments, shipments
TO ${debezium_user};
