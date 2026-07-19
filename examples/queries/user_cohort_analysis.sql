-- User cohort analysis: average order value by user registration month.
-- Shows whether newer cohorts have higher or lower spending patterns.

SELECT
    DATE_TRUNC('month', u.registered_date)::date AS cohort_month,
    COUNT(DISTINCT u.user_id)                    AS cohort_size,
    COUNT(DISTINCT o.order_id)                   AS total_orders,
    ROUND(AVG(o.total)::numeric, 2)              AS avg_order_value,
    ROUND(SUM(o.total)::numeric, 2)              AS total_revenue,
    ROUND(
        SUM(o.total)::numeric / NULLIF(COUNT(DISTINCT u.user_id), 0),
        2
    )                                            AS revenue_per_user
FROM users u
JOIN orders o ON o.user_id = u.user_id
WHERE u.registered_date >= CURRENT_DATE - INTERVAL '365 days'
GROUP BY DATE_TRUNC('month', u.registered_date)
ORDER BY cohort_month DESC;
