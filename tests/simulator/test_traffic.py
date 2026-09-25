import json
import random
from dataclasses import replace
from importlib import resources

import pytest
from fastavro import parse_schema
from fastavro.validation import validate
from simulator.config import SimConfig
from simulator.seed import seed_if_empty
from simulator.traffic.sessions import TrafficGenerator

SCHEMA = parse_schema(json.loads(resources.files("simulator").joinpath("schemas/clickstream_event.avsc").read_text()))


@pytest.fixture
def seeded(conn):
    seed_if_empty(conn, random.Random(1), customers=10)
    return conn


def make_traffic(conn, **cfg_overrides):
    events = []
    cfg = replace(SimConfig(invalid_event_rate=0.0), **cfg_overrides)
    return TrafficGenerator(conn, cfg, random.Random(7), events.append), events


def test_every_emitted_event_matches_the_avro_schema(seeded):
    traffic, events = make_traffic(seeded)
    for _ in range(30):
        traffic.tick(1.0)
    assert events
    for event in events:
        validate(event, SCHEMA, raise_errors=True)


def test_anonymous_session_is_stitched_and_linked_to_its_order(seeded):
    traffic, events = make_traffic(seeded, checkout_conversion=1.0)
    session = traffic.start_session(anonymous=True, will_checkout=True)
    traffic.run_to_end(session)

    mine = [e for e in events if e["session_id"] == str(session.session_id)]
    assert mine[0]["customer_id"] is None
    checkout = next(e for e in mine if e["event_type"] == "begin_checkout")
    assert checkout["customer_id"] is not None
    assert {e["anonymous_id"] for e in mine} == {str(session.anonymous_id)}

    order = seeded.execute(
        "SELECT customer_id::text FROM orders WHERE session_id = %s", (session.session_id,)
    ).fetchall()
    assert order == [(checkout["customer_id"],)]


def test_abandoned_checkout_creates_no_order(seeded):
    traffic, events = make_traffic(seeded, checkout_conversion=0.0)
    session = traffic.start_session(anonymous=False, will_checkout=True)
    traffic.run_to_end(session)

    assert any(e["event_type"] == "begin_checkout" for e in events)
    assert seeded.execute("SELECT count(*) FROM orders").fetchone()[0] == 0


def test_invalid_events_are_injected_but_still_schema_valid(seeded):
    traffic, events = make_traffic(seeded, invalid_event_rate=1.0)
    for _ in range(5):
        traffic.tick(1.0)
    assert events
    assert all(e["event_type"] not in TrafficGenerator.EVENT_TYPES or e["event_ts"] > 4102444800000 for e in events)
    for event in events:
        validate(event, SCHEMA, raise_errors=True)
