CREATE TABLE IF NOT EXISTS product_funnel_1m (
    product_id   TEXT        NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end   TIMESTAMPTZ NOT NULL,
    page_views   BIGINT      NOT NULL DEFAULT 0,
    add_to_carts BIGINT      NOT NULL DEFAULT 0,
    purchases    BIGINT      NOT NULL DEFAULT 0,
    PRIMARY KEY (product_id, window_start)
);

CREATE INDEX IF NOT EXISTS idx_product_funnel_window ON product_funnel_1m (window_start);
CREATE INDEX IF NOT EXISTS idx_product_funnel_product ON product_funnel_1m (product_id, window_start DESC);
