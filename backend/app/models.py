from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from datetime import datetime, timezone
from .database import Base


class Case(Base):
    """
    One row per investigator query. `trace_json` stores the full TraceResult
    (hops, matched_vasp, confidence, match_method) exactly as produced by
    Person A's engine (or the sample generator, until that's plugged in).
    `risk_flags` is computed by this backend from the hops data.
    """
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    query_address = Column(String, index=True, nullable=False)
    matched_vasp = Column(String, nullable=True)
    confidence = Column(Float, nullable=False)
    match_method = Column(String, nullable=False)
    risk_flags = Column(JSON, nullable=False, default=list)
    trace_json = Column(JSON, nullable=False)  # full TraceResult dict
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
