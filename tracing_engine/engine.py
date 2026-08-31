"""Master orchestrator for the SIH26182 Tracing Engine.

Exposes `trace_wallet()` as the primary black-box entrypoint for Person B
(Platform / Dashboard / Graph UI / Reports).
"""

import logging
from typing import Any, Dict, Optional
import requests

from tracing_engine.clustering import cluster_addresses
from tracing_engine.confidence import calculate_confidence
from tracing_engine.config import DEFAULT_MAX_HOPS
from tracing_engine.hop_tracer import trace_hops
from tracing_engine.schema import HopInfo, TraceResult
from tracing_engine.vasp_matcher import match_vasp

logger = logging.getLogger(__name__)


def trace_wallet(
    address: str,
    max_hops: int = DEFAULT_MAX_HOPS,
    session: Optional[requests.Session] = None
) -> Dict[str, Any]:
    """Execute complete cryptocurrency trace and VASP attribution for a target Bitcoin address.
    
    This function serves as the primary integration contract for Person B.
    It orchestrates:
    1. Forward BFS hop tracing using live mempool.space blockchain data.
    2. Multi-input address clustering (Day 4 stub).
    3. Curated VASP tag matching (Day 5 stub).
    4. Deterministic confidence scoring (Day 5-6 stub).
    5. Assembly of the canonical TraceResult JSON contract.
    
    Args:
        address: Bitcoin address to analyze (Base58 or Bech32).
        max_hops: Maximum exploration depth for forward hop tracing (default 4).
        session: Optional requests.Session for HTTP connection reuse.
        
    Returns:
        JSON-compliant dictionary matching the integration contract:
        {
            "query_address": "1A2b3C...",
            "chain": "bitcoin",
            "hops": [
                {
                    "hop_index": 0,
                    "address": "1Destination...",
                    "tx_hash": "9f8e7d...",
                    "timestamp": "2026-09-01T10:08:32Z",
                    "amount_btc": 0.452
                }
            ],
            "matched_vasp": null,
            "confidence": 0.0,
            "match_method": "unresolved",
            "risk_flags": []
        }
    """
    clean_address = address.strip() if address else ""
    logger.info(f"Initiating wallet trace for '{clean_address}' (max_hops={max_hops})")

    # 1. Forward hop tracing (live blockchain data)
    raw_hops = []
    if clean_address:
        try:
            raw_hops = trace_hops(
                seed_address=clean_address,
                max_hops=max_hops,
                session=session
            )
        except Exception as e:
            logger.error(f"Error during hop tracing for {clean_address}: {e}")
            raw_hops = []

    # Convert raw hop dicts to HopInfo dataclass instances
    hop_objects = [
        HopInfo(
            hop_index=hop["hop_index"],
            address=hop["address"],
            tx_hash=hop["tx_hash"],
            timestamp=hop.get("timestamp"),
            amount_btc=hop.get("amount_btc", 0.0)
        )
        for hop in raw_hops
    ]

    # 2. Entity clustering (Day 4 Component - currently stubbed)
    cluster = cluster_addresses(clean_address)

    # 3. VASP identification (Day 5 Component - currently stubbed)
    matched_vasp, match_method = match_vasp(
        query_address=clean_address,
        cluster=cluster,
        hops=raw_hops
    )

    # 4. Confidence scoring (Task 6 Component)
    cluster_size = (
        cluster.size
        if hasattr(cluster, "size")
        else (len(cluster.members) if hasattr(cluster, "members") else None)
    )
    confidence = calculate_confidence(
        match_method=match_method,
        hop_index=0,
        cluster_size=cluster_size,
        seed_entry_confidence=None,
    )

    # 5. Assemble final contract
    # Note: risk_flags is strictly owned by Person B and initialized as empty list []
    trace_result = TraceResult(
        query_address=clean_address,
        chain="bitcoin",
        hops=hop_objects,
        matched_vasp=matched_vasp,
        confidence=confidence,
        match_method=match_method,
        risk_flags=[]
    )

    return trace_result.to_dict()
