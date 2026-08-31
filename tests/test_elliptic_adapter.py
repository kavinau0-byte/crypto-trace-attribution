"""Unit tests for the Elliptic graph adapter (Task 7 Component)."""

import unittest
from unittest.mock import patch

from benchmarks.elliptic_adapter import EllipticGraphAdapter
from tracing_engine.hop_tracer import trace_hops


class TestEllipticAdapter(unittest.TestCase):
    """Test suite verifying adapter contract conformity and graph translation."""

    def setUp(self):
        # Construct a known small test graph:
        # A -> B, A -> C
        # B -> D
        # C -> D, C -> E
        # D -> E
        # E is a pure sink (no outgoing edges)
        # F is a disconnected singleton
        self.test_adj = {
            "node_A": ["node_B", "node_C"],
            "node_B": ["node_D"],
            "node_C": ["node_D", "node_E"],
            "node_D": ["node_E"],
            "node_E": [],  # pure sink / destination only
        }
        self.adapter = EllipticGraphAdapter(adjacency_dict=self.test_adj)

    def test_synthesized_transaction_shape_and_fields(self):
        """Verify transaction dictionary format conforms strictly to fetcher specification."""
        txs = self.adapter.get_transactions("node_A")
        self.assertIsInstance(txs, list)
        self.assertEqual(len(txs), 2, "node_A has 2 outgoing edges")

        # Validate first edge (node_A -> node_B)
        tx_b = txs[0]
        self.assertEqual(tx_b["tx_hash"], "elliptic_edge::node_A->node_B")
        self.assertIsNone(tx_b["timestamp"], "Elliptic timestamps must remain None (no fabrication)")
        self.assertEqual(tx_b["inputs"], [{"address": "node_A"}])
        self.assertEqual(tx_b["outputs"], [{"address": "node_B", "value_btc": 0.0}])

        # Validate second edge (node_A -> node_C)
        tx_c = txs[1]
        self.assertEqual(tx_c["tx_hash"], "elliptic_edge::node_A->node_C")
        self.assertIsNone(tx_c["timestamp"])
        self.assertEqual(tx_c["inputs"], [{"address": "node_A"}])
        self.assertEqual(tx_c["outputs"], [{"address": "node_C", "value_btc": 0.0}])

    def test_node_with_zero_outgoing_edges(self):
        """Verify nodes with zero outgoing edges return empty list []."""
        txs = self.adapter.get_transactions("node_E")
        self.assertEqual(txs, [])

    def test_destination_only_sink_node(self):
        """Verify a node appearing only as a destination and never as a source returns []."""
        # "node_E" is in the graph as a destination but has 0 outgoing edges
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
        """Verify real, unmodified trace_hops() traverses correctly using monkeypatched adapter."""
        with patch("tracing_engine.hop_tracer.get_transactions", side_effect=self.adapter.get_transactions):
            # Trace from node_A with max_hops=1 (only immediate neighbors)
            hops_1 = trace_hops(seed_address="node_A", max_hops=1)
            self.assertEqual(len(hops_1), 2)
            dest_addrs_1 = {h["address"] for h in hops_1}
            self.assertEqual(dest_addrs_1, {"node_B", "node_C"})
            for h in hops_1:
                self.assertEqual(h["hop_index"], 0)

            # Trace from node_A with max_hops=2
            # Hop 0: node_B, node_C
            # Hop 1: node_D, node_E
            hops_2 = trace_hops(seed_address="node_A", max_hops=2)
            dest_addrs_2 = {h["address"] for h in hops_2}
            self.assertEqual(dest_addrs_2, {"node_B", "node_C", "node_D", "node_E"})
            self.assertEqual(len(hops_2), 4)

            # Hop indices:
            # Hop 0: node_B, node_C
            # Hop 1: node_D, node_E
            hop_0_addrs = {h["address"] for h in hops_2 if h["hop_index"] == 0}
            hop_1_addrs = {h["address"] for h in hops_2 if h["hop_index"] == 1}
            self.assertEqual(hop_0_addrs, {"node_B", "node_C"})
            self.assertEqual(hop_1_addrs, {"node_D", "node_E"})

    def test_trace_hops_from_sink_node(self):
        """Verify trace_hops() on a pure sink node returns empty hop list []."""
        with patch("tracing_engine.hop_tracer.get_transactions", side_effect=self.adapter.get_transactions):
            hops = trace_hops(seed_address="node_E", max_hops=4)
            self.assertEqual(hops, [])


if __name__ == "__main__":
    unittest.main()
