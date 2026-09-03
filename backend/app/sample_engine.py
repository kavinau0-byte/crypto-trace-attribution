"""
Wraps Person A's real tracing engine for use by the FastAPI backend.

This module used to contain a STAND-IN that faked `trace_address()` with
deterministic, semi-randomized sample data (per Section 3 of the build
plan: "Person B's entire backend/dashboard is built against this shape
from day one, using hand-written sample trace results until Person A's
real engine is ready to plug in.") That fake data path has now been
swapped out -- see git history on this file if you need to reference the
old randomized-data version for any reason.

Person A's real entrypoint is `tracing_engine.engine.trace_wallet`. This
module keeps the local name `trace_address` so nothing else in this
backend (main.py, schemas.py, risk_engine.py, report_generator.py) needed
to change at swap time.

Everything downstream (risk_engine, database, report_generator) consumes
the same TraceResult shape the real engine returns, so no other code
needed to change either.

NOTE: since real VASP attribution only covers a curated seed list of 45
addresses across 12 exchanges (see data/vasp_seed_list.json), most real
addresses traced through this endpoint will now correctly come back with
matched_vasp: null and match_method: "unresolved" -- that is expected,
real behavior, not a bug. The old fake data used to always resolve to
something for demo purposes; the real engine does not.
"""
from tracing_engine.engine import trace_wallet


def trace_address(address: str, max_hops: int = 4) -> dict:
    """
    Calls Person A's real tracing engine and returns its TraceResult-shaped
    dict directly. See module docstring for the swap-out history.
    """
    return trace_wallet(address, max_hops=max_hops)
