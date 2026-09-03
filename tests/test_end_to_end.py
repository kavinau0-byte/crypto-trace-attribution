"""End-to-end live network tests for the SIH26182 Tracing Engine.

IMPORTANT: These tests intentionally hit the REAL mempool.space API through the
full trace_wallet() entrypoint — NO mocking. They validate the complete
integration pipeline: fetcher -> hop_tracer -> clustering -> vasp_matcher ->
confidence -> engine contract assembly.

These tests require an active internet connection and may be slow due to real
HTTP round-trips to mempool.space. They are designed to verify that the full
system produces correct, well-formed output against real Bitcoin blockchain data.
"""

import unittest

from tracing_engine.engine import trace_wallet


# Full 7-key contract shape expected from trace_wallet()
EXPECTED_CONTRACT_KEYS = {
    "query_address", "chain", "hops", "matched_vasp",
    "confidence", "match_method", "risk_flags"
}


def _assert_full_contract_shape(test_case, result, expected_address):
    """Helper: assert the full 7-key JSON contract shape and type invariants."""
    test_case.assertIsInstance(result, dict)
    test_case.assertEqual(set(result.keys()), EXPECTED_CONTRACT_KEYS)

    test_case.assertEqual(result["query_address"], expected_address)
    test_case.assertEqual(result["chain"], "bitcoin")
    test_case.assertIsInstance(result["hops"], list)
    test_case.assertIn(result["match_method"], ["direct_tag", "cluster_match", "unresolved"])
    test_case.assertIsInstance(result["confidence"], (int, float))
    test_case.assertGreaterEqual(result["confidence"], 0.0)
    test_case.assertLessEqual(result["confidence"], 1.0)
    test_case.assertIsInstance(result["risk_flags"], list)
    test_case.assertEqual(result["risk_flags"], [], "risk_flags must be empty (owned by Person B)")

    # Validate each hop's shape if present
    for hop in result["hops"]:
        test_case.assertIn("hop_index", hop)
        test_case.assertIn("address", hop)
        test_case.assertIn("tx_hash", hop)
        test_case.assertIn("timestamp", hop)
        test_case.assertIn("amount_btc", hop)
        test_case.assertIsInstance(hop["hop_index"], int)
        test_case.assertIsInstance(hop["amount_btc"], (int, float))


class TestEndToEndLive(unittest.TestCase):
    """LIVE NETWORK TESTS: Full trace_wallet() integration against real mempool.space API."""

    def test_binance_direct_tag(self):
        """LIVE: Known Binance cold storage address must match as direct_tag.

        Address 34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo is a verified Binance reserve
        wallet present in data/vasp_seed_list.json with confidence=high.
        """
        binance_addr = "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo"
        result = trace_wallet(binance_addr, max_hops=1)

        _assert_full_contract_shape(self, result, binance_addr)
        self.assertEqual(result["matched_vasp"], "Binance")
        self.assertEqual(result["match_method"], "direct_tag")

    def test_bitfinex_direct_tag(self):
        """LIVE: Known Bitfinex cold wallet must match as direct_tag.

        Address 3D2oetdNuZUqQHPJmcMDDHYoqkyNVsFk9r is a verified Bitfinex
        multi-signature cold storage wallet in data/vasp_seed_list.json.
        This proves more than one VASP actually matches, not just Binance.
        """
        bitfinex_addr = "3D2oetdNuZUqQHPJmcMDDHYoqkyNVsFk9r"
        result = trace_wallet(bitfinex_addr, max_hops=1)

        _assert_full_contract_shape(self, result, bitfinex_addr)
        self.assertEqual(result["matched_vasp"], "Bitfinex")
        self.assertEqual(result["match_method"], "direct_tag")

    def test_unresolved_address(self):
        """LIVE: Real address NOT in VASP seed list must return well-formed unresolved contract.

        Uses the Bitcoin genesis / Satoshi address 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa which
        is definitely not in the VASP seed list but has real on-chain activity.
        """
        unresolved_addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        result = trace_wallet(unresolved_addr, max_hops=1)

        _assert_full_contract_shape(self, result, unresolved_addr)
        self.assertEqual(result["match_method"], "unresolved")
        self.assertIsNone(result["matched_vasp"])
        # Unresolved confidence must be exactly 0.0 per confidence.py spec
        self.assertEqual(result["confidence"], 0.0)


if __name__ == "__main__":
    unittest.main()
