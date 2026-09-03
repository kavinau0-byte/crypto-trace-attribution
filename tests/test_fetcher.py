"""Tests for the transaction fetcher and tracing engine modules."""

import unittest
from unittest.mock import patch, MagicMock
import requests

from tracing_engine.fetcher import get_transactions
from tracing_engine.engine import trace_wallet
from tracing_engine.schema import TraceResult, HopInfo
from tracing_engine.config import MAX_RETRIES


class TestFetcher(unittest.TestCase):
    """Smoke and unit tests for mempool.space fetcher."""

    def test_get_transactions_known_address(self):
        """Smoke test fetching transactions for a known active Bitcoin address."""
        # Genesis address: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
        genesis_addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        txs = get_transactions(genesis_addr)

        self.assertIsInstance(txs, list)
        self.assertGreater(len(txs), 0, "Genesis address should return historical transactions")

        # Validate transaction normalization structure
        sample_tx = txs[0]
        self.assertIn("tx_hash", sample_tx)
        self.assertIn("timestamp", sample_tx)
        self.assertIn("confirmed", sample_tx)
        self.assertIn("inputs", sample_tx)
        self.assertIn("outputs", sample_tx)
        self.assertIsInstance(sample_tx["inputs"], list)
        self.assertIsInstance(sample_tx["outputs"], list)

        # Validate input/output field structures
        if sample_tx["outputs"]:
            out = sample_tx["outputs"][0]
            self.assertIn("address", out)
            self.assertIn("value_sat", out)
            self.assertIn("value_btc", out)

    def test_get_transactions_invalid_address(self):
        """Test graceful handling of invalid addresses without crashing."""
        invalid_addr = "invalid_non_existent_bitcoin_address_12345"
        txs = get_transactions(invalid_addr)
        self.assertIsInstance(txs, list)
        self.assertEqual(len(txs), 0)

    def test_get_transactions_empty_address(self):
        """Test handling of empty string address."""
        txs = get_transactions("")
        self.assertIsInstance(txs, list)
        self.assertEqual(len(txs), 0)


class TestFetcherMocked(unittest.TestCase):
    """Mocked tests for get_transactions retry and error handling — zero real network calls."""

    @patch("tracing_engine.fetcher.time.sleep")
    def test_429_then_success(self, mock_sleep):
        """First call returns 429 (rate limit), second call returns 200 with valid data."""
        # Build mock responses
        mock_429 = MagicMock()
        mock_429.status_code = 429

        sample_raw_tx = {
            "txid": "abc123",
            "status": {"confirmed": True, "block_time": 1700000000},
            "fee": 1000,
            "vin": [{"prevout": {"scriptpubkey_address": "sender_A", "value": 100000},
                      "is_coinbase": False, "txid": "prev_tx", "vout": 0}],
            "vout": [{"scriptpubkey_address": "dest_B", "value": 50000,
                       "scriptpubkey_type": "p2pkh"}],
        }
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = [sample_raw_tx]
        mock_200.raise_for_status = MagicMock()

        with patch("tracing_engine.fetcher.requests") as mock_requests:
            mock_requests.get.side_effect = [mock_429, mock_200]
            mock_requests.exceptions = requests.exceptions

            result = get_transactions("test_address_429")

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["tx_hash"], "abc123")
        # time.sleep must have been called during backoff
        mock_sleep.assert_called()

    @patch("tracing_engine.fetcher.time.sleep")
    def test_persistent_timeout_exhausts_retries(self, mock_sleep):
        """All retries raise Timeout — must return [] and call mock exactly MAX_RETRIES times."""
        with patch("tracing_engine.fetcher.requests") as mock_requests:
            mock_requests.get.side_effect = requests.exceptions.Timeout("timed out")
            mock_requests.exceptions = requests.exceptions

            result = get_transactions("test_address_timeout")

        self.assertIsInstance(result, list)
        self.assertEqual(result, [])
        self.assertEqual(
            mock_requests.get.call_count,
            MAX_RETRIES,
            f"Must retry exactly MAX_RETRIES={MAX_RETRIES} times before giving up",
        )


class TestEngineContract(unittest.TestCase):
    """Integration and schema contract verification tests."""

    def test_trace_wallet_contract_structure(self):
        """Verify that trace_wallet returns the exact JSON contract required for Person B."""
        test_addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        result = trace_wallet(test_addr, max_hops=1)

        # Top-level contract validation
        self.assertIsInstance(result, dict)
        expected_keys = {
            "query_address",
            "chain",
            "hops",
            "matched_vasp",
            "confidence",
            "match_method",
            "risk_flags"
        }
        self.assertEqual(set(result.keys()), expected_keys)

        # Field types and values
        self.assertEqual(result["query_address"], test_addr)
        self.assertEqual(result["chain"], "bitcoin")
        self.assertIsInstance(result["hops"], list)
        self.assertIn(result["match_method"], ["direct_tag", "cluster_match", "unresolved"])
        self.assertIsInstance(result["confidence"], (int, float))
        self.assertEqual(result["risk_flags"], [], "risk_flags must remain empty list for Person B")

        # If hops exist, validate Hop structure
        for hop in result["hops"]:
            self.assertIn("hop_index", hop)
            self.assertIn("address", hop)
            self.assertIn("tx_hash", hop)
            self.assertIn("timestamp", hop)
            self.assertIn("amount_btc", hop)
            self.assertIsInstance(hop["hop_index"], int)
            self.assertIsInstance(hop["amount_btc"], (int, float))

    def test_trace_wallet_invalid_address(self):
        """Verify trace_wallet handles invalid address gracefully and returns valid empty-hop contract."""
        result = trace_wallet("not_a_real_address", max_hops=2)
        self.assertEqual(result["query_address"], "not_a_real_address")
        self.assertEqual(result["chain"], "bitcoin")
        self.assertEqual(result["hops"], [])
        self.assertIsNone(result["matched_vasp"])
        self.assertEqual(result["confidence"], 0.0)
        self.assertEqual(result["match_method"], "unresolved")
        self.assertEqual(result["risk_flags"], [])


if __name__ == "__main__":
    unittest.main()

