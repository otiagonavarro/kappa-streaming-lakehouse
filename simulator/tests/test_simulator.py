import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

sys.path.insert(0, "src")

from simulator.events import EventGenerator
from simulator.main import cli

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
        assert mock_producer.send.call_count == 50

    def test_produces_valid_json(self):
        runner = CliRunner()
        captured = []

        mock_producer = MagicMock()
        mock_producer.send = lambda topic, value: captured.append(value)
        mock_producer.flush = MagicMock()
        mock_producer.close = MagicMock()

        with patch("simulator.main._make_producer", return_value=mock_producer):
            runner.invoke(cli, ["--count", "10", "--rate", "1000", "--brokers", "localhost:9092"])

        assert len(captured) == 10
        for event in captured:
            assert REQUIRED_FIELDS.issubset(set(event.keys()))
