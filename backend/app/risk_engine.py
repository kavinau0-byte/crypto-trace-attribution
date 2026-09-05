"""
Risk-flag rule engine (Person B's responsibility per the plan).

Takes the `hops` list from a TraceResult and computes risk_flags using
simple, explainable heuristics. These are an honest first pass, not a
claimed solved detector (per Section 1 of the build plan).

Tunable thresholds live at the top of this file so they're easy to adjust
once you benchmark against real Elliptic examples later (Section 6 stretch:
"tune thresholds against labeled examples" rather than guessed cutoffs).
"""
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Optional

# --- Thresholds (starting guesses; refine later against real data) ---
RAPID_HOP_SECONDS = 600          # < 10 min between consecutive hops = "rapid"
RAPID_HOP_FRACTION = 0.5         # if >=50% of hops are "rapid", flag it
HIGH_FANOUT_COUNT = 3            # >=3 outgoing edges from one address = fan-out


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    """Parse a contract timestamp, or return None when there isn't one.

    `timestamp` is Optional[str] in the contract (tracing_engine/schema.py):
    an unconfirmed transaction has no block time yet, so mempool.space
    reports it as None. That is normal, expected data — not an error — and
    a pending transaction simply carries no time signal to reason about.
    """
    if not ts:
        return None
    # Handles "...Z" suffix (UTC) from the contract's timestamp format
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def compute_risk_flags(hops: List[Dict]) -> List[str]:
    if not hops:
        return []

    flags = []

    # Sort by hop_index in case the engine returns them out of order
    sorted_hops = sorted(hops, key=lambda h: h["hop_index"])

    # --- rapid_hopping: check time gaps between consecutive hops ---
    if len(sorted_hops) >= 2:
        gaps = []
        for a, b in zip(sorted_hops, sorted_hops[1:]):
            try:
                ts_a = _parse_ts(a["timestamp"])
                ts_b = _parse_ts(b["timestamp"])
            except (ValueError, KeyError):
                continue
            # An unconfirmed hop has no block time, so this pair yields no
            # measurable gap. Skip it rather than inventing one — the
            # remaining pairs still decide the rapid_hopping fraction.
            if ts_a is None or ts_b is None:
                continue
            gaps.append((ts_b - ts_a).total_seconds())
        if gaps:
            rapid_count = sum(1 for g in gaps if 0 <= g < RAPID_HOP_SECONDS)
            if rapid_count / len(gaps) >= RAPID_HOP_FRACTION:
                flags.append("rapid_hopping")

    # --- high_fanout: multiple hops branching from the same source address ---
    # Supports engines that emit >1 hop per hop_index for branching paths.
    fanout_by_index = defaultdict(set)
    for h in sorted_hops:
        fanout_by_index[h["hop_index"]].add(h["address"])
    if any(len(addrs) >= HIGH_FANOUT_COUNT for addrs in fanout_by_index.values()):
        flags.append("high_fanout")

    # --- possible_mixer: rapid hopping + high fan-out together is the
    #     classic tumbler signature (many quick, split transfers) ---
    if "rapid_hopping" in flags and "high_fanout" in flags:
        flags.append("possible_mixer")

    return flags
