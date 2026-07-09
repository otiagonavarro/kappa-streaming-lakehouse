CREATE TABLE IF NOT EXISTS session_metrics (
    session_id       TEXT        PRIMARY KEY,
    user_id          TEXT        NOT NULL,
    session_date     DATE        NOT NULL,
    session_start    TIMESTAMPTZ NOT NULL,
    session_end      TIMESTAMPTZ,
    session_duration_seconds BIGINT,
    event_count      INT         NOT NULL DEFAULT 0,
    page_views       INT         NOT NULL DEFAULT 0,
    add_to_carts     INT         NOT NULL DEFAULT 0,
    purchases        INT         NOT NULL DEFAULT 0,
    converted        BOOLEAN     NOT NULL DEFAULT FALSE,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_session_metrics_user_id    ON session_metrics (user_id);
CREATE INDEX IF NOT EXISTS idx_session_metrics_session_date ON session_metrics (session_date);
CREATE INDEX IF NOT EXISTS idx_session_metrics_converted  ON session_metrics (converted);
