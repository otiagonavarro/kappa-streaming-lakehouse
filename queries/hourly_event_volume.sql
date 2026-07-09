-- Event counts per hour per event type, derived from session_metrics.
-- Useful for spotting traffic spikes and off-peak patterns.

SELECT
    DATE_TRUNC('hour', session_start)                         AS hour_bucket,
    SUM(page_views)                                           AS page_views,
    SUM(add_to_carts)                                         AS add_to_carts,
    SUM(purchases)                                            AS purchases,
    SUM(page_views) + SUM(add_to_carts) + SUM(purchases)     AS total_events,
    COUNT(DISTINCT session_id)                                AS unique_sessions
FROM session_metrics
WHERE session_start IS NOT NULL
GROUP BY DATE_TRUNC('hour', session_start)
ORDER BY hour_bucket DESC
LIMIT 48;
