"""Simulation knobs. Business delays are in simulated days; TIME_SCALE maps one day to real seconds."""
import os
from dataclasses import dataclass, fields
from datetime import timedelta


@dataclass(frozen=True)
class SimConfig:
    seconds_per_day: float = 60.0  # TIME_SCALE
    # Order lifecycle delays (simulated days)
    pay_after_days: float = 0.05
    ship_after_days: float = 1.0
    deliver_after_days: float = 3.0
    refund_after_days: float = 2.0
    refund_window_days: float = 7.0
    # Probabilities
    payment_decline_rate: float = 0.05
    max_payment_attempts: int = 3
    cancel_rate: float = 0.03
    refund_rate: float = 0.02
    checkout_conversion: float = 0.70
    anonymous_session_rate: float = 0.30
    invalid_event_rate: float = 0.005
    # Traffic and catalog upkeep
    sessions_per_second: float = 2.0
    low_stock_threshold: int = 10
    restock_quantity: int = 100

    def delay(self, days: float) -> timedelta:
        return timedelta(seconds=days * self.seconds_per_day)

    @classmethod
    def from_env(cls, **overrides) -> "SimConfig":
        """Each field can be set as SIM_<FIELD_NAME>; SIM_SECONDS_PER_DAY is also accepted as TIME_SCALE."""
        values = {}
        for f in fields(cls):
            raw = os.environ.get(f"SIM_{f.name.upper()}")
            if f.name == "seconds_per_day":
                raw = os.environ.get("TIME_SCALE", raw)
            if raw is not None:
                values[f.name] = type(f.default)(raw)
        values |= {k: v for k, v in overrides.items() if v is not None}
        return cls(**values)
