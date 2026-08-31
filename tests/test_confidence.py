"""Unit tests for the Task 6 attribution confidence scoring module."""

import math
import unittest

from tracing_engine.confidence import (
    BASE_SCORE_CLUSTER_MATCH,
    BASE_SCORE_DIRECT_TAG,
    BASE_SCORE_UNRESOLVED,
    CLUSTER_MODIFIER_BASE,
    CLUSTER_MODIFIER_MAX,
    CLUSTER_MODIFIER_SLOPE,
    HOP_DECAY_FACTOR,
    SOURCE_CONFIDENCE_DEFAULT,
    SOURCE_CONFIDENCE_HIGH,
    SOURCE_CONFIDENCE_LOW,
    SOURCE_CONFIDENCE_MEDIUM,
    _base_score,
    _cluster_modifier,
    _hop_decay,
    _source_confidence_modifier,
    calculate_confidence,
)


class TestConfidenceScoring(unittest.TestCase):
    """Test suite for calculate_confidence and individual formula components."""

    # --------------------------------------------------------------------------
    # 1. Direct tag baseline tests
    # --------------------------------------------------------------------------

    def test_direct_tag_hop_0_max_score(self):
        """Verify direct_tag at hop 0 produces expected max-ish score (~0.9)."""
        score = calculate_confidence(
            match_method="direct_tag",
            hop_index=0,
            cluster_size=None,
            seed_entry_confidence=None,
        )
        self.assertAlmostEqual(score, 0.9, places=6)

        # With high source confidence rating
        score_high = calculate_confidence(
            match_method="direct_tag",
            hop_index=0,
            seed_entry_confidence="high",
        )
        self.assertAlmostEqual(score_high, 0.9, places=6)

    # --------------------------------------------------------------------------
    # 2. Direct tag vs Cluster match relative ranking
    # --------------------------------------------------------------------------

    def test_cluster_match_scores_lower_than_direct_tag(self):
        """Verify cluster_match scores strictly lower than equivalent direct_tag at same hop."""
        for hop in [0, 1, 2, 3]:
            direct_score = calculate_confidence(
                match_method="direct_tag",
                hop_index=hop,
            )
            # Even with large cluster reinforcing score, cluster match base is 0.5 vs 0.9
            cluster_score_max = calculate_confidence(
                match_method="cluster_match",
                hop_index=hop,
                cluster_size=20,
                seed_entry_confidence="high",
            )
            cluster_score_min = calculate_confidence(
                match_method="cluster_match",
                hop_index=hop,
                cluster_size=0,
                seed_entry_confidence="low",
            )
            self.assertGreater(
                direct_score,
                cluster_score_max,
                f"direct_tag at hop {hop} should exceed cluster_match (max reinforcement)",
            )
            self.assertGreater(
                direct_score,
                cluster_score_min,
                f"direct_tag at hop {hop} should exceed cluster_match (min reinforcement)",
            )

    # --------------------------------------------------------------------------
    # 3. Unresolved match method tests
    # --------------------------------------------------------------------------

    def test_unresolved_always_returns_zero(self):
        """Verify unresolved always returns exactly 0.0 regardless of other inputs."""
        test_cases = [
            (0, None, None),
            (0, 10, "high"),
            (1, 0, "low"),
            (5, 50, "medium"),
            (10, 100, "high"),
        ]
        for hop, cluster_sz, seed_conf in test_cases:
            score = calculate_confidence(
                match_method="unresolved",
                hop_index=hop,
                cluster_size=cluster_sz,
                seed_entry_confidence=seed_conf,
            )
            self.assertEqual(score, 0.0, f"Unresolved at hop={hop} must be 0.0")

    # --------------------------------------------------------------------------
    # 4. Hop decay strict decrease (no floor / no plateauing)
    # --------------------------------------------------------------------------

    def test_hop_decay_strictly_decreases_without_floor(self):
        """Verify increasing hop_index strictly decreases score and never plateaus at a floor."""
        previous_score = calculate_confidence("direct_tag", hop_index=0)
        self.assertAlmostEqual(previous_score, 0.9, places=6)

        # Check consecutive hops from 1 to 20 to ensure continuous decay
        for hop in range(1, 21):
            current_score = calculate_confidence("direct_tag", hop_index=hop)
            self.assertLess(
                current_score,
                previous_score,
                f"Score at hop {hop} ({current_score}) must be strictly less than hop {hop - 1} ({previous_score})",
            )
            # Pure exponential decay formula: 0.9 * (0.8 ** hop)
            expected_score = 0.9 * (0.8 ** hop)
            self.assertAlmostEqual(
                current_score,
                expected_score,
                places=7,
                msg=f"Hop {hop} did not match exact exponential decay",
            )
            # Score must remain positive (no zeroing out prematurely)
            self.assertGreater(current_score, 0.0)
            previous_score = current_score

    # --------------------------------------------------------------------------
    # 5. Modifiers never return zero
    # --------------------------------------------------------------------------

    def test_modifiers_never_return_zero_at_weakest_inputs(self):
        """Verify cluster_modifier and source_confidence_modifier never return 0.0."""
        # Weakest cluster modifier: cluster_size = 0
        weak_cluster_mod = _cluster_modifier(cluster_size=0, match_method="cluster_match")
        self.assertEqual(weak_cluster_mod, 0.7)
        self.assertGreater(weak_cluster_mod, 0.0)

        # Weakest source confidence modifier: "low"
        weak_source_mod = _source_confidence_modifier("low")
        self.assertEqual(weak_source_mod, 0.7)
        self.assertGreater(weak_source_mod, 0.0)

        # Combined weakest cluster match at hop 0
        weakest_cluster_score = calculate_confidence(
            match_method="cluster_match",
            hop_index=0,
            cluster_size=0,
            seed_entry_confidence="low",
        )
        # Expected: 0.5 * 1.0 * 0.7 * 0.7 = 0.245
        self.assertAlmostEqual(weakest_cluster_score, 0.245, places=6)
        self.assertGreater(weakest_cluster_score, 0.0)

    # --------------------------------------------------------------------------
    # 6. Clamping within [0.0, 1.0]
    # --------------------------------------------------------------------------

    def test_output_always_clamped_in_unit_interval(self):
        """Verify calculated confidence is always within [0.0, 1.0]."""
        matrix = [
            ("direct_tag", 0, None, "high"),
            ("direct_tag", 0, 100, "high"),
            ("direct_tag", 10, None, "low"),
            ("cluster_match", 0, 50, "high"),
            ("cluster_match", 5, 0, "low"),
            ("unresolved", 0, None, None),
        ]
        for method, hop, c_size, s_conf in matrix:
            score = calculate_confidence(
                match_method=method,
                hop_index=hop,
                cluster_size=c_size,
                seed_entry_confidence=s_conf,
            )
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)

    # --------------------------------------------------------------------------
    # 7. Invalid input error handling
    # --------------------------------------------------------------------------

    def test_invalid_match_method_raises_value_error(self):
        """Verify passing an invalid match_method raises a clear ValueError."""
        invalid_methods = ["direct", "cluster", "random_string", "", "DIRECT_TAG", None]
        for invalid in invalid_methods:
            with self.assertRaises(ValueError):
                calculate_confidence(match_method=invalid, hop_index=0)

    def test_negative_hop_index_raises_value_error(self):
        """Verify negative hop_index raises a ValueError."""
        with self.assertRaises(ValueError):
            calculate_confidence(match_method="direct_tag", hop_index=-1)
            
    def test_negative_hop_index_raises_even_when_unresolved(self):
        """Verify negative hop_index still raises when match_method is 'unresolved',
        i.e. the base==0.0 short-circuit must not silently swallow invalid input."""
        with self.assertRaises(ValueError):
            calculate_confidence(match_method="unresolved", hop_index=-1)

    def test_negative_cluster_size_raises_value_error(self):
        """Verify negative cluster_size raises a ValueError when cluster_match is evaluated."""
        with self.assertRaises(ValueError):
            calculate_confidence(
                match_method="cluster_match",
                hop_index=0,
                cluster_size=-5,
            )

    # --------------------------------------------------------------------------
    # 8. Detailed unit tests for individual components
    # --------------------------------------------------------------------------

    def test_base_score_constants(self):
        """Verify _base_score returns exact named constants."""
        self.assertEqual(_base_score("direct_tag"), BASE_SCORE_DIRECT_TAG)
        self.assertEqual(_base_score("cluster_match"), BASE_SCORE_CLUSTER_MATCH)
        self.assertEqual(_base_score("unresolved"), BASE_SCORE_UNRESOLVED)

    def test_cluster_modifier_behavior(self):
        """Verify _cluster_modifier formula: min(1.0, 0.7 + 0.05 * cluster_size)."""
        # Neutral if match_method != cluster_match
        self.assertEqual(_cluster_modifier(0, "direct_tag"), 1.0)
        self.assertEqual(_cluster_modifier(10, "unresolved"), 1.0)
        self.assertEqual(_cluster_modifier(None, "cluster_match"), 1.0)

        # Formula checks for cluster_match
        self.assertAlmostEqual(_cluster_modifier(0, "cluster_match"), 0.70)
        self.assertAlmostEqual(_cluster_modifier(1, "cluster_match"), 0.75)
        self.assertAlmostEqual(_cluster_modifier(2, "cluster_match"), 0.80)
        self.assertAlmostEqual(_cluster_modifier(4, "cluster_match"), 0.90)
        self.assertAlmostEqual(_cluster_modifier(6, "cluster_match"), 1.00)
        # Clamped at 1.0 for large clusters
        self.assertEqual(_cluster_modifier(10, "cluster_match"), 1.00)
        self.assertEqual(_cluster_modifier(100, "cluster_match"), 1.00)

    def test_source_confidence_modifier_behavior(self):
        """Verify _source_confidence_modifier mappings and case-insensitivity."""
        self.assertEqual(_source_confidence_modifier(None), SOURCE_CONFIDENCE_DEFAULT)
        self.assertEqual(_source_confidence_modifier(""), SOURCE_CONFIDENCE_DEFAULT)
        self.assertEqual(_source_confidence_modifier("high"), SOURCE_CONFIDENCE_HIGH)
        self.assertEqual(_source_confidence_modifier("HIGH"), SOURCE_CONFIDENCE_HIGH)
        self.assertEqual(_source_confidence_modifier("  High  "), SOURCE_CONFIDENCE_HIGH)
        self.assertEqual(_source_confidence_modifier("medium"), SOURCE_CONFIDENCE_MEDIUM)
        self.assertEqual(_source_confidence_modifier("Medium"), SOURCE_CONFIDENCE_MEDIUM)
        self.assertEqual(_source_confidence_modifier("low"), SOURCE_CONFIDENCE_LOW)
        self.assertEqual(_source_confidence_modifier("LOW"), SOURCE_CONFIDENCE_LOW)
        # Fallback for unrecognized values
        self.assertEqual(_source_confidence_modifier("unknown_rating"), SOURCE_CONFIDENCE_DEFAULT)

    # --------------------------------------------------------------------------
    # 9. Deterministic end-to-end calculations
    # --------------------------------------------------------------------------

    def test_exact_end_to_end_calculations(self):
        """Verify full formula for multi-hop scenarios with diverse modifiers."""
        # Case A: direct_tag at hop 1 with medium seed confidence
        # 0.9 * (0.8 ** 1 = 0.8) * 1.0 * 0.85 = 0.612
        score_a = calculate_confidence(
            match_method="direct_tag",
            hop_index=1,
            seed_entry_confidence="medium",
        )
        self.assertAlmostEqual(score_a, 0.612, places=6)

        # Case B: cluster_match at hop 2, cluster_size=2, high seed confidence
        # 0.5 * (0.8 ** 2 = 0.64) * (0.7 + 0.05*2 = 0.8) * 1.0 = 0.256
        score_b = calculate_confidence(
            match_method="cluster_match",
            hop_index=2,
            cluster_size=2,
            seed_entry_confidence="high",
        )
        self.assertAlmostEqual(score_b, 0.256, places=6)

        # Case C: cluster_match at hop 3, cluster_size=6 (max modifier 1.0), low seed confidence
        # 0.5 * (0.8 ** 3 = 0.512) * 1.0 * 0.7 = 0.1792
        score_c = calculate_confidence(
            match_method="cluster_match",
            hop_index=3,
            cluster_size=6,
            seed_entry_confidence="low",
        )
        self.assertAlmostEqual(score_c, 0.1792, places=6)


if __name__ == "__main__":
    unittest.main()
