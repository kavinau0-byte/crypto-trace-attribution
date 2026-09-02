"""Address clustering module for Bitcoin heuristics (Task 4 Component).

This clustering is a heuristic based on common-input-ownership.
It is NOT proof of common wallet ownership. Known failure mode:
CoinJoin/mixing transactions can cause false-positive merges
between unrelated addresses. A coarse input-count guard
(MAX_INPUTS_FOR_CLUSTERING) partially mitigates this but does not
eliminate it.

================================================================================
CLUSTERING HEURISTICS & ARCHITECTURAL SPECIFICATION:
================================================================================
1. Common Input Ownership Heuristic (CIOH):
   In standard Bitcoin transactions, all spending inputs must be cryptographically
   signed by the private keys controlling their respective UTXOs. Consequently,
   all input addresses in a multi-input transaction are assumed to belong to the
   same wallet/entity.
   
2. CoinJoin & Mixer Mitigation:
   Collaborative transactions (CoinJoin / Wasabi / Whirlpool) intentionally combine
   inputs from multiple independent users to obfuscate transaction graphs. Merging
   such inputs leads to catastrophic cluster over-expansion ("super-clustering").
   We apply a coarse guard: transactions with more than MAX_INPUTS_FOR_CLUSTERING
   inputs are excluded from input unioning.

3. Disjoint-Set / Union-Find:
   Entity clusters are formed and transitively merged using an in-memory disjoint-set
   data structure with path compression and union by rank.
================================================================================
"""

from dataclasses import dataclass, asdict
import logging
import time
from typing import Any, Dict, List, Optional, Set, Union
import requests

from tracing_engine.config import (
    BACKOFF_FACTOR,
    DEFAULT_HEADERS,
    INITIAL_RETRY_DELAY,
    MAX_RETRIES,
    MEMPOOL_API_BASE,
    REQUEST_TIMEOUT,
)
from tracing_engine.fetcher import get_transactions

logger = logging.getLogger(__name__)

# Coarse heuristic threshold to guard against CoinJoin-style mixing transactions.
# Standard user/merchant transactions rarely consume more than 5 distinct input addresses.
# Transactions with >5 inputs have a significantly higher likelihood of being CoinJoins,
# exchange consolidation sweeps, or batch settlements, which would cause false-positive merges.
MAX_INPUTS_FOR_CLUSTERING: int = 5


@dataclass
class ClusterInfo:
    """Metadata representing an identified entity cluster for an address.
    
    Attributes:
        cluster_id: Canonical identifier for the cluster (root representative address).
        members: Complete list of Bitcoin addresses belonging to this cluster.
        size: Total number of addresses in the cluster.
    """
    cluster_id: str
    members: List[str]
    size: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert ClusterInfo to a standard dictionary."""
        return asdict(self)


class DisjointSet:
    """Lightweight Disjoint-Set (Union-Find) with path compression and union by rank."""

    def __init__(self) -> None:
        self.parent: Dict[str, str] = {}
        self.rank: Dict[str, int] = {}

    def add(self, item: str) -> None:
        """Register an item as a singleton set if not already present."""
        if item not in self.parent:
            self.parent[item] = item
            self.rank[item] = 0

    def find(self, item: str) -> str:
        """Find the root representative of the set containing item (with path compression)."""
        if item not in self.parent:
            self.add(item)
            return item
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, item1: str, item2: str) -> None:
        """Merge the sets containing item1 and item2 (with union by rank)."""
        root1 = self.find(item1)
        root2 = self.find(item2)

        if root1 == root2:
            return

        if self.rank[root1] < self.rank[root2]:
            self.parent[root1] = root2
        elif self.rank[root1] > self.rank[root2]:
            self.parent[root2] = root1
        else:
            self.parent[root2] = root1
            self.rank[root1] += 1

    def get_clusters(self) -> Dict[str, List[str]]:
        """Return a mapping of root representative address -> list of member addresses."""
        clusters: Dict[str, List[str]] = {}
        for item in self.parent:
            root = self.find(item)
            if root not in clusters:
                clusters[root] = []
            clusters[root].append(item)
        return clusters


def fetch_transaction_details(
    tx_hash: str,
    session: Optional[requests.Session] = None
) -> Optional[Dict[str, Any]]:
    """Fetch complete transaction details for a single transaction hash from mempool.space.
    
    NOTE (Step 0 Requirement):
    hop_tracer.py only records the single destination hop address followed during forward BFS,
    not all co-spending input addresses of the transaction. When clustering addresses from
    raw hop records or standalone tx hashes, this helper fetches the complete transaction
    payload to extract all input UTXO addresses.
    
    Args:
        tx_hash: Bitcoin transaction identifier (txid).
        session: Optional persistent requests.Session for connection reuse.
        
    Returns:
        Raw transaction dictionary from mempool.space or None if fetch fails.
    """
    clean_tx = tx_hash.strip() if tx_hash else ""
    if not clean_tx:
        return None

    url = f"{MEMPOOL_API_BASE}/tx/{clean_tx}"
    http = session or requests

    retry_delay = INITIAL_RETRY_DELAY
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = http.get(
                url,
                headers=DEFAULT_HEADERS,
                timeout=REQUEST_TIMEOUT
            )
            if response.status_code in (429, 500, 502, 503, 504):
                logger.warning(
                    f"mempool.space API returned HTTP {response.status_code} for tx {clean_tx}. "
                    f"Attempt {attempt}/{MAX_RETRIES}. Retrying in {retry_delay:.2f}s..."
                )
                time.sleep(retry_delay)
                retry_delay *= BACKOFF_FACTOR
                continue

            if response.status_code in (400, 404):
                logger.warning(f"Transaction not found or invalid: {clean_tx} (HTTP {response.status_code})")
                return None

            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else None

        except requests.exceptions.RequestException as e:
            logger.warning(f"Network error fetching tx {clean_tx}: {e}. Attempt {attempt}/{MAX_RETRIES}.")
            if attempt < MAX_RETRIES:
                time.sleep(retry_delay)
                retry_delay *= BACKOFF_FACTOR
            else:
                logger.error(f"Failed to fetch tx details for {clean_tx} after {MAX_RETRIES} attempts.")
                return None
        except ValueError as e:
            logger.error(f"Failed to parse JSON for tx {clean_tx}: {e}")
            return None

    return None


def extract_input_addresses(
    tx: Union[Dict[str, Any], str],
    session: Optional[requests.Session] = None
) -> List[str]:
    """Extract all valid, non-coinbase input addresses from a transaction.
    
    Supports:
    - Normalized transaction dicts (from fetcher.py with "inputs" key)
    - Raw mempool.space transaction dicts (with "vin" key)
    - Hop dictionaries or transaction hashes (fetches full tx details if necessary)
    
    Args:
        tx: Transaction dictionary or tx_hash string.
        session: Optional shared requests.Session.
        
    Returns:
        List of distinct input addresses for the transaction.
    """
    raw_tx = tx
    if isinstance(tx, str):
        raw_tx = fetch_transaction_details(tx, session=session)
        if not raw_tx:
            return []

    if not isinstance(raw_tx, dict):
        return []

    # If transaction is a hop record with only tx_hash and without full inputs/vin
    if "inputs" not in raw_tx and "vin" not in raw_tx and "tx_hash" in raw_tx:
        fetched = fetch_transaction_details(raw_tx["tx_hash"], session=session)
        if fetched:
            raw_tx = fetched
        else:
            return []

    input_addresses: List[str] = []

    # 1. Normalized transaction format (fetcher.py)
    if "inputs" in raw_tx and isinstance(raw_tx["inputs"], list):
        for inp in raw_tx["inputs"]:
            if isinstance(inp, dict) and not inp.get("is_coinbase", False):
                addr = inp.get("address")
                if addr and isinstance(addr, str) and addr.strip():
                    input_addresses.append(addr.strip())

    # 2. Raw mempool.space format
    elif "vin" in raw_tx and isinstance(raw_tx["vin"], list):
        for vin in raw_tx["vin"]:
            if isinstance(vin, dict) and not vin.get("is_coinbase", False):
                prevout = vin.get("prevout") or {}
                addr = prevout.get("scriptpubkey_address")
                if addr and isinstance(addr, str) and addr.strip():
                    input_addresses.append(addr.strip())

    # Return deduplicated input addresses while preserving order
    seen: Set[str] = set()
    deduped: List[str] = []
    for addr in input_addresses:
        if addr not in seen:
            seen.add(addr)
            deduped.append(addr)

    return deduped


def build_clusters(
    transactions: List[Any],
    session: Optional[requests.Session] = None
) -> Dict[str, ClusterInfo]:
    """Cluster Bitcoin addresses using the Common-Input-Ownership Heuristic (CIOH).
    
    For each transaction in `transactions`:
    1. Extracts all distinct input addresses.
    2. Registers every input address in the disjoint-set structure.
    3. Evaluates the mixing guard: if input count exceeds MAX_INPUTS_FOR_CLUSTERING (5),
       the transaction is skipped for unioning (inputs remain in their respective clusters).
    4. For transactions passing the guard with >= 2 inputs, all input addresses are unioned.
    
    Args:
        transactions: List of transaction dictionaries (normalized or raw) or hop objects.
        session: Optional requests.Session for network pooling if transaction details need fetching.
        
    Returns:
        Dictionary mapping each observed address -> ClusterInfo(cluster_id, members, size).
    """
    if not transactions:
        return {}

    disjoint_set = DisjointSet()

    for tx in transactions:
        inputs = extract_input_addresses(tx, session=session)

        # Register every address in disjoint-set as at least a singleton
        for addr in inputs:
            disjoint_set.add(addr)

        # Guard: Skip unioning if single input or if likely CoinJoin (> MAX_INPUTS_FOR_CLUSTERING)
        if len(inputs) <= 1:
            continue

        if len(inputs) > MAX_INPUTS_FOR_CLUSTERING:
            logger.info(
                f"Skipping multi-input clustering for transaction with {len(inputs)} inputs "
                f"(exceeds MAX_INPUTS_FOR_CLUSTERING={MAX_INPUTS_FOR_CLUSTERING} CoinJoin guard)."
            )
            continue

        # CIOH Union: All inputs co-spending in this valid transaction belong to the same entity
        primary_input = inputs[0]
        for co_input in inputs[1:]:
            disjoint_set.union(primary_input, co_input)

    # Build cluster mapping and metadata
    raw_clusters = disjoint_set.get_clusters()
    result_clusters: Dict[str, ClusterInfo] = {}

    for root_id, member_list in raw_clusters.items():
        # Sort members for deterministic output ordering
        sorted_members = sorted(member_list)
        cluster_metadata = ClusterInfo(
            cluster_id=root_id,
            members=sorted_members,
            size=len(sorted_members)
        )
        for member_addr in sorted_members:
            result_clusters[member_addr] = cluster_metadata

    return result_clusters


def cluster_addresses(
    seed_address: str,
    max_depth: int = 1,
    session: Optional[requests.Session] = None
) -> Set[str]:
    """Identify the cluster of Bitcoin addresses belonging to the same entity as `seed_address`.
    
    Fetches the transaction history for `seed_address`, performs CIOH clustering,
    and returns the set of all addresses belonging to the seed address's cluster.
    
    Args:
        seed_address: The target Bitcoin address to cluster.
        max_depth: Reserved for multi-hop cluster expansion (depth=1 default for CIOH).
        session: Optional persistent requests.Session instance.
        
    Returns:
        Set of Bitcoin addresses attributed to the same entity cluster (at minimum contains seed_address).
    """
    clean_seed = seed_address.strip() if seed_address else ""
    if not clean_seed:
        return set()

    logger.info(f"Clustering entity addresses for seed {clean_seed}")
    
    try:
        txs = get_transactions(clean_seed, session=session)
    except Exception as e:
        logger.warning(f"Failed to fetch transactions for clustering {clean_seed}: {e}")
        return {clean_seed}

    if not txs:
        return {clean_seed}

    clusters = build_clusters(txs, session=session)

    if clean_seed in clusters:
        return set(clusters[clean_seed].members)

    return {clean_seed}
