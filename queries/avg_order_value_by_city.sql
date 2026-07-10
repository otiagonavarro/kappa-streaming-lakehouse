-- Average order value and order frequency by user city.
-- Useful for geographic segmentation analysis.

SELECT
    u.city,
    COUNT(DISTINCT o.order_id)      AS total_orders,
    COUNT(DISTINCT u.user_id)       AS unique_buyers,
    ROUND(AVG(o.total)::numeric, 2) AS avg_order_value,
    ROUND(SUM(o.total)::numeric, 2) AS total_revenue,
    ROUND(
        SUM(o.total)::numeric / NULLIF(COUNT(DISTINCT u.user_id), 0),
        2
    )                               AS revenue_per_buyer
FROM orders o
JOIN users u ON u.user_id = o.user_id
WHERE o.order_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY u.city
HAVING COUNT(DISTINCT o.order_id) >= 5
ORDER BY total_revenue DESC
LIMIT 15;
