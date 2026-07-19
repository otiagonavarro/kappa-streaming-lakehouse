import click
from common import build_env
from contracts.loader import ddl_columns


@click.command()
@click.option("--from-beginning", is_flag=True, default=False, help="Reset consumer group to earliest offset")
def main(from_beginning: bool):
    env, t_env = build_env()

    t_env.execute_sql(f"""
        CREATE TABLE IF NOT EXISTS gold.user_360 (
            {ddl_columns("gold", "user_360")}
        ) WITH (
            'format-version' = '2',
            'write.format.default' = 'parquet',
            'write.parquet.compression-codec' = 'snappy'
        )
    """)

    t_env.execute_sql("""
        INSERT INTO gold.user_360
        SELECT
            user_id,
            COUNT(*) AS total_sessions,
            SUM(event_count) AS total_events,
            SUM(page_views) AS total_page_views,
            SUM(add_to_carts) AS total_add_to_carts,
            SUM(purchases) AS total_purchases,
            AVG(session_duration_seconds) AS avg_session_duration_seconds,
            MIN(session_date) AS first_activity_date,
            MAX(session_date) AS last_activity_date,
            MAX(converted) AS is_converted
        FROM gold.session_metrics
        GROUP BY user_id
    """)

    print("User 360 aggregation pipeline running.")


if __name__ == "__main__":
    main()
