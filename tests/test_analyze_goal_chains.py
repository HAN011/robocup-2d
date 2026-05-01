#!/usr/bin/env python3
from __future__ import annotations

import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_goal_chains import (
    InputGroup,
    build_summary,
    load_goal_chain_rows,
    resolve_observability_csv,
)


FIELDNAMES = [
    "match_label",
    "match_dir",
    "team_name",
    "opponent_team",
    "opponent_key",
    "run_label",
    "experiment_profile",
    "score_for",
    "score_against",
    "health",
    "disconnects",
    "timing_warnings",
    "comm_warnings",
    "opponent_actions",
    "goal_window_index",
    "goal_event_side",
    "goal_goal_cycle",
    "goal_score_before_for",
    "goal_score_before_against",
    "goal_score_after_for",
    "goal_score_after_against",
    "goal_restart_context",
    "goal_ball_channel",
    "goal_entered_box",
    "goal_entered_box_front",
    "goal_goalie_final_x",
    "goal_goalie_final_y",
    "goal_defenders_avg_depth",
    "goal_defenders_avg_width",
    "goal_midfielders_avg_depth",
    "goal_midfielders_avg_width",
    "goal_midfield_defense_gap",
    "goal_nearest_our_player_unum",
    "goal_nearest_our_player_distance",
    "goal_nearest_opponent_player_unum",
    "goal_nearest_opponent_player_distance",
]


class AnalyzeGoalChainsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="goal_chains_test_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    def write_observability_csv(self, stem: str, rows: list[dict[str, str]]) -> Path:
        path = self.temp_dir / f"{stem}_observability.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            for row in rows:
                base = {field: "" for field in FIELDNAMES}
                base.update(row)
                writer.writerow(base)
        return path

    def test_resolve_summary_to_sibling_observability_csv(self) -> None:
        summary = self.temp_dir / "parallel_fixed_baseline_run.txt"
        summary.write_text("summary\n", encoding="utf-8")
        csv_path = self.write_observability_csv("parallel_fixed_baseline_run", [])

        self.assertEqual(resolve_observability_csv(summary), csv_path)

    def test_goal_rows_classify_center_kickoff_gap(self) -> None:
        csv_path = self.write_observability_csv(
            "run_a",
            [
                {
                    "match_label": "match_001",
                    "opponent_key": "cyrus2d",
                    "goal_window_index": "1",
                    "goal_event_side": "against",
                    "goal_goal_cycle": "900",
                    "goal_restart_context": "kick_off",
                    "goal_ball_channel": "center",
                    "goal_entered_box": "True",
                    "goal_midfield_defense_gap": "13.2",
                    "goal_nearest_our_player_unum": "3",
                }
            ],
        )

        rows = load_goal_chain_rows([InputGroup("low", (csv_path,))])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["mechanism_cluster"], "center_kickoff_midfield_gap")
        self.assertEqual(rows[0]["nearest_our_band"], "defender")
        self.assertEqual(rows[0]["box_entry_cycle"], "unavailable_in_observability_csv")

    def test_summary_marks_clusters_above_ten_percent_gate(self) -> None:
        csv_path = self.write_observability_csv(
            "run_b",
            [
                {
                    "match_label": "match_001",
                    "opponent_key": "foxsy_cyrus",
                    "goal_window_index": str(index),
                    "goal_event_side": "against",
                    "goal_goal_cycle": str(1000 + index),
                    "goal_restart_context": "kick_off",
                    "goal_ball_channel": "center",
                    "goal_entered_box": "True",
                    "goal_midfield_defense_gap": "12.5",
                    "goal_nearest_our_player_unum": "2",
                }
                for index in range(1, 11)
            ],
        )
        rows = load_goal_chain_rows([InputGroup("all", (csv_path,))])

        summary = build_summary(rows, ["all"], min_improvement_pct=0.10, baseline_goals=89)
        eligible = summary["groups"]["all"]["experiment_eligible_clusters"]

        self.assertEqual(summary["groups"]["all"]["goals_against"], 10)
        self.assertEqual(eligible[0]["cluster"], "center_kickoff_midfield_gap")


if __name__ == "__main__":
    unittest.main()
