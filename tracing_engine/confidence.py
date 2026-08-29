"""Attribution confidence scoring module (Day 5-6 Component).

Calculates a transparent, deterministic, and explainable confidence score [0.0 - 1.0]
for VASP attributions.

================================================================================
CONFIDENCE SCORING FORMULA SPECIFICATION:
================================================================================
Confidence scoring must NEVER be an opaque black-box or fabricated guess.
The planned formula for Days 5-6 uses explicit forensic signals:

1. Direct Tag on Query Address (Hop 0):
   - Base Confidence: 0.98 (near-certainty for verified exchange deposit/hot wallets)
   
2. Direct Tag on Downstream Hop (Hop Distance Decay):
   - Formula: Confidence = Base * (DecayFactor ^ hop_index)
   - With Base = 0.95, DecayFactor = 0.85:
     - Hop 0: 0.95
     - Hop 1: 0.81
     - Hop 2: 0.69
     - Hop 3: 0.58
     - Hop 4: 0.49

3. Cluster Match:
   - Base Confidence: 0.85
   - Cluster Quality Discount: Penalized if cluster size is excessively large (potential mixing/CoinJoin contamination).

4. Unresolved:
   - Confidence = 0.00
================================================================================
"""

import logging
from typing import Optional
from tracing_engine.schema import MatchMethod

logger = logging.getLogger(__name__)


def calculate_confidence(
    match_method: MatchMethod,
    matched_vasp: Optional[str] = None,
    hop_distance: Optional[int] = None,
    cluster_size: int = 1
) -> float:
    """Compute a transparent attribution confidence score based on evidence quality and hop distance.
    
    # TODO(Day 5-6): Implement transparent confidence scoring formula
    # 1. If match_method == "unresolved" or matched_vasp is None -> return 0.0
    # 2. If match_method == "direct_tag":
    #      hop = hop_distance if hop_distance is not None else 0
    #      return round(0.95 * (0.85 ** hop), 4)
    # 3. If match_method == "cluster_match":
    #      cluster_penalty = 0.10 if cluster_size > 50 else 0.0
    #      return round(max(0.0, 0.85 - cluster_penalty), 4)
    
    Args:
        match_method: Attribution method ('direct_tag', 'cluster_match', or 'unresolved').
        matched_vasp: Name of the identified VASP, if any.
        hop_distance: 0-indexed hop distance where the VASP match occurred (0 for direct address match).
        cluster_size: Number of addresses in the attributed entity cluster.
        
    Returns:
        Float confidence score between 0.0 and 1.0 (returns 0.0 in this stub version).
    """
    logger.debug(
        f"[Stub Day 5-6] Confidence calculation requested: method={match_method}, "
        f"vasp={matched_vasp}, hop={hop_distance}, cluster_size={cluster_size}"
    )

    # Placeholder return: 0.0 until Day 5-6 implementation
    return 0.0
