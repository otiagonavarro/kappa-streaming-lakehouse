import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

sys.path.insert(0, "src")

from simulator.events import EventGenerator
from simulator.main import cli
from simulator.entities import CategoryPool, ProductPool, UserPool

REQUIRED_FIELDS = {"event_id", "event_type", "user_id", "session_id", "product_id", "timestamp", "metadata"}
VALID_TYPES = {"page_view", "add_to_cart", "purchase"}


class TestEventGenerator:
    def test_schema_compliance(self):
        gen = EventGenerator(seed=42)
        for _ in range(100):
            event = gen.generate()
            assert REQUIRED_FIELDS.issubset(set(event.keys())), f"Missing fields: {REQUIRED_FIELDS - set(event.keys())}"

    def test_event_types_valid(self):
        gen = EventGenerator(seed=42)
        for _ in range(100):
            assert gen.generate()["event_type"] in VALID_TYPES

    def test_all_three_types_appear(self):
        gen = EventGenerator(seed=42)
        seen = {gen.generate()["event_type"] for _ in range(500)}
        assert seen == VALID_TYPES, f"Not all event types seen: {seen}"

    def test_deterministic_with_seed(self):
        seq_a = [EventGenerator(seed=7).generate()["event_id"] for _ in range(20)]
        seq_b = [EventGenerator(seed=7).generate()["event_id"] for _ in range(20)]
        assert seq_a == seq_b

    def test_different_seeds_differ(self):
        seq_a = [EventGenerator(seed=1).generate()["event_id"] for _ in range(10)]
        seq_b = [EventGenerator(seed=2).generate()["event_id"] for _ in range(10)]
        assert seq_a != seq_b

    def test_entity_snapshots_count(self):
        gen = EventGenerator(seed=42)
        snapshots = gen.generate_entity_snapshots()
        categories = [s for s in snapshots if s["entity_type"] == "category"]
        users = [s for s in snapshots if s["entity_type"] == "user"]
        products = [s for s in snapshots if s["entity_type"] == "product"]
        assert len(categories) >= 10
        assert len(users) == 200
        assert len(products) == len(ProductPool.PRODUCT_NAMES)

    def test_entity_snapshots_have_required_fields(self):
        gen = EventGenerator(seed=42)
        snapshots = gen.generate_entity_snapshots()
        for snap in snapshots:
            assert "entity_type" in snap
            assert "timestamp" in snap
            if snap["entity_type"] == "user":
                assert "user_id" in snap
                assert "user_name" in snap
                assert "user_email" in snap
                assert "user_city" in snap
                assert "updated_at" in snap
            elif snap["entity_type"] == "product":
                assert "product_id" in snap
                assert "product_name" in snap
                assert "category_id" in snap
                assert "price" in snap
            elif snap["entity_type"] == "category":
                assert "category_id" in snap
                assert "cat_name" in snap

    def test_generate_order(self):
        gen = EventGenerator(seed=42)
        order = gen.generate_order("U1000", "P100")
        assert order["entity_type"] == "order"
        assert order["order_id"].startswith("ORD-")
        assert order["order_user_id"] == "U1000"
        assert order["order_total"] > 0
        assert order["order_status"] == "completed"
        assert "order_date" in order

    def test_generate_order_item(self):
        gen = EventGenerator(seed=42)
        item = gen.generate_order_item("ORD-000001", "P100", 3)
        assert item["entity_type"] == "order_item"
        assert item["order_item_id"].startswith("OI-")
        assert item["order_item_order_id"] == "ORD-000001"
        assert item["product_id"] == "P100"
        assert item["quantity"] == 3
        assert item["line_total"] == round(item["unit_price"] * 3, 2)


class TestCLI:
    def test_count_exits_cleanly(self):
        runner = CliRunner()
        mock_producer = MagicMock()
        mock_producer.send = MagicMock()
        mock_producer.flush = MagicMock()
        mock_producer.close = MagicMock()

        with patch("simulator.main._make_producer", return_value=mock_producer):
            result = runner.invoke(cli, ["--count", "50", "--rate", "1000", "--brokers", "localhost:9092"])

        assert result.exit_code == 0, result.output
        # At least 50 raw events + 260 entity snapshots (200 users + 50 products + 10 categories)
        assert mock_producer.send.call_count >= 50

    def test_produces_valid_json(self):
        runner = CliRunner()
        captured = []

        mock_producer = MagicMock()
        mock_producer.send = lambda topic, value: captured.append(value)
        mock_producer.flush = MagicMock()
        mock_producer.close = MagicMock()

        with patch("simulator.main._make_producer", return_value=mock_producer):
            runner.invoke(cli, ["--count", "10", "--rate", "1000", "--brokers", "localhost:9092"])

        # Should have at least 10 raw events + 260 entity snapshots
        assert len(captured) >= 10
        # Check that raw events have required fields
        raw_events = [e for e in captured if "event_id" in e]
        for event in raw_events[:10]:
            assert REQUIRED_FIELDS.issubset(set(event.keys()))
