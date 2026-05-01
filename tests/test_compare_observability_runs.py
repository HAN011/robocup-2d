#!/usr/bin/env python3
from __future__ import annotations

import unittest

from scripts.compare_observability_runs import build_rows, count_back_passes, summarize_report


class CompareObservabilityRunsTest(unittest.TestCase):
    def test_count_back_passes_uses_our_side(self) -> None:
        match = {
            "our_side": "r",
            "referee_events": [
                {"token": "back_pass_l"},
                {"token": "back_pass_r"},
                {"token": "back_pass_r"},
            ],
        }

        self.assertEqual(count_back_passes(match), 2)

    def test_count_back_passes_uses_referee_token_counts(self) -> None:
        match = {
            "our_side": "l",
            "referee_event_tokens": {
                "back_pass_l": 3,
                "back_pass_r": 2,
                "free_kick_l": 1,
            },
        }

        self.assertEqual(count_back_passes(match), 3)

    def test_build_rows_compares_total_and_opponent_deltas(self) -> None:
        baseline = summarize_report(
            {
                "_source_path": "baseline_observability.json",
                "matches": [
                    {
                        "experiment_profile": "exp_o_guarded_light_box_finish_tight",
                        "opponent_key": "starter2d",
                        "score_for": 0,
                        "score_against": 5,
                        "our_side": "r",
                        "referee_events": [{"token": "back_pass_r"}],
                        "goal_windows": [{"cycle": 250}, {"cycle": 900}],
                        "health": "ok",
                        "disconnects": 0,
                        "timing_warnings": 1,
                    }
                ],
            }
        )
        candidate = summarize_report(
            {
                "_source_path": "candidate_observability.json",
                "matches": [
                    {
                        "experiment_profile": "candidate_12",
                        "opponent_key": "starter2d",
                        "score_for": 1,
                        "score_against": 4,
                        "our_side": "r",
                        "referee_events": [],
                        "goal_windows": [{"cycle": 700}],
                        "health": "ok",
                        "disconnects": 0,
                        "timing_warnings": 3,
                    }
                ],
            }
        )

        rows = build_rows(baseline, [candidate])
        total = rows[0]
        opponent = rows[1]

        self.assertEqual(total["scope"], "total")
        self.assertEqual(total["profile"], "candidate_12")
        self.assertEqual(total["delta_gf"], 1)
        self.assertEqual(total["delta_ga"], -1)
        self.assertEqual(total["delta_gd"], 2)
        self.assertEqual(total["delta_back_pass"], -1)
        self.assertEqual(total["delta_early_ga_300"], -1)
        self.assertEqual(total["delta_early_ga_1000"], -1)
        self.assertEqual(opponent["opponent"], "starter2d")
        self.assertEqual(opponent["delta_timing_warnings"], 2)


if __name__ == "__main__":
    unittest.main()
