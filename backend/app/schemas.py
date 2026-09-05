"""
Pydantic schemas.

TraceResult mirrors the JSON contract from Section 3 of the build plan EXACTLY.
This is the shape Person A's tracing engine must return, and the shape this
backend consumes. Do not change field names/types here without re-syncing
with Person A.
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class Hop(BaseModel):
    hop_index: int
    address: str
    tx_hash: str
    # Optional to match tracing_engine/schema.py: an unconfirmed transaction
    # has no block time yet, so the engine emits None here.
    timestamp: Optional[str] = None  # ISO 8601, e.g. "2026-09-01T10:08:32Z"
    amount_btc: float
    # The address that sent this hop's funds. The engine records the BFS node it
    # was walking, so consumers can draw the real from->to edge instead of
    # guessing which address at the previous level paid. Optional so hop records
    # stored before the field existed still validate.
    from_address: Optional[str] = None


class TraceResult(BaseModel):
    query_address: str
    chain: str = "bitcoin"
    hops: List[Hop]
    matched_vasp: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    match_method: str  # "direct_tag" | "cluster_match" | "unresolved"
    risk_flags: List[str] = []


class TraceRequest(BaseModel):
    address: str
    max_hops: int = 4


class CaseSummary(BaseModel):
    id: int
    query_address: str
    matched_vasp: Optional[str]
    confidence: float
    risk_flags: List[str]
    created_at: str


class CaseDetail(CaseSummary):
    trace: TraceResult
