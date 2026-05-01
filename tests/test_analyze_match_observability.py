#!/usr/bin/env python3
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_match_observability import (
    aggregate_matches,
    analyze_input,
    build_goal_events,
    build_goal_window,
    classify_ball_channel,
    classify_referee_family,
    classify_restart_context,
    collect_match_inputs,
    entered_box,
    entered_box_front,
    extract_log_paths,
    extract_result_paths,
    parse_rcl_events,
)


class AnalyzeMatchObservabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="obs_test_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    def test_extract_result_paths_from_summary(self) -> None:
        result_a = self.temp_dir / "results" / "a.txt"
        result_b = self.temp_dir / "results" / "b.txt"
        text = "\n".join(
            [
                "RoboCup 2D Fixed Baseline",
                f"  result: {result_a}",
                f"  result: {result_b}",
            ]
        )

        paths = extract_result_paths(text, self.temp_dir)

        self.assertEqual(paths, [result_a, result_b])

    def test_extract_log_paths_from_result(self) -> None:
        match_dir = self.temp_dir / "log" / "matches" / "match_001"
        text = f"Match 1: Aurora 1 - 0 Rival\n  logs: {match_dir}\n"

        paths = extract_log_paths(text, self.temp_dir)

        self.assertEqual(paths, [match_dir])

    def test_parse_rcl_events_and_goal_counts(self) -> None:
        rcl_path = self.temp_dir / "sample.rcl"
        rcl_path.write_text(
            "\n".join(
                [
                    "0,512\t(referee kick_off_l)",
                    "10,0\t(referee play_on)",
                    "220,0\t(referee goal_l_1)",
                    "221,0\t(referee kick_off_r)",
                    "250,0\t(referee play_on)",
                    "820,0\t(referee goal_r_1)",
                    "900,0\t(referee back_pass_l)",
                ]
            ),
            encoding="utf-8",
        )

        events = parse_rcl_events(rcl_path)
        goals = build_goal_events(events, "r")

        self.assertEqual(len(events), 7)
        self.assertEqual(len(goals), 2)
        self.assertEqual(goals[0].event_side, "against")
        self.assertEqual(goals[0].score_before_for, 0)
        self.assertEqual(goals[0].score_after_against, 1)
        self.assertEqual(goals[1].event_side, "for")
        self.assertEqual(goals[1].score_after_for, 1)
        self.assertEqual(classify_referee_family("back_pass_l"), "back_pass")

    def test_referee_family_covers_goalie_catch_and_indirect_free_kick(self) -> None:
        self.assertEqual(classify_referee_family("goalie_catch_ball_r"), "goalie_catch_ball")
        self.assertEqual(classify_referee_family("indirect_free_kick_l"), "setplay")
        self.assertEqual(classify_referee_family("drop_ball"), "drop_ball")
        self.assertEqual(classify_referee_family("half_time"), "time")
        self.assertEqual(classify_referee_family("time_over"), "time")
        self.assertEqual(classify_referee_family("yellow_card_r_10"), "card")

    def test_classify_restart_context_uses_last_non_play_on_event(self) -> None:
        events = [
            {"token": "kick_off_r"},
            {"token": "play_on"},
            {"token": "goal_l_1"},
        ]

        restart_context, preceding_mode, recent = classify_restart_context(events, 2)

        self.assertEqual(restart_context, "kick_off")
        self.assertEqual(preceding_mode, "play_on")
        self.assertEqual(recent, ["kick_off_r", "play_on"])

    def test_geometry_helpers_classify_channel_and_box_entry(self) -> None:
        left_flank = [{"x": -30.0, "y": -20.0}, {"x": -35.0, "y": -18.0}]
        center = [{"x": -30.0, "y": 0.0}, {"x": -35.0, "y": 5.0}]
        params = {"pitch_half_length": 52.5, "penalty_area_length": 16.5, "penalty_area_width": 40.32}

        self.assertEqual(classify_ball_channel(left_flank), "left_flank")
        self.assertEqual(classify_ball_channel(center), "center")
        self.assertTrue(entered_box([{"x": -37.0, "y": 0.0}], params))
        self.assertFalse(entered_box([{"x": -20.0, "y": 25.0}], params))
        self.assertTrue(entered_box_front([{"x": -33.0, "y": 10.0}], params))

    def test_build_goal_window_summarizes_geometry(self) -> None:
        events = [
            {"cycle": 0, "stopped_cycle": 0, "token": "kick_off_r"},
            {"cycle": 10, "stopped_cycle": 0, "token": "play_on"},
            {"cycle": 120, "stopped_cycle": 0, "token": "goal_l_1"},
        ]
        goals = build_goal_events(events, "r")
        snapshots = {
            100: {
                "cycle": 100,
                "ball": {"x": -32.0, "y": -18.0},
                "players": {
                    "r": {
                        1: {"x": -47.0, "y": 0.5},
                        2: {"x": -35.0, "y": -12.0},
                        3: {"x": -36.0, "y": -4.0},
                        4: {"x": -34.0, "y": 5.0},
                        5: {"x": -33.0, "y": 12.0},
                        6: {"x": -27.0, "y": -8.0},
                        7: {"x": -26.0, "y": 0.0},
                        8: {"x": -25.0, "y": 9.0},
                    },
                    "l": {9: {"x": -31.0, "y": -17.0}},
                },
            },
            120: {
                "cycle": 120,
                "ball": {"x": -38.0, "y": -16.0},
                "players": {
                    "r": {
                        1: {"x": -48.0, "y": 0.3},
                        2: {"x": -36.0, "y": -11.0},
                        3: {"x": -37.0, "y": -3.0},
                        4: {"x": -35.0, "y": 4.0},
                        5: {"x": -34.0, "y": 11.0},
                        6: {"x": -28.0, "y": -7.0},
                        7: {"x": -27.0, "y": 1.0},
                        8: {"x": -26.0, "y": 8.0},
                    },
                    "l": {9: {"x": -37.0, "y": -15.5}},
                },
            },
        }
        params = {"pitch_half_length": 52.5, "penalty_area_length": 16.5, "penalty_area_width": 40.32}

        window = build_goal_window(goals[0], events, snapshots, "r", params, 30)

        self.assertEqual(window["event_side"], "against")
        self.assertEqual(window["restart_context"], "kick_off")
        self.assertEqual(window["ball_channel"], "left_flank")
        self.assertTrue(window["entered_box"])
        self.assertEqual(window["nearest_our_player"]["unum"], 2)
        self.assertIsNotNone(window["goalie"])
        self.assertIsNotNone(window["defenders"])
        self.assertIsNotNone(window["midfielders"])

    def test_result_only_fallback_when_match_directory_is_missing(self) -> None:
        missing_match_dir = self.temp_dir / "logs" / "matches" / "gone_run" / "match_001"
        result_path = self.temp_dir / "results" / "missing_result.txt"
        result_path.parent.mkdir(parents=True)
        result_path.write_text(
            "\n".join(
                [
                    "RoboCup 2D Match Report",
                    "my_team: Aurora",
                    "opponent_key: rival",
                    "opponent_team: Rival",
                    "---",
                    "Match 1: Aurora 2 - 1 Rival",
                    f"  logs: {missing_match_dir}",
                    "  health: clean",
                    "  disconnects: 1",
                    "  timing_warnings: 2",
                    "  comm_warnings: 0",
                    "  opponent_actions: 3",
                ]
            ),
            encoding="utf-8",
        )

        report = analyze_input(result_path, None, 30)
        match = report["matches"][0]

        self.assertEqual(match["score_for"], 2)
        self.assertEqual(match["score_against"], 1)
        self.assertEqual(match["data_quality"]["availability"], "result_only")
        self.assertEqual(match["health"], "clean")
        self.assertEqual(match["goal_windows"], [])

    def test_result_only_fallback_when_match_directory_exists_but_records_are_missing(self) -> None:
        match_dir = self.temp_dir / "log" / "matches" / "existing_run" / "match_001"
        match_dir.mkdir(parents=True)

        result_path = self.temp_dir / "results" / "existing_missing_records.txt"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            "\n".join(
                [
                    "RoboCup 2D Match Report",
                    "my_team: Aurora",
                    "opponent_key: rival",
                    "opponent_team: Rival",
                    "---",
                    "Match 1: Aurora 3 - 2 Rival",
                    f"  logs: {match_dir}",
                    "  health: clean",
                    "  disconnects: 0",
                    "  timing_warnings: 0",
                    "  comm_warnings: 0",
                    "  opponent_actions: 1",
                ]
            ),
            encoding="utf-8",
        )

        report = analyze_input(result_path, None, 30)
        match = report["matches"][0]

        self.assertEqual(match["score_for"], 3)
        self.assertEqual(match["score_against"], 2)
        self.assertEqual(match["data_quality"]["availability"], "result_only")
        self.assertEqual(match["goal_windows"], [])

    def test_collect_match_inputs_from_summary_and_analyze_input(self) -> None:
        match_dir = self.temp_dir / "log" / "matches" / "demo_run" / "match_001"
        server_records = match_dir / "server_records"
        server_records.mkdir(parents=True)

        (server_records / "sample.rcg").write_text(
            "\n".join(
                [
                    "(server_param (pitch_half_length 52.5)(penalty_area_length 16.5)(penalty_area_width 40.32)(goal_width 14.02))",
                    "(team 1 Rival Aurora 0 0)",
                    "(show 100 ((b) 36 18 0 0) ((l 1) 0 0x1 47 0 0 0 0 0) ((l 9) 0 0x1 37 15 0 0 0 0) ((r 1) 0 0x1 48 -0.3 0 0 0 0) ((r 2) 0 0x1 36 11 0 0 0 0) ((r 3) 0 0x1 37 3 0 0 0 0) ((r 4) 0 0x1 35 -4 0 0 0 0) ((r 5) 0 0x1 34 -11 0 0 0 0) ((r 6) 0 0x1 28 7 0 0 0 0) ((r 7) 0 0x1 27 -1 0 0 0 0) ((r 8) 0 0x1 26 -8 0 0 0 0))",
                    "(show 120 ((b) 38 16 0 0) ((l 1) 0 0x1 47 0 0 0 0 0) ((l 9) 0 0x1 37 15.5 0 0 0 0) ((r 1) 0 0x1 48 -0.1 0 0 0 0) ((r 2) 0 0x1 36 11 0 0 0 0) ((r 3) 0 0x1 37 3 0 0 0 0) ((r 4) 0 0x1 35 -4 0 0 0 0) ((r 5) 0 0x1 34 -11 0 0 0 0) ((r 6) 0 0x1 28 7 0 0 0 0) ((r 7) 0 0x1 27 -1 0 0 0 0) ((r 8) 0 0x1 26 -8 0 0 0 0))",
                    "(team 120 Rival Aurora 1 0)",
                ]
            ),
            encoding="utf-8",
        )
        (server_records / "sample.rcl").write_text(
            "\n".join(
                [
                    "0,0\t(referee kick_off_l)",
                    "10,0\t(referee play_on)",
                    "120,0\t(referee goal_l_1)",
                ]
            ),
            encoding="utf-8",
        )
        (match_dir / "rcssserver.log").write_text(
            "\n".join(
                [
                    "'Rival' vs 'Aurora'",
                    "Score: 1 - 0",
                ]
            ),
            encoding="utf-8",
        )

        result_path = self.temp_dir / "results" / "demo_result.txt"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            "\n".join(
                [
                    "RoboCup 2D Match Report",
                    "my_team: Aurora",
                    "opponent_key: rival",
                    "opponent_team: Rival",
                    "experiment_profile: baseline",
                    "---",
                    "Match 1: Aurora 0 - 1 Rival",
                    f"  logs: {match_dir}",
                    "  health: clean",
                    "  disconnects: 0",
                    "  timing_warnings: 0",
                    "  comm_warnings: 0",
                    "  opponent_actions: 0",
                ]
            ),
            encoding="utf-8",
        )

        summary_path = self.temp_dir / "results" / "summary.txt"
        summary_path.write_text(
            "\n".join(
                [
                    "RoboCup 2D Fixed Baseline",
                    "run_label: sample",
                    "experiment_profile: baseline",
                    "---",
                    f"  result: {result_path}",
                ]
            ),
            encoding="utf-8",
        )

        match_inputs = collect_match_inputs(summary_path, None)
        report = analyze_input(summary_path, None, 30)
        aggregate = aggregate_matches(report["matches"])

        self.assertEqual(len(match_inputs), 1)
        self.assertEqual(report["summary"]["match_count"], 1)
        self.assertEqual(report["summary"]["goals_against"], 1)
        self.assertEqual(report["summary"]["early_goals_against_300"], 1)
        self.assertEqual(report["matches"][0]["goal_windows"][0]["ball_channel"], "left_flank")
        self.assertEqual(report["matches"][0]["referee_event_counts"]["goal"], 1)
        self.assertEqual(aggregate["conceded_restart_contexts"]["kick_off"], 1)


if __name__ == "__main__":
    unittest.main()
