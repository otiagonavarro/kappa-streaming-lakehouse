-- Top 10 products by conversion rate in the last 24 hours.
-- Conversion rate = purchases / page_views (requires at least 10 page views to filter noise).

SELECT
    product_id,
    SUM(page_views)   AS total_page_views,
    SUM(add_to_carts) AS total_add_to_carts,
    SUM(purchases)    AS total_purchases,
    ROUND(
        100.0 * SUM(purchases)::numeric / NULLIF(SUM(page_views), 0),
        2
    )                 AS conversion_rate_pct,
    ROUND(
        100.0 * SUM(add_to_carts)::numeric / NULLIF(SUM(page_views), 0),
        2
    )                 AS add_to_cart_rate_pct
FROM product_funnel_1m
WHERE window_start >= NOW() - INTERVAL '24 hours'
GROUP BY product_id
HAVING SUM(page_views) >= 10
ORDER BY conversion_rate_pct DESC
LIMIT 10;
