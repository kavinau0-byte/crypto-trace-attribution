"""Unit tests for the Elliptic graph adapter (Task 7 Component)."""

import unittest
from unittest.mock import patch

from benchmarks.elliptic_adapter import EllipticGraphAdapter
from tracing_engine.hop_tracer import trace_hops


class TestEllipticAdapter(unittest.TestCase):
    """Test suite verifying adapter contract conformity, transaction batching, and branch limits."""

    def setUp(self):
        # Construct a known small test graph:
        # A -> B, A -> C
        # B -> D
        # C -> D, C -> E
        # D -> E
        # E is a pure sink (no outgoing edges)
        # HighFanout -> out_1, out_2, ..., out_8 (8 outgoing edges to test max_branches_per_tx cap)
        self.test_adj = {
            "node_A": ["node_B", "node_C"],
            "node_B": ["node_D"],
            "node_C": ["node_D", "node_E"],
            "node_D": ["node_E"],
            "node_E": [],  # pure sink / destination only
            "node_HighFanout": [f"out_dest_{i}" for i in range(1, 9)],  # 8 outgoing edges
        }
        self.adapter = EllipticGraphAdapter(adjacency_dict=self.test_adj)

    def test_synthesized_transaction_shape_and_fields(self):
        """Verify single batched transaction dictionary format per source node with all outputs."""
        txs = self.adapter.get_transactions("node_A")
        self.assertIsInstance(txs, list)
        self.assertEqual(len(txs), 1, "Must return exactly one transaction containing all outputs")

        tx_a = txs[0]
        self.assertEqual(tx_a["tx_hash"], "elliptic_node_tx::node_A")
        self.assertIsNone(tx_a["timestamp"], "Elliptic timestamps must remain None (no fabrication)")
        self.assertEqual(tx_a["inputs"], [{"address": "node_A"}])
        self.assertEqual(
            tx_a["outputs"],
            [
                {"address": "node_B", "value_btc": 0.0},
                {"address": "node_C", "value_btc": 0.0},
            ],
        )

    def test_node_with_zero_outgoing_edges(self):
        """Verify nodes with zero outgoing edges return empty list []."""
        txs = self.adapter.get_transactions("node_E")
        self.assertEqual(txs, [])

    def test_destination_only_sink_node(self):
        """Verify a node appearing only as a destination and never as a source returns []."""
        self.assertIn("node_E", self.adapter.all_nodes)
        self.assertNotIn("node_E", self.adapter.source_nodes)
        self.assertEqual(self.adapter.get_transactions("node_E"), [])

    def test_nonexistent_and_empty_nodes(self):
        """Verify non-existent, empty, or whitespace addresses return empty list gracefully."""
        self.assertEqual(self.adapter.get_transactions("non_existent_node_xyz"), [])
        self.assertEqual(self.adapter.get_transactions(""), [])
        self.assertEqual(self.adapter.get_transactions("   "), [])
        self.assertEqual(self.adapter.get_transactions(None), [])

    def test_trace_hops_integration_with_adapter(self):
        """Verify real, unmodified trace_hops() traverses correctly using batched adapter."""
        with patch("tracing_engine.hop_tracer.get_transactions", side_effect=self.adapter.get_transactions):
            # Trace from node_A with max_hops=1 (only immediate neighbors)
            hops_1 = trace_hops(seed_address="node_A", max_hops=1)
            self.assertEqual(len(hops_1), 2)
            dest_addrs_1 = {h["address"] for h in hops_1}
            self.assertEqual(dest_addrs_1, {"node_B", "node_C"})
            for h in hops_1:
                self.assertEqual(h["hop_index"], 0)
                self.assertEqual(h["tx_hash"], "elliptic_node_tx::node_A")

            # Trace from node_A with max_hops=2
            # Hop 0: node_B, node_C
            # Hop 1: node_D, node_E
            hops_2 = trace_hops(seed_address="node_A", max_hops=2)
            dest_addrs_2 = {h["address"] for h in hops_2}
            self.assertEqual(dest_addrs_2, {"node_B", "node_C", "node_D", "node_E"})
            # node_D receives two GENUINELY SEPARATE real edges: node_B -> node_D
            # (tx elliptic_node_tx::node_B) and node_C -> node_D (tx
            # elliptic_node_tx::node_C). The ancestor-aware dedup fix correctly
            # records both as distinct hops (different tx_hash), so total hop
            # count is 5, not 4 unique destinations.
            self.assertEqual(len(hops_2), 5)

            hop_0_addrs = {h["address"] for h in hops_2 if h["hop_index"] == 0}
            hop_1_addrs = {h["address"] for h in hops_2 if h["hop_index"] == 1}
            self.assertEqual(hop_0_addrs, {"node_B", "node_C"})
            self.assertEqual(hop_1_addrs, {"node_D", "node_E"})

            # Confirm node_D specifically appears twice at hop 1 (once per
            # real incoming transaction), not collapsed into one entry.
            hop_1_dest_d_count = sum(
                1 for h in hops_2 if h["hop_index"] == 1 and h["address"] == "node_D"
            )
            self.assertEqual(hop_1_dest_d_count, 2)

    def test_trace_hops_from_sink_node(self):
        """Verify trace_hops() on a pure sink node returns empty hop list []."""
        with patch("tracing_engine.hop_tracer.get_transactions", side_effect=self.adapter.get_transactions):
            hops = trace_hops(seed_address="node_E", max_hops=4)
            self.assertEqual(hops, [])

    def test_max_branches_per_tx_cap_enforced(self):
        """Verify trace_hops() properly stops after max_branches_per_tx outputs on high-fanout node.

        This test verifies the fix to the bug where 1-output-per-edge adapter synthesis prevented
        branches_count from ever reaching max_branches_per_tx (5).
        """
        with patch("tracing_engine.hop_tracer.get_transactions", side_effect=self.adapter.get_transactions):
            # node_HighFanout has 8 outgoing edges (out_dest_1 ... out_dest_8)
            # With max_branches_per_tx=5, only the first 5 branches should be traversed
            hops_capped = trace_hops(
                seed_address="node_HighFanout",
                max_hops=1,
                max_branches_per_tx=5,
            )
            self.assertEqual(
                len(hops_capped),
                5,
                "trace_hops must cap exploration at exactly max_branches_per_tx=5 outputs",
            )
            discovered_addresses = [h["address"] for h in hops_capped]
            expected_addresses = [f"out_dest_{i}" for i in range(1, 6)]
            self.assertEqual(discovered_addresses, expected_addresses)
            self.assertNotIn("out_dest_6", discovered_addresses)
            self.assertNotIn("out_dest_7", discovered_addresses)
            self.assertNotIn("out_dest_8", discovered_addresses)

            # If cap is raised to 8, all 8 destinations should be discovered
            hops_uncapped = trace_hops(
                seed_address="node_HighFanout",
                max_hops=1,
                max_branches_per_tx=8,
            )
            self.assertEqual(len(hops_uncapped), 8)


if __name__ == "__main__":
    unittest.main()
