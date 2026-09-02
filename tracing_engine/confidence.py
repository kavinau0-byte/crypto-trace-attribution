"""Attribution confidence scoring module (Task 6 Component).

Calculates a transparent, deterministic, formula-based confidence score [0.0 - 1.0]
representing evidence strength for VASP attributions.

================================================================================
FORENSIC & METHODOLOGICAL SPECIFICATION:
================================================================================
1. What this score represents:
   This confidence score represents EVIDENCE STRENGTH FOR INVESTIGATIVE LEADS,
   NOT a calibrated statistical probability of ground truth. A higher score
   reflects stronger, closer, and more reliable forensic indicators connecting
   a queried wallet to an identified VASP entity.

2. The four signals used and their rationale:
   - Base Score (match_method): Captures the foundational evidence quality of
     how the attribution was established (direct verified tag vs. heuristic
     multi-input cluster match vs. unresolved).
   - Hop Decay (hop_index): Models diminishing investigative certainty as funds
     propagate across sequential forward transaction hops from the origin.
   - Cluster Modifier (cluster_size): Modulates evidence strength for cluster-based
     matches; larger co-spending clusters reinforce the entity attribution
     without zeroing out smaller clusters.
   - Source Confidence Modifier (seed_entry_confidence): Reflects the upstream
     provenance and verification quality of the specific VASP seed list entry
     (e.g., official proof-of-reserves disclosure vs. single-source tracker).

3. Prototype calibration notice:
   All weights, multipliers, and decay factors in this module are HAND-PICKED
   STARTING POINTS for a hackathon prototype, NOT statistically validated or
   calibrated values derived from labeled ground-truth datasets.

4. Legal & Investigative disclaimer:
   A high confidence score represents investigative lead strength, NOT legal or
   factual proof of identity, wallet ownership, control, or illicit wrongdoing.
================================================================================
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ==============================================================================
# NAMED CONSTANTS (Hand-picked hackathon prototype starting points)
# ==============================================================================

# Base confidence scores per attribution match method.
# Hand-picked hackathon prototype starting points representing relative evidence strength:
# - BASE_SCORE_DIRECT_TAG (0.9): Direct match against verified seed list provides strongest initial lead.
# - BASE_SCORE_CLUSTER_MATCH (0.5): Common-input-ownership heuristic match introduces moderate uncertainty.
# - BASE_SCORE_UNRESOLVED (0.0): No VASP match found, zero attribution evidence.
BASE_SCORE_DIRECT_TAG: float = 0.9
BASE_SCORE_CLUSTER_MATCH: float = 0.5
BASE_SCORE_UNRESOLVED: float = 0.0

# Exponential decay factor per transaction hop distance.
# Hand-picked hackathon prototype starting point (0.8 decay per hop).
# Multiplied as (0.8 ** hop_index). Deliberately has NO FLOOR / NO CLAMP to allow
# the score to approach zero for distant forwarding hops without plateauing.
HOP_DECAY_FACTOR: float = 0.8

# Cluster size modifier constants for cluster matches.
# Hand-picked hackathon prototype starting points.
# Formula: min(1.0, 0.7 + 0.05 * cluster_size)
# - CLUSTER_MODIFIER_BASE (0.7): Floor modifier ensuring a small cluster (cluster_size ≈ 0)
#   does not zero out an otherwise valid cluster match (weak evidence, but non-zero).
# - CLUSTER_MODIFIER_SLOPE (0.05): Incremental reinforcement per additional clustered address.
# - CLUSTER_MODIFIER_MAX (1.0): Upper ceiling ensuring modifier never inflates beyond neutral 1.0.
CLUSTER_MODIFIER_BASE: float = 0.7
CLUSTER_MODIFIER_SLOPE: float = 0.05
CLUSTER_MODIFIER_MAX: float = 1.0

# Source confidence modifier weights based on seed list entry rating.
# Hand-picked hackathon prototype starting points.
# IMPORTANT: This modifier reflects the upstream reliability of the seed database entry itself
# ("how confident we are this seed-list address really belongs to this VASP"), which is distinct
# from the overall trace confidence score ("how confident we are this trace correctly reaches it").
# - SOURCE_CONFIDENCE_HIGH (1.0): Official proof-of-reserves or multi-source verified label.
# - SOURCE_CONFIDENCE_MEDIUM (0.85): Reputable community/forensics tracker label.
# - SOURCE_CONFIDENCE_LOW (0.7): Single-source or uncorroborated label (never returns 0).
# - SOURCE_CONFIDENCE_DEFAULT (1.0): Neutral modifier when seed confidence is absent/unspecified.
SOURCE_CONFIDENCE_HIGH: float = 1.0
SOURCE_CONFIDENCE_MEDIUM: float = 0.85
SOURCE_CONFIDENCE_LOW: float = 0.7
SOURCE_CONFIDENCE_DEFAULT: float = 1.0


# ==============================================================================
# PRIVATE HELPER FUNCTIONS
# ==============================================================================

def _base_score(match_method: str) -> float:
    """Return base confidence score for a given match method.

    Args:
        match_method: Attribution method ('direct_tag', 'cluster_match', or 'unresolved').

    Returns:
        Base confidence float.

    Raises:
        ValueError: If match_method is not one of the expected valid methods.
    """
    if match_method == "direct_tag":
        return BASE_SCORE_DIRECT_TAG
    if match_method == "cluster_match":
        return BASE_SCORE_CLUSTER_MATCH
    if match_method == "unresolved":
        return BASE_SCORE_UNRESOLVED

    raise ValueError(
        f"Invalid match_method '{match_method}'. "
        "Expected 'direct_tag', 'cluster_match', or 'unresolved'."
    )


def _hop_decay(hop_index: int) -> float:
    """Calculate pure exponential hop decay factor based on distance.

    Args:
        hop_index: 0-based hop index (0 for seed / query address).

    Returns:
        Exponential decay multiplier in (0.0, 1.0].

    Raises:
        ValueError: If hop_index is negative or not an integer.
    """
    if not isinstance(hop_index, int) or isinstance(hop_index, bool) or hop_index < 0:
        raise ValueError(f"hop_index must be a non-negative integer, got {hop_index!r}")

    # Pure exponential decay with no floor/clamp — intentionally allowed to
    # approach zero for very distant hops without plateauing.
    return float(HOP_DECAY_FACTOR ** hop_index)


def _cluster_modifier(cluster_size: Optional[int], match_method: str) -> float:
    """Calculate cluster size modifier for cluster-based attributions.

    Args:
        cluster_size: Total address count in the identified entity cluster, or None.
        match_method: Attribution method string.

    Returns:
        Modifier float in [0.7, 1.0]. Never returns 0.0.

    Raises:
        ValueError: If cluster_size is negative.
    """
    # Only meaningfully applies when match_method == "cluster_match" and cluster_size is provided
    if match_method != "cluster_match" or cluster_size is None:
        return 1.0

    if not isinstance(cluster_size, int) or isinstance(cluster_size, bool) or cluster_size < 0:
        raise ValueError(f"cluster_size must be a non-negative integer, got {cluster_size!r}")

    # Formula: min(1.0, 0.7 + 0.05 * cluster_size)
    # A small cluster is weaker evidence, but should not zero out an otherwise valid match (floor is 0.7).
    modifier = CLUSTER_MODIFIER_BASE + (CLUSTER_MODIFIER_SLOPE * cluster_size)
    return float(min(CLUSTER_MODIFIER_MAX, modifier))


def _source_confidence_modifier(seed_entry_confidence: Optional[str]) -> float:
    """Calculate modifier based on the upstream VASP seed entry confidence rating.

    IMPORTANT: This reflects how confident we are that the seed-list address really
    belongs to this VASP (data provenance), which is distinct from the overall trace
    confidence score (investigative reach strength).

    Args:
        seed_entry_confidence: Optional string ('high', 'medium', 'low') from the seed list entry.

    Returns:
        Modifier float in [0.7, 1.0]. Never returns 0.0.
    """
    if seed_entry_confidence is None:
        return SOURCE_CONFIDENCE_DEFAULT

    cleaned = str(seed_entry_confidence).strip().lower()
    if not cleaned:
        return SOURCE_CONFIDENCE_DEFAULT

    if cleaned == "high":
        return SOURCE_CONFIDENCE_HIGH
    if cleaned == "medium":
        return SOURCE_CONFIDENCE_MEDIUM
    if cleaned == "low":
        return SOURCE_CONFIDENCE_LOW

    logger.warning(
        f"Unrecognized seed_entry_confidence '{seed_entry_confidence}', "
        f"falling back to default {SOURCE_CONFIDENCE_DEFAULT}"
    )
    return SOURCE_CONFIDENCE_DEFAULT


# ==============================================================================
# PUBLIC ENTRYPOINT
# ==============================================================================

def calculate_confidence(
    match_method: str,
    hop_index: int,
    cluster_size: Optional[int] = None,
    seed_entry_confidence: Optional[str] = None,
) -> float:
    """Returns a transparent, formula-based confidence score in [0.0, 1.0]

    representing evidence strength for a VASP match — NOT a calibrated
    statistical probability of ground truth. See module docstring for
    full explanation of signals and limitations.

    Formula:
        confidence = base_score(match_method)
                      * hop_decay(hop_index)
                      * cluster_modifier(cluster_size, match_method)
                      * source_confidence_modifier(seed_entry_confidence)
        confidence = clamp(confidence, 0.0, 1.0)

    Args:
        match_method: Attribution method ('direct_tag', 'cluster_match', or 'unresolved').
        hop_index: 0-indexed distance where the VASP match occurred (0 for seed address).
        cluster_size: Optional number of addresses in the entity cluster.
        seed_entry_confidence: Optional confidence tag ('high', 'medium', 'low') from seed list.

    Returns:
        Float confidence score clamped to [0.0, 1.0].

    Raises:
        ValueError: If match_method is invalid or hop_index is negative.
    """
    base = _base_score(match_method)

    # Validate hop_index unconditionally (even for unresolved matches) so
    # invalid input always raises, rather than being silently swallowed by
    # the base == 0.0 short-circuit below.
    decay = _hop_decay(hop_index)

    if base == 0.0:
        return 0.0
        
    cluster_mod = _cluster_modifier(cluster_size, match_method)
    source_mod = _source_confidence_modifier(seed_entry_confidence)

    raw_confidence = base * decay * cluster_mod * source_mod
    clamped_confidence = max(0.0, min(1.0, float(raw_confidence)))

    logger.debug(
        f"Confidence calculated: {clamped_confidence:.4f} "
        f"(base={base}, decay={decay:.4f}, cluster_mod={cluster_mod:.2f}, source_mod={source_mod:.2f})"
    )

    return clamped_confidence
