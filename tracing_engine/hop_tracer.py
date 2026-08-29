"""Forward hop tracing module for Bitcoin transaction graphs.

Implements Breadth-First Search (BFS) forward exploration from a query address,
following output addresses across transactions to trace fund flow towards potential VASPs.

================================================================================
HEURISTIC & UTXO ARCHITECTURE NOTICE:
================================================================================
Bitcoin operates on the Unspent Transaction Output (UTXO) model rather than an
account-based model (like Ethereum). Key implications for forward tracing:
1. Multiple Inputs & Outputs: A single transaction frequently aggregates coins
   from multiple input addresses and splits them across multiple outputs (e.g.
   intended payment recipient + change address).
2. Heuristic Forward Tracing: This BFS tracer performs a heuristic forward trace
   by following destination outputs where the current address is an input spender.
3. Change Outputs & Address Reuse: Without heuristics to distinguish change
   addresses from recipient addresses (which will be implemented in Day 4
   `clustering.py` using Common Input Ownership & Change Heuristics), forward
   tracing may follow both change and payment paths.
4. Cycles & Loops: Cryptocurrency transactions can loop back to known entities;
   a visited-address set prevents infinite loops and ensures BFS termination.
================================================================================
"""

import collections
import logging
from typing import Any, Dict, List, Optional, Set
import requests

from tracing_engine.config import DEFAULT_MAX_HOPS
from tracing_engine.fetcher import get_transactions
from tracing_engine.schema import HopInfo

logger = logging.getLogger(__name__)


def trace_hops(
    seed_address: str,
    max_hops: int = DEFAULT_MAX_HOPS,
    session: Optional[requests.Session] = None,
    max_branches_per_tx: int = 5
) -> List[Dict[str, Any]]:
    """Perform forward BFS hop tracing from a starting Bitcoin seed address.
    
    Traverses forward through transactions where the current address acted as an input
    spender, identifying downstream destination addresses up to `max_hops` depth.
    
    Args:
        seed_address: The initial target Bitcoin address to begin tracing from.
        max_hops: Maximum BFS depth level (0-indexed hop levels up to max_hops - 1).
        session: Optional shared requests.Session for network pooling.
        max_branches_per_tx: Safeguard capping destination branches per transaction
            to prevent graph explosion on high-fanout batch transactions (e.g. exchange withdrawals).
            
    Returns:
        List of hop dictionaries matching the HopInfo schema:
        [
            {
                "hop_index": 0,
                "address": "1Destination...",
                "tx_hash": "9f8e7d...",
                "timestamp": "2026-09-01T10:08:32Z",
                "amount_btc": 0.452
            },
            ...
        ]
    """
    clean_seed = seed_address.strip() if seed_address else ""
    if not clean_seed or max_hops <= 0:
        return []

    visited_addresses: Set[str] = {clean_seed}
    hops_record: List[Dict[str, Any]] = []

    # Queue contains tuples of (current_address, current_hop_index)
    queue = collections.deque([(clean_seed, 0)])

    logger.info(f"Starting forward BFS trace from {clean_seed} (max_hops={max_hops})")

    while queue:
        current_addr, current_hop = queue.popleft()

        if current_hop >= max_hops:
            continue

        # Fetch transactions for current address
        try:
            txs = get_transactions(current_addr, session=session)
        except Exception as e:
            logger.warning(f"Unexpected error fetching transactions for {current_addr}: {e}")
            continue

        if not txs:
            logger.debug(f"No transactions found for address {current_addr} at hop {current_hop}")
            continue

        # Analyze transactions to locate outgoing spends where current_addr was an input
        for tx in txs:
            tx_hash = tx.get("tx_hash", "")
            timestamp = tx.get("timestamp")
            inputs = tx.get("inputs", [])
            outputs = tx.get("outputs", [])

            # Check if current_addr is among the inputs (i.e. sending funds out)
            is_spender = any(inp.get("address") == current_addr for inp in inputs)
            
            # Only follow transactions where current_addr actually spent funds (was an input).
            # This applies uniformly to the seed address too -- if the seed only ever received
            # money in a given tx, we must not treat that tx's other outputs as downstream hops,
            # since the seed never sent that money anywhere.
            if not is_spender:
                continue

            branches_count = 0
            for out in outputs:
                dest_addr = out.get("address")
                amount_btc = out.get("value_btc", 0.0)

                # Skip invalid, missing, self-referencing (same address), or already visited addresses
                if not dest_addr or dest_addr == current_addr or dest_addr in visited_addresses:
                    continue

                # Record the hop
                hop_entry = HopInfo(
                    hop_index=current_hop,
                    address=dest_addr,
                    tx_hash=tx_hash,
                    timestamp=timestamp,
                    amount_btc=amount_btc
                )
                hops_record.append(hop_entry.to_dict())
                visited_addresses.add(dest_addr)
                branches_count += 1

                # Enqueue next level exploration if depth allows
                next_hop = current_hop + 1
                if next_hop < max_hops:
                    queue.append((dest_addr, next_hop))

                if branches_count >= max_branches_per_tx:
                    logger.debug(
                        f"Reached branch limit ({max_branches_per_tx}) for tx {tx_hash} at hop {current_hop}"
                    )
                    break

    logger.info(
        f"Completed forward trace for {clean_seed}: discovered {len(hops_record)} hops across {len(visited_addresses)} addresses"
    )
    return hops_record
