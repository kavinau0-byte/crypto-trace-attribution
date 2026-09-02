"""Unit tests for the CIOH clustering module."""

import unittest
from tracing_engine.clustering import (
    build_clusters,
    cluster_addresses,
    extract_input_addresses,
    DisjointSet,
    ClusterInfo,
    MAX_INPUTS_FOR_CLUSTERING,
)


class TestClustering(unittest.TestCase):
    """Test suite for Common-Input-Ownership Heuristic (CIOH) clustering."""

    def test_two_co_appearing_inputs_same_cluster(self):
        """Two addresses that co-appear as inputs in one transaction end up in the same cluster."""
        txs = [
            {
                "tx_hash": "tx_001",
                "inputs": [
                    {"address": "1AddrA", "value_btc": 1.0},
                    {"address": "1AddrB", "value_btc": 2.0}
                ],
                "outputs": [
                    {"address": "1AddrRecipient", "value_btc": 3.0}
                ]
            }
        ]

        clusters = build_clusters(txs)
        self.assertIn("1AddrA", clusters)
        self.assertIn("1AddrB", clusters)
        self.assertEqual(clusters["1AddrA"].cluster_id, clusters["1AddrB"].cluster_id)
        self.assertEqual(clusters["1AddrA"].size, 2)
        self.assertEqual(clusters["1AddrB"].size, 2)
        self.assertEqual(sorted(clusters["1AddrA"].members), ["1AddrA", "1AddrB"])

    def test_singleton_address_stays_in_own_cluster(self):
        """An address that never co-appears with anything stays in its own singleton cluster."""
        txs = [
            {
                "tx_hash": "tx_single_input",
                "inputs": [
                    {"address": "1SoloAddr", "value_btc": 0.5}
                ],
                "outputs": [
                    {"address": "1Destination", "value_btc": 0.49}
                ]
            }
        ]

        clusters = build_clusters(txs)
        self.assertIn("1SoloAddr", clusters)
        self.assertEqual(clusters["1SoloAddr"].cluster_id, "1SoloAddr")
        self.assertEqual(clusters["1SoloAddr"].members, ["1SoloAddr"])
        self.assertEqual(clusters["1SoloAddr"].size, 1)

    def test_coinjoin_guard_exceeding_max_inputs(self):
        """A transaction with >5 inputs does NOT cause its addresses to be unioned (guard works)."""
        # Create a tx with 6 inputs (exceeding MAX_INPUTS_FOR_CLUSTERING = 5)
        six_addresses = [f"1MixerUser{i}" for i in range(1, 7)]
        txs = [
            {
                "tx_hash": "tx_coinjoin_6_inputs",
                "inputs": [{"address": addr, "value_btc": 0.1} for addr in six_addresses],
                "outputs": [{"address": "1MixerOut", "value_btc": 0.6}]
            }
        ]

        self.assertGreater(len(six_addresses), MAX_INPUTS_FOR_CLUSTERING)

        clusters = build_clusters(txs)

        # All 6 addresses should exist as singletons and NOT be merged into a single cluster
        for addr in six_addresses:
            self.assertIn(addr, clusters)
            self.assertEqual(clusters[addr].cluster_id, addr)
            self.assertEqual(clusters[addr].size, 1)
            self.assertEqual(clusters[addr].members, [addr])

    def test_transitive_merging(self):
        """Transitive merging: if tx A merges {X,Y} and tx B merges {Y,Z}, then X, Y, Z all end up in the same cluster."""
        tx_a = {
            "tx_hash": "tx_a",
            "inputs": [
                {"address": "1AddrX", "value_btc": 1.0},
                {"address": "1AddrY", "value_btc": 1.5}
            ]
        }
        tx_b = {
            "tx_hash": "tx_b",
            "inputs": [
                {"address": "1AddrY", "value_btc": 0.8},
                {"address": "1AddrZ", "value_btc": 2.2}
            ]
        }

        clusters = build_clusters([tx_a, tx_b])

        # All three addresses must have identical cluster_id, size=3, and members=[1AddrX, 1AddrY, 1AddrZ]
        self.assertIn("1AddrX", clusters)
        self.assertIn("1AddrY", clusters)
        self.assertIn("1AddrZ", clusters)

        root = clusters["1AddrX"].cluster_id
        self.assertEqual(clusters["1AddrY"].cluster_id, root)
        self.assertEqual(clusters["1AddrZ"].cluster_id, root)

        expected_members = ["1AddrX", "1AddrY", "1AddrZ"]
        self.assertEqual(sorted(clusters["1AddrX"].members), expected_members)
        self.assertEqual(sorted(clusters["1AddrY"].members), expected_members)
        self.assertEqual(sorted(clusters["1AddrZ"].members), expected_members)
        self.assertEqual(clusters["1AddrX"].size, 3)

    def test_extract_input_addresses_raw_vin_format(self):
        """Test input address extraction from raw mempool.space vin structure."""
        raw_tx = {
            "txid": "raw_tx_001",
            "vin": [
                {
                    "is_coinbase": False,
                    "prevout": {"scriptpubkey_address": "1RawAddrA", "value": 50000}
                },
                {
                    "is_coinbase": False,
                    "prevout": {"scriptpubkey_address": "1RawAddrB", "value": 75000}
                },
                {
                    "is_coinbase": True  # Should be skipped
                }
            ]
        }

        inputs = extract_input_addresses(raw_tx)
        self.assertEqual(inputs, ["1RawAddrA", "1RawAddrB"])

    def test_disjoint_set_direct_operations(self):
        """Test unit operations of the internal DisjointSet implementation."""
        ds = DisjointSet()
        ds.add("A")
        ds.add("B")
        ds.add("C")

        self.assertEqual(ds.find("A"), "A")
        self.assertNotEqual(ds.find("A"), ds.find("B"))

        ds.union("A", "B")
        self.assertEqual(ds.find("A"), ds.find("B"))
        self.assertNotEqual(ds.find("A"), ds.find("C"))

        ds.union("B", "C")
        self.assertEqual(ds.find("A"), ds.find("C"))

        clusters = ds.get_clusters()
        self.assertEqual(len(clusters), 1)
        root = list(clusters.keys())[0]
        self.assertEqual(sorted(clusters[root]), ["A", "B", "C"])


if __name__ == "__main__":
    unittest.main()
