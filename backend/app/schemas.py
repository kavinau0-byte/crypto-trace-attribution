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
    timestamp: str  # ISO 8601, e.g. "2026-09-01T10:08:32Z"
    amount_btc: float


class TraceResult(BaseModel):
    query_address: str
    chain: str = "bitcoin"
    hops: List[Hop]
    matched_vasp: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    match_method: str  # "direct_tag" | "cluster_proximity" | "unresolved"
    risk_flags: List[str] = []


class TraceRequest(BaseModel):
    address: str
    max_hops: int = 5


class CaseSummary(BaseModel):
    id: int
    query_address: str
    matched_vasp: Optional[str]
    confidence: float
    risk_flags: List[str]
    created_at: str


class CaseDetail(CaseSummary):
    trace: TraceResult
