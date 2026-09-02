"""Elliptic Bitcoin transaction dataset graph adapter (Task 7 Component).

Converts the Kaggle Elliptic Bitcoin transaction-to-transaction edgelist
into the transaction dictionary format consumed by `tracing_engine.hop_tracer.trace_hops()`.

================================================================================
FORENSIC & BENCHMARKING SCOPE DISCLAIMER:
================================================================================
amount_btc and timestamp are placeholders; this dataset provides transaction-graph
topology only, not real amounts or times. Do not use output of this adapter to
validate amount or timestamp handling.

Topological Substitution & Transaction Batching:
Elliptic graph nodes represent Bitcoin transactions (txIds), not addresses.
In this benchmark, each Elliptic txId is used as a stand-in "address" purely
to exercise the BFS graph traversal algorithm against real, large-scale Bitcoin
transaction topology (branching factors, graph depth, and fan-out structures)
without fabricating external data sources.

Each source node synthesizes a single transaction containing all of that node's
outgoing edges in its `outputs` list (with `tx_hash` prefixed `elliptic_node_tx::{node_id}`).
This batching faithfully represents the node's real Bitcoin transaction out-degree,
allowing the BFS traversal engine's `max_branches_per_tx` safeguard to properly
cap high-fanout nodes.
================================================================================
"""

from collections import defaultdict
import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)

# Default path to the Elliptic transaction edgelist CSV
DEFAULT_EDGELIST_PATH: Path = (
    Path(__file__).resolve().parent.parent / "data" / "elliptic" / "elliptic_txs_edgelist.csv"
)


class EllipticGraphAdapter:
    """In-memory graph adapter mapping Elliptic transaction edges into fetcher-compatible responses."""

    def __init__(
        self,
        edgelist_path: Optional[Union[str, Path]] = None,
        adjacency_dict: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        """Initialize the adapter.

        Args:
            edgelist_path: Path to the elliptic_txs_edgelist.csv file.
            adjacency_dict: Optional pre-constructed adjacency dictionary (useful for unit tests).
        """
        self.edgelist_path = Path(edgelist_path) if edgelist_path else DEFAULT_EDGELIST_PATH
        self._adj: Dict[str, List[str]] = defaultdict(list)
        self._all_nodes: Set[str] = set()
        self._sources: Set[str] = set()
        self._destinations: Set[str] = set()
        self._is_loaded: bool = False

        if adjacency_dict is not None:
            self._load_from_dict(adjacency_dict)
        elif self.edgelist_path.exists():
            self.load()

    def _load_from_dict(self, adjacency_dict: Dict[str, List[str]]) -> None:
        """Load graph topology directly from an in-memory dictionary."""
        self._adj = defaultdict(list)
        self._all_nodes = set()
        self._sources = set()
        self._destinations = set()

        for src, dests in adjacency_dict.items():
            src_str = str(src).strip()
            if src_str:
                self._all_nodes.add(src_str)
                for dst in dests:
                    dst_str = str(dst).strip()
                    if dst_str:
                        self._adj[src_str].append(dst_str)
                        self._destinations.add(dst_str)
                        self._all_nodes.add(dst_str)
                if self._adj[src_str]:
                    self._sources.add(src_str)
        self._is_loaded = True

    def load(self, force_reload: bool = False) -> None:
        """Parse elliptic_txs_edgelist.csv and construct outgoing adjacency lists.

        Args:
            force_reload: If True, re-reads the CSV from disk even if already loaded.
        """
        if self._is_loaded and not force_reload:
            return

        if not self.edgelist_path.exists():
            logger.warning(f"Elliptic edgelist CSV not found at {self.edgelist_path}")
            return

        logger.info(f"Loading Elliptic edgelist from {self.edgelist_path}...")
        self._adj = defaultdict(list)
        self._all_nodes = set()
        self._sources = set()
        self._destinations = set()

        with open(self.edgelist_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)  # Skip txId1,txId2 header
            for row in reader:
                if len(row) >= 2:
                    u = str(row[0]).strip()
                    v = str(row[1]).strip()
                    if u and v:
                        self._adj[u].append(v)
                        self._sources.add(u)
                        self._destinations.add(v)
                        self._all_nodes.add(u)
                        self._all_nodes.add(v)

        self._is_loaded = True
        logger.info(
            f"Loaded {len(self._all_nodes)} total unique nodes "
            f"({len(self._sources)} source nodes, {sum(len(v) for v in self._adj.values())} edges) "
            f"from {self.edgelist_path}"
        )

    @property
    def all_nodes(self) -> Set[str]:
        """Return set of all unique nodes (both sources and destinations) in the graph."""
        return self._all_nodes

    @property
    def source_nodes(self) -> Set[str]:
        """Return set of all source nodes (nodes with out-degree >= 1)."""
        return self._sources

    @property
    def adjacency(self) -> Dict[str, List[str]]:
        """Return the raw adjacency mapping."""
        return self._adj

    def get_transactions(
        self,
        address: str,
        session: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Synthesize a single transaction record for a given node containing all outgoing edges.

        For a source node `node_id`, creates a single transaction dictionary where:
        - `tx_hash = f"elliptic_node_tx::{node_id}"` (explicit synthetic prefix per source node)
        - `timestamp = None` (no fabricated timestamp)
        - `inputs = [{"address": node_id}]` (marks node_id as spender so is_spender passes in trace_hops)
        - `outputs = [{"address": dest_id, "value_btc": 0.0} for dest_id in outgoing_dests]`
          (all outgoing destination edges as separate outputs in a single transaction)

        Args:
            address: The stand-in node identifier (Elliptic txId string).
            session: Ignored network session parameter (matching fetcher.get_transactions signature).

        Returns:
            Single-element list `[tx]` containing the batched transaction, or `[]` if node has no outgoing edges.
        """
        clean_node = str(address).strip() if address else ""
        if not clean_node or clean_node not in self._adj:
            return []

        outgoing_dests = self._adj[clean_node]
        if not outgoing_dests:
            return []

        tx = {
            "tx_hash": f"elliptic_node_tx::{clean_node}",
            "timestamp": None,
            "inputs": [{"address": clean_node}],
            "outputs": [
                {"address": dest_id, "value_btc": 0.0}
                for dest_id in outgoing_dests
            ],
        }

        return [tx]


# Module-level singleton instance for convenient monkeypatching and direct usage
_DEFAULT_ADAPTER: Optional[EllipticGraphAdapter] = None


def get_adapter(edgelist_path: Optional[Union[str, Path]] = None) -> EllipticGraphAdapter:
    """Retrieve or initialize the global EllipticGraphAdapter instance."""
    global _DEFAULT_ADAPTER
    if _DEFAULT_ADAPTER is None or (edgelist_path and Path(edgelist_path) != _DEFAULT_ADAPTER.edgelist_path):
        _DEFAULT_ADAPTER = EllipticGraphAdapter(edgelist_path=edgelist_path)
    return _DEFAULT_ADAPTER


def get_transactions(
    address: str,
    session: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Fetcher-compatible entrypoint backed by the default EllipticGraphAdapter.

    Matches signature of `tracing_engine.fetcher.get_transactions`.
    """
    adapter = get_adapter()
    return adapter.get_transactions(address=address, session=session)
