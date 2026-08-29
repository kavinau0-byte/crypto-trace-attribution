"""Schema definitions for the SIH26182 Tracing Engine.

Defines the exact JSON output contract required for integration between
Person A (Tracing Engine) and Person B (Platform / Dashboard / Risk).
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Literal, Dict, Any

# Match methods supported by the attribution pipeline
MatchMethod = Literal["direct_tag", "cluster_match", "unresolved"]


@dataclass
class HopInfo:
    """Represents a single forward transfer hop in the Bitcoin transaction graph.
    
    Attributes:
        hop_index: 0-indexed distance from the queried seed address.
        address: The destination Bitcoin address reached at this hop.
        tx_hash: The transaction identifier (txid) linking the hop.
        timestamp: ISO-8601 UTC timestamp string (e.g. '2026-09-01T10:08:32Z') or None if unconfirmed.
        amount_btc: The amount transferred to the destination address in BTC.
    """
    hop_index: int
    address: str
    tx_hash: str
    timestamp: Optional[str]
    amount_btc: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert HopInfo to a standard dictionary."""
        return asdict(self)


@dataclass
class TraceResult:
    """The master JSON contract returned by trace_wallet().
    
    This contract is the strict integration boundary between Person A and Person B.
    
    Ownership:
        - query_address, chain, hops, matched_vasp, confidence, match_method -> Owned by Person A
        - risk_flags -> Owned by Person B (Person A always initializes as empty list `[]`)
    """
    query_address: str
    chain: str = "bitcoin"
    hops: List[HopInfo] = field(default_factory=list)
    matched_vasp: Optional[str] = None
    confidence: float = 0.0
    match_method: MatchMethod = "unresolved"
    risk_flags: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert TraceResult into the exact JSON-compatible dictionary contract."""
        return {
            "query_address": self.query_address,
            "chain": self.chain,
            "hops": [
                hop.to_dict() if isinstance(hop, HopInfo) else hop
                for hop in self.hops
            ],
            "matched_vasp": self.matched_vasp,
            "confidence": round(float(self.confidence), 4),
            "match_method": self.match_method,
            "risk_flags": self.risk_flags,
        }
