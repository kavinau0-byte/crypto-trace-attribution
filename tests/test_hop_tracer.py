"""Unit and integration tests for tracing_engine.hop_tracer.

All mocked tests use unittest.mock.patch to replace get_transactions with
synthetic transaction data, so no real network calls are made. One live-network
test (test_trace_wallet_unresolved_live) intentionally hits mempool.space to
verify the full contract shape for an unresolved address.
"""

import unittest
from unittest.mock import patch, MagicMock

from tracing_engine.hop_tracer import trace_hops
from tracing_engine.engine import trace_wallet


def _make_tx(tx_hash, sender, destinations, timestamp=None):
    """Helper: build a synthetic normalized transaction dict.

    Matches the exact shape produced by fetcher._normalize_transaction:
    tx_hash, timestamp, inputs (list of {address, value_btc, ...}),
    outputs (list of {address, value_btc, ...}).
    """
    return {
        "tx_hash": tx_hash,
        "timestamp": timestamp,
        "confirmed": True,
        "fee_sat": 0,
        "fee_btc": 0.0,
        "inputs": [{"address": sender, "value_sat": 100000, "value_btc": 0.001,
                     "is_coinbase": False, "txid": None, "vout": 0}],
        "outputs": [
            {"address": dest, "value_sat": 50000, "value_btc": 0.0005,
             "scriptpubkey_type": "p2pkh"}
            for dest in destinations
        ],
    }


class TestHopTracerMocked(unittest.TestCase):
    """Mocked tests for trace_hops() — zero real network calls."""

    # ---- Test 1: Cycle termination (A→B→A) ----
    def test_cycle_termination(self):
        """BFS must terminate on A→B→A cycles; address A must not be re-fetched."""
        txs_a = [_make_tx("tx_a_to_b", "A", ["B"])]
        txs_b = [_make_tx("tx_b_to_a", "B", ["A"])]

        call_counts = {"A": 0, "B": 0}

        def mock_get_txs(address, session=None):
            call_counts[address] = call_counts.get(address, 0) + 1
            if address == "A":
                return txs_a
            elif address == "B":
                return txs_b
            return []

        with patch("tracing_engine.hop_tracer.get_transactions", side_effect=mock_get_txs):
            hops = trace_hops("A", max_hops=5)

        # Must terminate (test itself would hang if infinite loop)
        self.assertIsInstance(hops, list)
        # A was fetched exactly once — never re-queued after the cycle
        self.assertEqual(call_counts["A"], 1, "Address A must be fetched exactly once")
        # B was discovered and fetched exactly once
        self.assertEqual(call_counts["B"], 1, "Address B must be fetched exactly once")

    # ---- Test 2: Duplicate tx in one response (pagination overlap) ----
    def test_pagination_overlap_dedup(self):
        """Exact same tx dict appearing twice in one response must produce only one hop entry."""
        dup_tx = _make_tx("tx_dup", "A", ["B"])
        # Exact same object twice — simulates pagination overlap
        txs_a = [dup_tx, dup_tx]

        with patch("tracing_engine.hop_tracer.get_transactions", return_value=txs_a):
            hops = trace_hops("A", max_hops=2)

        b_hops = [h for h in hops if h["address"] == "B"]
        self.assertEqual(len(b_hops), 1, "Duplicate (tx_hash, dest_addr) must produce exactly 1 hop")

    # ---- Test 3: Repeat real destination — the actual fix under test ----
    def test_repeat_real_destination(self):
        """Same dest B paid by two DIFFERENT transactions must produce TWO hop entries."""
        tx1 = _make_tx("tx_first_payment", "A", ["B"])
        tx2 = _make_tx("tx_second_payment", "A", ["B"])
        txs_a = [tx1, tx2]

        with patch("tracing_engine.hop_tracer.get_transactions", return_value=txs_a):
            hops = trace_hops("A", max_hops=2)

        b_hops = [h for h in hops if h["address"] == "B"]
        self.assertEqual(len(b_hops), 2, "Two different tx_hashes paying B must produce 2 hop entries")
        tx_hashes = {h["tx_hash"] for h in b_hops}
        self.assertEqual(tx_hashes, {"tx_first_payment", "tx_second_payment"})

    # ---- Test 4: Branch cap still enforced ----
    def test_branch_cap_enforced(self):
        """Transaction with 8 outputs must record only max_branches_per_tx (5) hops."""
        destinations = [f"dest_{i}" for i in range(1, 9)]  # 8 distinct addresses
        tx_big = _make_tx("tx_big_fanout", "A", destinations)

        with patch("tracing_engine.hop_tracer.get_transactions", return_value=[tx_big]):
            hops = trace_hops("A", max_hops=1, max_branches_per_tx=5)

        self.assertEqual(len(hops), 5, "Must record exactly max_branches_per_tx=5 hops")
        # Should be the first 5 in order
        recorded_addrs = [h["address"] for h in hops]
        self.assertEqual(recorded_addrs, [f"dest_{i}" for i in range(1, 6)])

    # ---- Test 5: Mid-trace fetch exception doesn't crash ----
    def test_mid_trace_exception_resilience(self):
        """Exception fetching one address mid-trace must not crash the whole trace."""
        txs_a = [_make_tx("tx_a_out", "A", ["B", "C"])]
        txs_c = [_make_tx("tx_c_out", "C", ["D"])]

        def mock_get_txs(address, session=None):
            if address == "A":
                return txs_a
            elif address == "B":
                raise Exception("Simulated network failure for B")
            elif address == "C":
                return txs_c
            return []

        with patch("tracing_engine.hop_tracer.get_transactions", side_effect=mock_get_txs):
            hops = trace_hops("A", max_hops=3)

        self.assertIsInstance(hops, list)
        # Hops from A (B, C) and from C (D) should still be present despite B failing
        discovered_addrs = {h["address"] for h in hops}
        self.assertIn("B", discovered_addrs, "B should still be recorded as a hop even if fetching B fails later")
        self.assertIn("C", discovered_addrs, "C should be discovered from A")
        self.assertIn("D", discovered_addrs, "D should be discovered from C despite B failing")

    # ---- Test 6: Live unresolved trace_wallet contract (real network) ----
    def test_trace_wallet_unresolved_live(self):
        """LIVE NETWORK TEST: Verify trace_wallet() returns well-formed unresolved contract.

        Uses a real Bitcoin address that is NOT in data/vasp_seed_list.json and has
        some real transaction history. Intentionally hits mempool.space API.
        """
        # Genesis block coinbase address — definitely not in the VASP seed list,
        # but has real on-chain activity (receives miner tips/donations)
        unresolved_addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        result = trace_wallet(unresolved_addr, max_hops=1)

        # Full 7-key contract shape validation
        expected_keys = {
            "query_address", "chain", "hops", "matched_vasp",
            "confidence", "match_method", "risk_flags"
        }
        self.assertEqual(set(result.keys()), expected_keys)
        self.assertEqual(result["query_address"], unresolved_addr)
        self.assertEqual(result["chain"], "bitcoin")
        self.assertIsInstance(result["hops"], list)

        # Must be unresolved — this address is NOT a known VASP
        self.assertEqual(result["match_method"], "unresolved")
        self.assertIsNone(result["matched_vasp"])

        # Confidence sanity bounds
        self.assertIsInstance(result["confidence"], (int, float))
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)

        # risk_flags must be empty (owned by Person B)
        self.assertEqual(result["risk_flags"], [])


if __name__ == "__main__":
    unittest.main()
