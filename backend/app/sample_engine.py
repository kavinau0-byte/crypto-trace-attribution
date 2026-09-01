"""
STAND-IN for Person A's tracing engine.

Per Section 3 of the plan: "Person B's entire backend/dashboard is built
against this shape from day one, using hand-written sample trace results
until Person A's real engine is ready to plug in."

This module fakes `trace_address()` with deterministic, semi-randomized
sample data so the rest of the backend (DB, API, risk engine, PDF report)
can be built and tested independently right now.

SWAP-OUT POINT: once Person A's real module is ready, replace the body of
`trace_address()` with a call into their module, e.g.:

    from tracing_engine import trace_address as real_trace_address
    def trace_address(address, max_hops=5):
        return real_trace_address(address, max_hops=max_hops)

Everything downstream (risk_engine, database, report_generator) already
consumes the same TraceResult shape, so no other code needs to change.
"""
import hashlib
import random
from datetime import datetime, timedelta, timezone

KNOWN_VASPS = ["Binance", "Coinbase", "Kraken", None, None]  # None = unresolved, weighted


def _seeded_random(address: str) -> random.Random:
    # Deterministic per-address so repeated demo queries look stable
    seed = int(hashlib.sha256(address.encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def _fake_address(rng: random.Random) -> str:
    chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    return "1" + "".join(rng.choice(chars) for _ in range(33))


def _fake_txhash(rng: random.Random) -> str:
    return "".join(rng.choice("0123456789abcdef") for _ in range(64))


def trace_address(address: str, max_hops: int = 5) -> dict:
    """
    Returns a TraceResult-shaped dict for `address`, matching Section 3
    of the build plan exactly. Replace with the real engine call once
    Person A's module is ready (see module docstring).
    """
    rng = _seeded_random(address)
    n_hops = rng.randint(2, max_hops)

    start = datetime.now(timezone.utc) - timedelta(days=1)
    hops = []
    current_time = start
    for i in range(n_hops):
        # occasionally simulate a fan-out (two edges leaving the same hop_index)
        branch = rng.random() < 0.15
        edges_this_hop = 2 if branch else 1
        for _ in range(edges_this_hop):
            current_time += timedelta(minutes=rng.randint(2, 240))
            hops.append({
                "hop_index": i,
                "address": _fake_address(rng),
                "tx_hash": _fake_txhash(rng),
                "timestamp": current_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "amount_btc": round(rng.uniform(0.001, 2.5), 6),
            })

    matched_vasp = rng.choice(KNOWN_VASPS)
    if matched_vasp:
        match_method = rng.choice(["direct_tag", "cluster_match"])
        confidence = round(rng.uniform(0.55, 0.97), 2)
    else:
        match_method = "unresolved"
        confidence = round(rng.uniform(0.05, 0.4), 2)

    return {
        "query_address": address,
        "chain": "bitcoin",
        "hops": hops,
        "matched_vasp": matched_vasp,
        "confidence": confidence,
        "match_method": match_method,
        # risk_flags intentionally omitted here — Person B's risk_engine
        # computes that from the hops, not the tracing engine.
    }
