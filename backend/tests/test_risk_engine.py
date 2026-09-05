"""Unit tests for backend.app.risk_engine.

Focus: unconfirmed transactions. mempool.space reports `timestamp: None` for a
transaction that is still pending, and `tracing_engine/schema.py` declares
`HopInfo.timestamp` as `Optional[str]` accordingly. That is normal, expected
data — not a data error — so neither `_parse_ts` nor `compute_risk_flags` may
raise on it.

These tests are entirely synthetic: they build hop dicts directly rather than
tracing a live address, because whether any given address has a pending
transaction changes minute to minute as blocks are mined.
"""

import unittest

from backend.app.risk_engine import (
    _parse_ts,
    compute_risk_flags,
    RAPID_HOP_SECONDS,
)


def _hop(hop_index, address, timestamp, tx_hash=None, amount_btc=0.001):
    """Build a synthetic hop dict matching the TraceResult contract shape."""
    return {
        "hop_index": hop_index,
        "address": address,
        "tx_hash": tx_hash or f"tx_{hop_index}_{address}",
        "timestamp": timestamp,
        "amount_btc": amount_btc,
    }


class TestParseTs(unittest.TestCase):
    """_parse_ts must absorb a missing timestamp instead of crashing on it."""

    def test_none_timestamp_returns_none(self):
        """The regression: `.replace()` on None raised AttributeError."""
        self.assertIsNone(_parse_ts(None))

    def test_empty_timestamp_returns_none(self):
        self.assertIsNone(_parse_ts(""))

    def test_valid_timestamp_still_parses(self):
        parsed = _parse_ts("2026-09-01T10:08:32Z")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.year, 2026)
        self.assertEqual(parsed.minute, 8)
        self.assertEqual(parsed.second, 32)


class TestComputeRiskFlagsUnconfirmed(unittest.TestCase):
    """compute_risk_flags must survive unconfirmed hops anywhere in the trace."""

    def test_single_none_timestamp_does_not_raise(self):
        """One pending hop among confirmed ones — the live 500 scenario."""
        hops = [
            _hop(0, "A", "2026-09-01T10:00:00Z"),
            _hop(1, "B", None),
            _hop(2, "C", "2026-09-01T10:30:00Z"),
        ]
        flags = compute_risk_flags(hops)
        self.assertIsInstance(flags, list)

    def test_all_none_timestamps_does_not_raise(self):
        """Every hop pending: no time signal at all, but still no crash."""
        hops = [_hop(i, chr(ord("A") + i), None) for i in range(4)]
        flags = compute_risk_flags(hops)
        self.assertIsInstance(flags, list)
        self.assertNotIn("rapid_hopping", flags)

    def test_missing_timestamp_key_does_not_raise(self):
        """A hop dict lacking the key entirely is still handled (KeyError path)."""
        hops = [
            {"hop_index": 0, "address": "A", "tx_hash": "t0", "amount_btc": 0.1},
            {"hop_index": 1, "address": "B", "tx_hash": "t1", "amount_btc": 0.1},
        ]
        self.assertIsInstance(compute_risk_flags(hops), list)

    def test_unconfirmed_hop_contributes_no_time_signal(self):
        """A pending hop is skipped for rapid_hopping, not counted either way.

        Both surviving gaps (A->B is skipped, B->C is skipped) leave only the
        C->D gap, which is deliberately slow — so rapid_hopping must not fire
        even though the pending hop sits between fast neighbours.
        """
        slow = 3 * RAPID_HOP_SECONDS
        hops = [
            _hop(0, "A", "2026-09-01T10:00:00Z"),
            _hop(1, "B", None),
            _hop(2, "C", "2026-09-01T10:00:10Z"),
            _hop(3, "D", "2026-09-01T12:00:00Z"),
        ]
        flags = compute_risk_flags(hops)
        self.assertNotIn("rapid_hopping", flags)
        self.assertGreater(slow, RAPID_HOP_SECONDS)  # sanity on the fixture

    def test_no_unconfirmed_risk_flag_is_invented(self):
        """A pending hop must not introduce a new flag category.

        The documented flag vocabulary is rapid_hopping / high_fanout /
        possible_mixer. Skipping a pending hop is a graceful omission, not a
        new signal — this test pins that decision.
        """
        hops = [
            _hop(0, "A", "2026-09-01T10:00:00Z"),
            _hop(1, "B", None),
        ]
        known = {"rapid_hopping", "high_fanout", "possible_mixer"}
        self.assertTrue(set(compute_risk_flags(hops)).issubset(known))


class TestComputeRiskFlagsUnchangedBehaviour(unittest.TestCase):
    """Confirmed-only traces must behave exactly as before the fix."""

    def test_rapid_hopping_still_detected(self):
        hops = [
            _hop(0, "A", "2026-09-01T10:00:00Z"),
            _hop(1, "B", "2026-09-01T10:01:00Z"),
            _hop(2, "C", "2026-09-01T10:02:00Z"),
        ]
        self.assertIn("rapid_hopping", compute_risk_flags(hops))

    def test_slow_hops_not_flagged_rapid(self):
        hops = [
            _hop(0, "A", "2026-09-01T10:00:00Z"),
            _hop(1, "B", "2026-09-01T14:00:00Z"),
            _hop(2, "C", "2026-09-01T20:00:00Z"),
        ]
        self.assertNotIn("rapid_hopping", compute_risk_flags(hops))

    def test_high_fanout_still_detected(self):
        hops = [
            _hop(0, "A", "2026-09-01T10:00:00Z"),
            _hop(0, "B", "2026-09-01T10:00:00Z"),
            _hop(0, "C", "2026-09-01T10:00:00Z"),
        ]
        self.assertIn("high_fanout", compute_risk_flags(hops))

    def test_high_fanout_detected_even_when_hops_unconfirmed(self):
        """Fan-out is address-based, so pending hops must not suppress it."""
        hops = [
            _hop(0, "A", None),
            _hop(0, "B", None),
            _hop(0, "C", None),
        ]
        self.assertIn("high_fanout", compute_risk_flags(hops))

    def test_empty_hops_returns_empty(self):
        self.assertEqual(compute_risk_flags([]), [])


class TestHopSchemaAcceptsNullTimestamp(unittest.TestCase):
    """The pydantic layer must not reject what the engine legitimately emits."""

    def test_hop_accepts_none_timestamp(self):
        from backend.app.schemas import Hop

        hop = Hop(
            hop_index=1,
            address="bc1qexample",
            tx_hash="abc123",
            timestamp=None,
            amount_btc=0.5,
        )
        self.assertIsNone(hop.timestamp)

    def test_hop_still_accepts_a_real_timestamp(self):
        from backend.app.schemas import Hop

        hop = Hop(
            hop_index=0,
            address="bc1qexample",
            tx_hash="abc123",
            timestamp="2026-09-01T10:08:32Z",
            amount_btc=0.5,
        )
        self.assertEqual(hop.timestamp, "2026-09-01T10:08:32Z")


if __name__ == "__main__":
    unittest.main()
