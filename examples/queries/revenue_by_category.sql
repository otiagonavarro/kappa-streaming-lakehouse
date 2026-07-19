-- Revenue by product category (last 30 days).
-- Joins order_items → products → categories to compute revenue per category.

SELECT
    c.name                          AS category,
    COUNT(DISTINCT o.order_id)      AS total_orders,
    SUM(oi.quantity)                AS total_items_sold,
    ROUND(SUM(oi.line_total)::numeric, 2) AS total_revenue,
    ROUND(AVG(o.total)::numeric, 2)       AS avg_order_value
FROM order_items oi
JOIN orders o    ON o.order_id = oi.order_id
JOIN products p  ON p.product_id = oi.product_id
JOIN categories c ON c.category_id = p.category_id
WHERE o.order_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY c.name
ORDER BY total_revenue DESC;
