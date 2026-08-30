"""VASP (Virtual Asset Service Provider) matching module (Task 5 Component).

Correlates queried Bitcoin addresses and co-clustered entity addresses against
a curated database of real, publicly documented exchange and custodian tags
(e.g., Binance, Bitfinex, Coinbase, Kraken, Bitstamp, Bittrex, Huobi, Poloniex).

Match Priority:
1. "direct_tag": The queried target address directly matches a verified VASP tag.
2. "cluster_match": An address co-clustered with the target belongs to a verified VASP tag.
3. "unresolved": No known VASP entity identified.

Forensic Note:
The VASP seed database (data/vasp_seed_list.json) is a small curated seed list
for hackathon demo/evaluation purposes only and does NOT represent complete or
comprehensive global VASP coverage.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

from tracing_engine.clustering import ClusterInfo
from tracing_engine.schema import MatchMethod

logger = logging.getLogger(__name__)

# Module-level cache for the VASP seed lookup dictionary
_VASP_SEED_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


class MatchResult(dict):
    """Result dictionary holding VASP matching outcome.
    
    Subclasses dict so it equals standard dicts (e.g. {"matched_vasp": ..., "match_method": ...})
    while also supporting clean 2-tuple unpacking (matched_vasp, match_method) for downstream orchestrators.
    """

    def __init__(self, matched_vasp: Optional[str], match_method: MatchMethod) -> None:
        super().__init__(matched_vasp=matched_vasp, match_method=match_method)

    def __iter__(self) -> Iterator[Any]:
        """Yield (matched_vasp, match_method) during unpacking."""
        yield self["matched_vasp"]
        yield self["match_method"]


def get_default_seed_file_path() -> Path:
    """Return the absolute filesystem path to data/vasp_seed_list.json."""
    return Path(__file__).resolve().parent.parent / "data" / "vasp_seed_list.json"


def load_seed_list(
    seed_file: Optional[Union[str, Path]] = None,
    force_reload: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """Load and parse the curated VASP seed list into an in-memory lookup dictionary.

    Args:
        seed_file: Optional custom file path to the JSON seed list.
        force_reload: If True, bypass the in-memory cache and re-read from disk.

    Returns:
        Dictionary mapping Bitcoin address string -> metadata dict:
        {
            "vasp_name": str,
            "source": str,
            "confidence": str,
            "notes": str
        }
    """
    global _VASP_SEED_CACHE

    if not force_reload and _VASP_SEED_CACHE is not None and seed_file is None:
        return _VASP_SEED_CACHE

    file_path = Path(seed_file) if seed_file else get_default_seed_file_path()

    if not file_path.exists():
        logger.warning(f"VASP seed list file not found at {file_path}")
        return {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read/parse VASP seed list at {file_path}: {e}")
        return {}

    seed_dict: Dict[str, Dict[str, Any]] = {}
    entries: List[Dict[str, Any]] = []

    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = data.get("entries", data.get("vasps", []))

    for entry in entries:
        if isinstance(entry, dict) and "address" in entry and "vasp_name" in entry:
            clean_addr = str(entry["address"]).strip()
            if clean_addr:
                seed_dict[clean_addr] = {
                    "vasp_name": str(entry["vasp_name"]).strip(),
                    "source": str(entry.get("source", "")).strip(),
                    "confidence": str(entry.get("confidence", "medium")).strip(),
                    "notes": str(entry.get("notes", "")).strip(),
                }

    if seed_file is None:
        _VASP_SEED_CACHE = seed_dict

    logger.debug(f"Loaded {len(seed_dict)} verified VASP seed records from {file_path}")
    return seed_dict


def match_vasp(
    address: Optional[str] = None,
    cluster_info: Optional[ClusterInfo] = None,
    *,
    query_address: Optional[str] = None,
    cluster: Optional[Any] = None,
    seed_dict: Optional[Dict[str, Dict[str, Any]]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Match a Bitcoin address or its co-clustered members against known VASP seeds.

    Matching Logic (in strict priority order):
    1. DIRECT: If `address` itself is in the seed list ->
       match_method = "direct_tag", matched_vasp = that entry's vasp_name.
    2. CLUSTER: If not a direct hit, but cluster_info is provided and ANY address
       in cluster_info.members is in the seed list ->
       match_method = "cluster_match", matched_vasp = that member's vasp_name.
    3. UNRESOLVED: Neither of the above ->
       match_method = "unresolved", matched_vasp = None.

    Args:
        address: The target Bitcoin address to match.
        cluster_info: Optional ClusterInfo containing co-clustered member addresses.
        query_address: Optional alias for `address` (keyword compatibility).
        cluster: Optional alias for `cluster_info` (keyword compatibility).
        seed_dict: Optional pre-loaded seed dictionary (useful for custom testing).
        **kwargs: Additional parameters gracefully ignored for decoupled forward compatibility.

    Returns:
        Dictionary conforming to the attribution specification:
        {
            "matched_vasp": str | None,
            "match_method": "direct_tag" | "cluster_match" | "unresolved"
        }
    """
    target_address = (address if address is not None else query_address) or ""
    clean_target = target_address.strip()

    active_cluster = cluster_info if cluster_info is not None else cluster
    seeds = seed_dict if seed_dict is not None else load_seed_list()

    # 1. DIRECT TAG MATCHING
    if clean_target and clean_target in seeds:
        matched_name = seeds[clean_target]["vasp_name"]
        logger.info(f"Direct VASP match found for '{clean_target}': {matched_name}")
        return MatchResult(
            matched_vasp=matched_name,
            match_method="direct_tag",
        )

    # 2. CLUSTER MATCHING
    if active_cluster is not None:
        members: List[str] = []
        if hasattr(active_cluster, "members"):
            members = active_cluster.members or []
        elif isinstance(active_cluster, (list, set, tuple)):
            members = list(active_cluster)
        elif isinstance(active_cluster, dict) and "members" in active_cluster:
            members = active_cluster.get("members") or []

        for member in members:
            clean_member = member.strip() if isinstance(member, str) else str(member)
            if clean_member and clean_member in seeds:
                matched_name = seeds[clean_member]["vasp_name"]
                logger.info(
                    f"Cluster VASP match found for target '{clean_target}' "
                    f"via clustered member '{clean_member}': {matched_name}"
                )
                return MatchResult(
                    matched_vasp=matched_name,
                    match_method="cluster_match",
                )

    # 3. UNRESOLVED
    return MatchResult(
        matched_vasp=None,
        match_method="unresolved",
    )
