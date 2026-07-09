-- Full-dataset funnel: how many sessions had at least one page_view / add_to_cart / purchase.
-- Shows absolute drop-off at each stage and step-by-step retention rates.

WITH funnel AS (
    SELECT
        COUNT(*)                                             AS total_sessions,
        COUNT(*) FILTER (WHERE page_views > 0)              AS sessions_with_pageview,
        COUNT(*) FILTER (WHERE add_to_carts > 0)            AS sessions_with_add_to_cart,
        COUNT(*) FILTER (WHERE purchases > 0)               AS sessions_with_purchase
    FROM session_metrics
)
SELECT
    total_sessions,
    sessions_with_pageview,
    sessions_with_add_to_cart,
    sessions_with_purchase,
    ROUND(100.0 * sessions_with_add_to_cart::numeric / NULLIF(sessions_with_pageview,  0), 2) AS view_to_cart_pct,
    ROUND(100.0 * sessions_with_purchase::numeric   / NULLIF(sessions_with_add_to_cart, 0), 2) AS cart_to_purchase_pct,
    ROUND(100.0 * sessions_with_purchase::numeric   / NULLIF(sessions_with_pageview,   0), 2) AS overall_conversion_pct
FROM funnel;
