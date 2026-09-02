"""Unit tests for the VASP (Virtual Asset Service Provider) matcher (Task 5).

Verifies matching priority:
1. direct_tag (address directly in seed list)
2. cluster_match (clustered member in seed list)
3. unresolved (no match found)
"""

import pytest
from tracing_engine.clustering import ClusterInfo
from tracing_engine.vasp_matcher import match_vasp, load_seed_list


@pytest.fixture
def seed_dict():
    """Load the default curated seed dictionary."""
    return load_seed_list(force_reload=True)


def test_seed_list_loading_and_structure(seed_dict):
    """Verify that the seed list loads properly and contains expected fields."""
    assert len(seed_dict) >= 20, "Seed list should contain at least 20 verified addresses"
    for address, info in seed_dict.items():
        assert isinstance(address, str) and len(address) > 10
        assert "vasp_name" in info and len(info["vasp_name"]) > 0
        assert "source" in info and len(info["source"]) > 0
        assert info["confidence"] in ["high", "medium"]
        assert "notes" in info


def test_direct_tag_match_binance(seed_dict):
    """An address directly in the seed list returns direct_tag with correct vasp_name."""
    # Binance cold storage address
    binance_addr = "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo"
    result = match_vasp(binance_addr)

    assert result == {
        "matched_vasp": "Binance",
        "match_method": "direct_tag",
    }


def test_direct_tag_match_multiple_vasps():
    """Verify direct tagging across several major exchanges."""
    test_cases = [
        ("3D2oetdNuZUqQHPJmcMDDHYoqkyNVsFk9r", "Bitfinex"),
        ("1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ", "Coinbase"),
        ("bc1ql49ydapnjafl5t2cp9zqpjwe6pdgmxy98859v2", "Robinhood"),
        ("35Cm92BrvhoY6D2pu54VgBBVtBhcSveAzW", "Kraken"),
        ("3Ga8qCBzwMiitBGzaoHPhEFHpLMJEDpac7", "Bitstamp"),
        ("15ypfpV8KyoAw9JNDezHvHRFuQ5TLujuxM", "Bittrex"),
        ("19hx1B4pTDsBAYJJYYrj1t6bcVw1e9omuH", "Huobi"),
        ("1Po1oWkD2LmodfkBYiAktwh76vkF93LKnh", "Poloniex"),
        ("19vtVvVSbLzKTsrndadsgJcyq3RveWPG5E", "OKCoin"),
        ("17ac9tXHxu1nxdLgLu9WYk7vR8ggFN5GkH", "Luno"),
        ("1BQ3PsGSbqivWJm2TMBh2EiRzTS4pxcxwJ", "Paxful"),
        ("1Axkqh16GtQKsdsH7bvQXuSTX9Y7UUiuq1", "HitBTC"),
    ]
    for addr, expected_vasp in test_cases:
        res = match_vasp(addr)
        assert res["match_method"] == "direct_tag"
        assert res["matched_vasp"] == expected_vasp


def test_cluster_match():
    """An address NOT in the seed list, but clustered with one that is, returns cluster_match."""
    unknown_query_addr = "1UnknownSubjectWalletAddress1234567"
    known_kraken_member = "35Cm92BrvhoY6D2pu54VgBBVtBhcSveAzW"

    cluster = ClusterInfo(
        cluster_id=unknown_query_addr,
        members=[unknown_query_addr, "1AnotherRandomWalletAddress987", known_kraken_member],
        size=3,
    )

    result = match_vasp(unknown_query_addr, cluster_info=cluster)

    assert result == {
        "matched_vasp": "Kraken",
        "match_method": "cluster_match",
    }


def test_unresolved_no_seed_no_cluster():
    """An address with no seed-list match and no cluster returns unresolved with matched_vasp=None."""
    unknown_addr = "1NonExistentOrUnlabeledWalletAddress999"
    result = match_vasp(unknown_addr)

    assert result == {
        "matched_vasp": None,
        "match_method": "unresolved",
    }


def test_unresolved_with_unmatched_cluster():
    """An address not in the seed list, with cluster_info provided but NONE of its members in seed list."""
    unknown_query_addr = "1UnknownSubjectWalletAddress1111111"
    cluster = ClusterInfo(
        cluster_id=unknown_query_addr,
        members=[
            unknown_query_addr,
            "1UnknownPeerWalletAddress2222222",
            "1UnknownPeerWalletAddress3333333",
        ],
        size=3,
    )

    result = match_vasp(unknown_query_addr, cluster_info=cluster)

    assert result == {
        "matched_vasp": None,
        "match_method": "unresolved",
    }


def test_direct_takes_precedence_over_cluster():
    """Direct tag on query address takes priority even if cluster contains different VASP address."""
    direct_binance_addr = "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo"
    other_kraken_addr = "35Cm92BrvhoY6D2pu54VgBBVtBhcSveAzW"

    cluster = ClusterInfo(
        cluster_id=direct_binance_addr,
        members=[direct_binance_addr, other_kraken_addr],
        size=2,
    )

    result = match_vasp(direct_binance_addr, cluster_info=cluster)

    assert result == {
        "matched_vasp": "Binance",
        "match_method": "direct_tag",
    }


def test_empty_or_whitespace_address():
    """Empty or whitespace address returns unresolved when not in seed list."""
    assert match_vasp("") == {"matched_vasp": None, "match_method": "unresolved"}
    assert match_vasp("   ") == {"matched_vasp": None, "match_method": "unresolved"}
    assert match_vasp(None) == {"matched_vasp": None, "match_method": "unresolved"}


def test_custom_seed_dict_isolation():
    """Verify matcher works correctly with an isolated custom seed dictionary."""
    custom_seeds = {
        "1CustomExchangeAddr": {
            "vasp_name": "CustomVASP",
            "source": "Manual Test",
            "confidence": "high",
            "notes": "Test seed",
        }
    }

    # Direct match with custom seed
    res_direct = match_vasp("1CustomExchangeAddr", seed_dict=custom_seeds)
    assert res_direct == {"matched_vasp": "CustomVASP", "match_method": "direct_tag"}

    # Cluster match with custom seed
    cluster = ClusterInfo(
        cluster_id="1QueryAddr",
        members=["1QueryAddr", "1CustomExchangeAddr"],
        size=2,
    )
    res_cluster = match_vasp("1QueryAddr", cluster_info=cluster, seed_dict=custom_seeds)
    assert res_cluster == {"matched_vasp": "CustomVASP", "match_method": "cluster_match"}
