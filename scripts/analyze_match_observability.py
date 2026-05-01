#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results"

NUM_PATTERN = r"[-+]?\d+(?:\.\d+)?"
RESULT_PATH_RE = re.compile(r"^\s*result:\s*(.+?)\s*$")
LOG_PATH_RE = re.compile(r"^\s*logs:\s*(.+?)\s*$")
MATCH_LINE_RE = re.compile(r"^Match\s+(\d+):\s+(.+?)\s+(\d+)\s+-\s+(\d+)\s+(.+?)\s*$")
TOP_KV_RE = re.compile(r"^([A-Za-z0-9_]+):\s*(.*?)\s*$")
INDENTED_KV_RE = re.compile(r"^\s+([A-Za-z0-9_]+):\s*(.*?)\s*$")
RCL_REFEREE_RE = re.compile(r"^(\d+),(\d+)\s+\(referee\s+([^)]+)\)")
TEAM_LINE_RE = re.compile(r"^\(team\s+\d+\s+(\S+)\s+(\S+)\s+(\d+)\s+(\d+)\)\s*$")
PLAYMODE_LINE_RE = re.compile(r"^\(playmode\s+\(playmode\s+(\d+)\s+([^)]+)\)\)\s*$")
SHOW_LINE_RE = re.compile(r"^\(show\s+(\d+)\s+")
BALL_RE = re.compile(r"\(\(b\)\s+(%s)\s+(%s)(?:\s+(%s)\s+(%s))?\)" % ((NUM_PATTERN,) * 4))
PLAYER_RE = re.compile(r"\(\(([lr])\s+(\d+)\)\s+\S+\s+\S+\s+(%s)\s+(%s)" % (NUM_PATTERN, NUM_PATTERN))
SERVER_PARAM_LINE_RE = re.compile(r"^\(server_param\s+(.*)\)\s*$")
SERVER_PARAM_VALUE_RE = re.compile(r"\(([A-Za-z0-9_]+)\s+([^)]+)\)")
GOAL_TOKEN_RE = re.compile(r"^goal_([lr])(?:_(\d+))?$")
TEAM_VS_RE = re.compile(r"'([^']+)'\s+vs\s+'([^']+)'")
SERVER_SCORE_RE = re.compile(r"Score:\s*(\d+)\s*-\s*(\d+)")

DEFAULT_SERVER_PARAMS = {
    "pitch_half_length": 52.5,
    "penalty_area_length": 16.5,
    "penalty_area_width": 40.32,
    "goal_width": 14.02,
}

SETPLAY_PREFIXES = (
    "kick_in",
    "corner_kick",
    "goal_kick",
    "free_kick",
    "ind_free_kick",
    "indirect_free_kick",
    "goalie_catch_ball",
    "offside",
    "back_pass",
    "catch_fault",
    "illegal_defense",
    "foul_",
    "free_kick_fault",
)


@dataclass
class MatchInput:
    match_dir: Path
    source_path: Path
    result_path: Path | None = None
    my_team: str | None = None
    opponent_team: str | None = None
    opponent_key: str | None = None
    run_label: str | None = None
    experiment_profile: str | None = None
    score_for: int | None = None
    score_against: int | None = None
    health: str | None = None
    disconnects: int = 0
    timing_warnings: int = 0
    comm_warnings: int = 0
    opponent_actions: int = 0


@dataclass
class GoalEvent:
    cycle: int
    stopped_cycle: int
    token: str
    scoring_side: str
    event_side: str
    score_before_for: int
    score_before_against: int
    score_after_for: int
    score_after_against: int
    event_index: int


class ObservabilityError(RuntimeError):
    pass


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def resolve_path(raw_path: str, base_dir: Path) -> Path:
    path = Path(raw_path.strip())
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    if not path.exists():
        raw = str(path)
        if "/logs/matches/" in raw:
            candidate = Path(raw.replace("/logs/matches/", "/log/matches/", 1))
            if candidate.exists():
                return candidate
    return path


def unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def parse_top_metadata(text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "---":
            break
        if line.startswith("  "):
            continue
        match = TOP_KV_RE.match(stripped)
        if match:
            metadata[match.group(1)] = match.group(2)
    return metadata


def extract_result_paths(text: str, base_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for line in text.splitlines():
        match = RESULT_PATH_RE.match(line)
        if match:
            paths.append(resolve_path(match.group(1), base_dir))
    return unique_paths(paths)


def extract_log_paths(text: str, base_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for line in text.splitlines():
        match = LOG_PATH_RE.match(line)
        if match:
            paths.append(resolve_path(match.group(1), base_dir))
    return unique_paths(paths)


def parse_result_file(path: Path) -> tuple[dict[str, str], list[dict[str, Any]]]:
    text = read_text(path)
    top_metadata = parse_top_metadata(text)
    match_blocks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        match_line = MATCH_LINE_RE.match(line)
        if match_line:
            if current is not None:
                match_blocks.append(current)
            current = {
                "match_index": int(match_line.group(1)),
                "line_my_team": match_line.group(2),
                "line_my_score": int(match_line.group(3)),
                "line_opp_score": int(match_line.group(4)),
                "line_opp_team": match_line.group(5),
            }
            continue
        if current is None:
            continue
        kv_match = INDENTED_KV_RE.match(raw_line)
        if kv_match:
            current[kv_match.group(1)] = kv_match.group(2).strip()

    if current is not None:
        match_blocks.append(current)
    return top_metadata, match_blocks


def collect_match_inputs_from_result(path: Path) -> list[MatchInput]:
    top_metadata, match_blocks = parse_result_file(path)
    inputs: list[MatchInput] = []

    for block in match_blocks:
        log_dir_raw = block.get("logs")
        if not log_dir_raw:
            continue
        inputs.append(
            MatchInput(
                match_dir=resolve_path(log_dir_raw, path.parent),
                source_path=path,
                result_path=path,
                my_team=top_metadata.get("my_team") or block.get("line_my_team"),
                opponent_team=top_metadata.get("opponent_team") or block.get("line_opp_team"),
                opponent_key=top_metadata.get("opponent_key"),
                run_label=top_metadata.get("run_label"),
                experiment_profile=top_metadata.get("experiment_profile"),
                score_for=block.get("line_my_score"),
                score_against=block.get("line_opp_score"),
                health=block.get("health"),
                disconnects=to_int(block.get("disconnects"), default=0),
                timing_warnings=to_int(block.get("timing_warnings"), default=0),
                comm_warnings=to_int(block.get("comm_warnings"), default=0),
                opponent_actions=to_int(block.get("opponent_actions"), default=0),
            )
        )
    return inputs


def collect_match_inputs(source_path: Path, explicit_team_name: str | None) -> list[MatchInput]:
    if source_path.is_dir():
        return [MatchInput(match_dir=source_path, source_path=source_path, my_team=explicit_team_name)]

    if not source_path.is_file():
        raise ObservabilityError(f"input not found: {source_path}")

    text = read_text(source_path)
    result_paths = extract_result_paths(text, source_path.parent)
    if result_paths:
        collected: list[MatchInput] = []
        summary_metadata = parse_top_metadata(text)
        for result_path in result_paths:
            if not result_path.is_file():
                continue
            for item in collect_match_inputs_from_result(result_path):
                if item.run_label is None:
                    item.run_label = summary_metadata.get("run_label")
                if item.experiment_profile is None:
                    item.experiment_profile = summary_metadata.get("experiment_profile")
                if item.my_team is None:
                    item.my_team = explicit_team_name
                collected.append(item)
        if collected:
            return collected

    result_inputs = collect_match_inputs_from_result(source_path)
    if result_inputs:
        if explicit_team_name:
            for item in result_inputs:
                if item.my_team is None:
                    item.my_team = explicit_team_name
        return result_inputs

    log_paths = extract_log_paths(text, source_path.parent)
    if log_paths:
        top_metadata = parse_top_metadata(text)
        return [
            MatchInput(
                match_dir=path,
                source_path=source_path,
                my_team=explicit_team_name or top_metadata.get("my_team"),
                run_label=top_metadata.get("run_label"),
                experiment_profile=top_metadata.get("experiment_profile"),
            )
            for path in log_paths
        ]

    raise ObservabilityError(f"unsupported input format: {source_path}")


def to_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 3)


def maybe_round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 3)


def parse_server_params(rcg_path: Path | None) -> dict[str, float]:
    params = dict(DEFAULT_SERVER_PARAMS)
    if rcg_path is None or not rcg_path.is_file():
        return params

    with rcg_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            match = SERVER_PARAM_LINE_RE.match(line)
            if not match:
                continue
            for key, value in SERVER_PARAM_VALUE_RE.findall(match.group(1)):
                parsed = to_float(value)
                if parsed is not None:
                    params[key] = parsed
            break
    return params


def parse_rcg_metadata(rcg_path: Path | None) -> dict[str, Any]:
    metadata = {
        "left_team": None,
        "right_team": None,
        "left_score": None,
        "right_score": None,
        "playmodes": [],
        "server_params": parse_server_params(rcg_path),
    }
    if rcg_path is None or not rcg_path.is_file():
        return metadata

    first_team: tuple[str, str, int, int] | None = None
    last_team: tuple[str, str, int, int] | None = None
    playmodes: list[dict[str, Any]] = []

    with rcg_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            team_match = TEAM_LINE_RE.match(line)
            if team_match:
                team_tuple = (
                    team_match.group(1),
                    team_match.group(2),
                    int(team_match.group(3)),
                    int(team_match.group(4)),
                )
                if first_team is None:
                    first_team = team_tuple
                last_team = team_tuple
                continue
            playmode_match = PLAYMODE_LINE_RE.match(line)
            if playmode_match:
                playmodes.append({
                    "cycle": int(playmode_match.group(1)),
                    "token": playmode_match.group(2).strip().lower(),
                })

    selected = last_team or first_team
    if selected is not None:
        metadata.update(
            {
                "left_team": selected[0],
                "right_team": selected[1],
                "left_score": selected[2],
                "right_score": selected[3],
            }
        )
    metadata["playmodes"] = playmodes
    return metadata


def parse_server_log_metadata(server_log_path: Path | None) -> dict[str, Any]:
    metadata = {"left_team": None, "right_team": None, "left_score": None, "right_score": None}
    if server_log_path is None or not server_log_path.is_file():
        return metadata

    team_names: tuple[str, str] | None = None
    score: tuple[int, int] | None = None
    with server_log_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if team_names is None:
                match = TEAM_VS_RE.search(line)
                if match:
                    team_names = (match.group(1), match.group(2))
                    continue
            score_match = SERVER_SCORE_RE.search(line)
            if score_match:
                score = (int(score_match.group(1)), int(score_match.group(2)))
    if team_names is not None:
        metadata["left_team"] = team_names[0]
        metadata["right_team"] = team_names[1]
    if score is not None:
        metadata["left_score"] = score[0]
        metadata["right_score"] = score[1]
    return metadata


def choose_team_name(explicit_team_name: str | None, match_input: MatchInput, team_names: tuple[str | None, str | None]) -> str | None:
    if explicit_team_name:
        return explicit_team_name
    if match_input.my_team:
        return match_input.my_team
    left_team, right_team = team_names
    if left_team == "Aurora" or right_team == "Aurora":
        return "Aurora"
    return None


def determine_our_side(team_name: str | None, left_team: str | None, right_team: str | None) -> str | None:
    if team_name is None:
        return None
    if team_name == left_team:
        return "l"
    if team_name == right_team:
        return "r"
    return None


def parse_rcl_events(rcl_path: Path | None) -> list[dict[str, Any]]:
    if rcl_path is None or not rcl_path.is_file():
        return []

    events: list[dict[str, Any]] = []
    with rcl_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            match = RCL_REFEREE_RE.match(raw_line.strip())
            if not match:
                continue
            events.append(
                {
                    "cycle": int(match.group(1)),
                    "stopped_cycle": int(match.group(2)),
                    "token": match.group(3).strip().lower(),
                }
            )
    return events


def classify_referee_family(token: str) -> str:
    if token == "play_on":
        return "play_on"
    if token == "before_kick_off":
        return "before_kick_off"
    if token.startswith("goal_l") or token.startswith("goal_r"):
        return "goal"
    if token.startswith("kick_off"):
        return "kick_off"
    if token.startswith("back_pass"):
        return "back_pass"
    if token.startswith("goalie_catch_ball"):
        return "goalie_catch_ball"
    if token.startswith("catch_fault"):
        return "catch_fault"
    if token.startswith("illegal_defense"):
        return "illegal_defense"
    if token.startswith("yellow_card") or token.startswith("red_card"):
        return "card"
    if token.startswith("foul") or token.startswith("free_kick_fault"):
        return "foul"
    if token == "drop_ball":
        return "drop_ball"
    if token in ("half_time", "time_over", "time_up"):
        return "time"
    if token.startswith(SETPLAY_PREFIXES):
        return "setplay"
    return "other"


def build_goal_events(events: list[dict[str, Any]], our_side: str | None) -> list[GoalEvent]:
    goals: list[GoalEvent] = []
    left_score = 0
    right_score = 0

    for index, event in enumerate(events):
        match = GOAL_TOKEN_RE.match(event["token"])
        if not match:
            continue
        scoring_side = match.group(1)
        explicit_score = to_int(match.group(2))

        if scoring_side == "l":
            new_left = explicit_score if explicit_score is not None else left_score + 1
            new_right = right_score
        else:
            new_left = left_score
            new_right = explicit_score if explicit_score is not None else right_score + 1

        if our_side == "l":
            score_before_for, score_before_against = left_score, right_score
            score_after_for, score_after_against = new_left, new_right
            event_side = "for" if scoring_side == "l" else "against"
        elif our_side == "r":
            score_before_for, score_before_against = right_score, left_score
            score_after_for, score_after_against = new_right, new_left
            event_side = "for" if scoring_side == "r" else "against"
        else:
            score_before_for = score_before_against = score_after_for = score_after_against = -1
            event_side = scoring_side

        goals.append(
            GoalEvent(
                cycle=event["cycle"],
                stopped_cycle=event["stopped_cycle"],
                token=event["token"],
                scoring_side=scoring_side,
                event_side=event_side,
                score_before_for=score_before_for,
                score_before_against=score_before_against,
                score_after_for=score_after_for,
                score_after_against=score_after_against,
                event_index=index,
            )
        )
        left_score, right_score = new_left, new_right
    return goals


def normalize_point(x: float, y: float, our_side: str | None) -> tuple[float, float]:
    if our_side == "r":
        return -x, -y
    return x, y


def load_window_snapshots(rcg_path: Path | None, goal_cycles: list[int], our_side: str | None, window_size: int) -> dict[int, dict[str, Any]]:
    if rcg_path is None or not rcg_path.is_file() or not goal_cycles:
        return {}

    needed_cycles: set[int] = set()
    for goal_cycle in goal_cycles:
        start_cycle = max(1, goal_cycle - window_size)
        needed_cycles.update(range(start_cycle, goal_cycle + 1))

    snapshots: dict[int, dict[str, Any]] = {}
    with rcg_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            show_match = SHOW_LINE_RE.match(line)
            if not show_match:
                continue
            cycle = int(show_match.group(1))
            if cycle not in needed_cycles:
                continue
            snapshot = parse_show_snapshot(line, cycle, our_side)
            if snapshot is not None:
                snapshots[cycle] = snapshot
    return snapshots


def parse_show_snapshot(line: str, cycle: int, our_side: str | None) -> dict[str, Any] | None:
    ball_match = BALL_RE.search(line)
    if ball_match is None:
        return None

    ball_x, ball_y = normalize_point(float(ball_match.group(1)), float(ball_match.group(2)), our_side)
    players: dict[str, dict[int, dict[str, float]]] = {"l": {}, "r": {}}

    for player_match in PLAYER_RE.finditer(line):
        side = player_match.group(1)
        unum = int(player_match.group(2))
        x, y = normalize_point(float(player_match.group(3)), float(player_match.group(4)), our_side)
        players[side][unum] = {"x": round(x, 3), "y": round(y, 3)}

    return {
        "cycle": cycle,
        "ball": {"x": round(ball_x, 3), "y": round(ball_y, 3)},
        "players": players,
    }


def classify_restart_context(events: list[dict[str, Any]], goal_event_index: int) -> tuple[str, str | None, list[str]]:
    previous_tokens = [events[i]["token"] for i in range(max(0, goal_event_index - 5), goal_event_index)]
    preceding_mode = events[goal_event_index - 1]["token"] if goal_event_index > 0 else None

    play_on_index: int | None = None
    for index in range(goal_event_index - 1, -1, -1):
        if events[index]["token"] == "play_on":
            play_on_index = index
            break

    seed_token = preceding_mode
    if play_on_index is not None:
        for index in range(play_on_index - 1, -1, -1):
            candidate = events[index]["token"]
            if candidate == "play_on":
                continue
            seed_token = candidate
            break

    if seed_token is None:
        return "other", preceding_mode, previous_tokens
    if seed_token == "before_kick_off":
        return "before_kick_off", preceding_mode, previous_tokens
    if seed_token.startswith("kick_off"):
        return "kick_off", preceding_mode, previous_tokens
    if seed_token.startswith("goal_l") or seed_token.startswith("goal_r"):
        return "after_goal", preceding_mode, previous_tokens
    if seed_token.startswith(SETPLAY_PREFIXES):
        return "setplay", preceding_mode, previous_tokens
    if seed_token == "play_on":
        return "play_on", preceding_mode, previous_tokens
    return "other", preceding_mode, previous_tokens


def build_goal_window(
    goal: GoalEvent,
    events: list[dict[str, Any]],
    snapshots: dict[int, dict[str, Any]],
    our_side: str,
    server_params: dict[str, float],
    window_size: int,
) -> dict[str, Any]:
    start_cycle = max(1, goal.cycle - window_size)
    window_snapshots = [snapshots[cycle] for cycle in sorted(snapshots) if start_cycle <= cycle <= goal.cycle]
    restart_context, preceding_mode, recent_referee_events = classify_restart_context(events, goal.event_index)
    availability = "complete" if window_snapshots else "unavailable"

    result = {
        "event_side": goal.event_side,
        "goal_cycle": goal.cycle,
        "stopped_cycle": goal.stopped_cycle,
        "score_before": {"for": goal.score_before_for, "against": goal.score_before_against},
        "score_after": {"for": goal.score_after_for, "against": goal.score_after_against},
        "referee_goal_token": goal.token,
        "preceding_referee_mode": preceding_mode,
        "recent_referee_events": recent_referee_events,
        "restart_context": restart_context,
        "window_start_cycle": start_cycle,
        "window_end_cycle": goal.cycle,
        "snapshot_count": len(window_snapshots),
        "availability": availability,
        "ball_channel": "unavailable",
        "entered_box": None,
        "entered_box_front": None,
        "goalie": None,
        "defenders": None,
        "midfielders": None,
        "midfield_defense_gap": None,
        "nearest_our_player": None,
        "nearest_opponent_player": None,
    }

    if not window_snapshots:
        return result

    our_players_side = our_side
    opponent_side = "r" if our_side == "l" else "l"
    ball_points = [snapshot["ball"] for snapshot in window_snapshots]
    last_snapshot = window_snapshots[-1]

    result["ball_channel"] = classify_ball_channel(ball_points)
    result["entered_box"] = entered_box(ball_points, server_params)
    result["entered_box_front"] = entered_box_front(ball_points, server_params)
    result["goalie"] = summarize_goalie(window_snapshots, our_players_side)
    result["defenders"] = summarize_line(window_snapshots, our_players_side, [2, 3, 4, 5])
    result["midfielders"] = summarize_line(window_snapshots, our_players_side, [6, 7, 8])
    defenders_depth = None if result["defenders"] is None else result["defenders"].get("avg_depth")
    midfielders_depth = None if result["midfielders"] is None else result["midfielders"].get("avg_depth")
    if defenders_depth is not None and midfielders_depth is not None:
        result["midfield_defense_gap"] = round(midfielders_depth - defenders_depth, 3)
    result["nearest_our_player"] = nearest_player(last_snapshot, our_players_side)
    result["nearest_opponent_player"] = nearest_player(last_snapshot, opponent_side)
    return result


def classify_ball_channel(ball_points: list[dict[str, float]]) -> str:
    if not ball_points:
        return "unavailable"
    counts = Counter()
    for point in ball_points:
        y = point["y"]
        if y <= -15.0:
            counts["left_flank"] += 1
        elif y >= 15.0:
            counts["right_flank"] += 1
        else:
            counts["center"] += 1
    return counts.most_common(1)[0][0] if counts else "unavailable"


def entered_box(ball_points: list[dict[str, float]], server_params: dict[str, float]) -> bool:
    penalty_line_x = -server_params["pitch_half_length"] + server_params["penalty_area_length"]
    penalty_half_width = server_params["penalty_area_width"] / 2.0
    return any(point["x"] <= penalty_line_x and abs(point["y"]) <= penalty_half_width for point in ball_points)


def entered_box_front(ball_points: list[dict[str, float]], server_params: dict[str, float]) -> bool:
    penalty_line_x = -server_params["pitch_half_length"] + server_params["penalty_area_length"]
    penalty_half_width = server_params["penalty_area_width"] / 2.0
    return any(point["x"] <= penalty_line_x + 5.0 and abs(point["y"]) <= penalty_half_width + 5.0 for point in ball_points)


def summarize_goalie(window_snapshots: list[dict[str, Any]], side: str) -> dict[str, Any] | None:
    goalie_samples: list[dict[str, float]] = []
    for snapshot in window_snapshots:
        goalie = snapshot["players"].get(side, {}).get(1)
        if goalie is not None:
            goalie_samples.append(goalie)
    if not goalie_samples:
        return None
    final_goalie = goalie_samples[-1]
    return {
        "avg_x": safe_mean([sample["x"] for sample in goalie_samples]),
        "avg_y": safe_mean([sample["y"] for sample in goalie_samples]),
        "final_x": maybe_round(final_goalie["x"]),
        "final_y": maybe_round(final_goalie["y"]),
    }


def summarize_line(window_snapshots: list[dict[str, Any]], side: str, unums: list[int]) -> dict[str, Any] | None:
    mean_depths: list[float] = []
    widths: list[float] = []
    deepest_values: list[float] = []
    highest_values: list[float] = []

    for snapshot in window_snapshots:
        positions = [snapshot["players"].get(side, {}).get(unum) for unum in unums]
        positions = [position for position in positions if position is not None]
        if not positions:
            continue
        xs = [position["x"] for position in positions]
        ys = [position["y"] for position in positions]
        mean_depths.append(sum(xs) / len(xs))
        widths.append((max(ys) - min(ys)) if len(ys) >= 2 else 0.0)
        deepest_values.append(min(xs))
        highest_values.append(max(xs))

    if not mean_depths:
        return None
    return {
        "avg_depth": safe_mean(mean_depths),
        "avg_width": safe_mean(widths),
        "deepest_x": maybe_round(min(deepest_values)),
        "highest_x": maybe_round(max(highest_values)),
    }


def nearest_player(snapshot: dict[str, Any], side: str) -> dict[str, Any] | None:
    ball = snapshot["ball"]
    best_unum: int | None = None
    best_distance: float | None = None
    best_position: dict[str, float] | None = None

    for unum, position in snapshot["players"].get(side, {}).items():
        distance = ((position["x"] - ball["x"]) ** 2 + (position["y"] - ball["y"]) ** 2) ** 0.5
        if best_distance is None or distance < best_distance:
            best_unum = unum
            best_distance = distance
            best_position = position

    if best_unum is None or best_distance is None or best_position is None:
        return None
    return {
        "unum": best_unum,
        "distance": round(best_distance, 3),
        "x": maybe_round(best_position["x"]),
        "y": maybe_round(best_position["y"]),
    }


def count_goals(goals: list[GoalEvent], event_side: str, cutoff_cycle: int | None = None) -> int:
    count = 0
    for goal in goals:
        if goal.event_side != event_side:
            continue
        if cutoff_cycle is not None and goal.cycle > cutoff_cycle:
            continue
        count += 1
    return count


def build_result_only_match_report(match_input: MatchInput, team_name: str) -> dict[str, Any]:
    return {
        "match_label": match_input.match_dir.name,
        "match_dir": str(match_input.match_dir),
        "source_path": str(match_input.source_path),
        "result_path": str(match_input.result_path) if match_input.result_path is not None else None,
        "team_name": team_name,
        "our_side": None,
        "left_team": None,
        "right_team": None,
        "opponent_team": match_input.opponent_team,
        "opponent_key": match_input.opponent_key,
        "run_label": match_input.run_label,
        "experiment_profile": match_input.experiment_profile,
        "score_for": match_input.score_for,
        "score_against": match_input.score_against,
        "early_goals_for_300": 0,
        "early_goals_against_300": 0,
        "early_goals_for_1000": 0,
        "early_goals_against_1000": 0,
        "health": match_input.health or "unknown",
        "disconnects": match_input.disconnects,
        "timing_warnings": match_input.timing_warnings,
        "comm_warnings": match_input.comm_warnings,
        "opponent_actions": match_input.opponent_actions,
        "referee_event_counts": {},
        "referee_event_tokens": {},
        "goal_windows": [],
        "data_quality": {
            "rcg_present": False,
            "rcl_present": False,
            "server_log_present": False,
            "snapshot_cycles": 0,
            "goal_events": 0,
            "availability": "result_only",
        },
    }


def summarize_match(match_input: MatchInput, explicit_team_name: str | None, window_size: int) -> dict[str, Any]:
    match_dir = match_input.match_dir
    if not match_dir.exists():
        team_name = explicit_team_name or match_input.my_team
        if team_name is None:
            raise ObservabilityError(f"match directory missing and team is unknown for {match_dir}")
        return build_result_only_match_report(match_input, team_name)

    record_dir = match_dir / "server_records"
    rcg_candidates = sorted(record_dir.glob("*.rcg")) if record_dir.is_dir() else []
    rcl_candidates = sorted(record_dir.glob("*.rcl")) if record_dir.is_dir() else []
    rcg_path = rcg_candidates[-1] if rcg_candidates else None
    rcl_path = rcl_candidates[-1] if rcl_candidates else None
    server_log_path = match_dir / "rcssserver.log"

    rcg_metadata = parse_rcg_metadata(rcg_path)
    server_log_metadata = parse_server_log_metadata(server_log_path if server_log_path.is_file() else None)

    if rcg_path is None and rcl_path is None:
        team_name = explicit_team_name or match_input.my_team
        if team_name is not None and match_input.score_for is not None and match_input.score_against is not None:
            return build_result_only_match_report(match_input, team_name)

    left_team = rcg_metadata["left_team"] or server_log_metadata["left_team"]
    right_team = rcg_metadata["right_team"] or server_log_metadata["right_team"]
    team_name = choose_team_name(explicit_team_name, match_input, (left_team, right_team))
    our_side = determine_our_side(team_name, left_team, right_team)
    if our_side is None:
        raise ObservabilityError(
            f"cannot determine target team for {match_dir}. Use --team to specify one of {left_team!r} or {right_team!r}."
        )

    events = parse_rcl_events(rcl_path)
    goals = build_goal_events(events, our_side)
    snapshots = load_window_snapshots(rcg_path, [goal.cycle for goal in goals], our_side, window_size)
    server_params = rcg_metadata["server_params"]

    goal_windows = [build_goal_window(goal, events, snapshots, our_side, server_params, window_size) for goal in goals]
    referee_family_counts = Counter(classify_referee_family(event["token"]) for event in events)
    referee_token_counts = Counter(event["token"] for event in events)

    final_score_for, final_score_against = derive_final_score(match_input, rcg_metadata, server_log_metadata, our_side)
    health_status = match_input.health or "unknown"

    return {
        "match_label": match_dir.name,
        "match_dir": str(match_dir),
        "source_path": str(match_input.source_path),
        "result_path": str(match_input.result_path) if match_input.result_path is not None else None,
        "team_name": team_name,
        "our_side": our_side,
        "left_team": left_team,
        "right_team": right_team,
        "opponent_team": match_input.opponent_team,
        "opponent_key": match_input.opponent_key,
        "run_label": match_input.run_label,
        "experiment_profile": match_input.experiment_profile,
        "score_for": final_score_for,
        "score_against": final_score_against,
        "early_goals_for_300": count_goals(goals, "for", 300),
        "early_goals_against_300": count_goals(goals, "against", 300),
        "early_goals_for_1000": count_goals(goals, "for", 1000),
        "early_goals_against_1000": count_goals(goals, "against", 1000),
        "health": health_status,
        "disconnects": match_input.disconnects,
        "timing_warnings": match_input.timing_warnings,
        "comm_warnings": match_input.comm_warnings,
        "opponent_actions": match_input.opponent_actions,
        "referee_event_counts": dict(sorted(referee_family_counts.items())),
        "referee_event_tokens": dict(sorted(referee_token_counts.items())),
        "goal_windows": goal_windows,
        "data_quality": {
            "rcg_present": rcg_path is not None,
            "rcl_present": rcl_path is not None,
            "server_log_present": server_log_path.is_file(),
            "snapshot_cycles": len(snapshots),
            "goal_events": len(goals),
        },
    }


def derive_final_score(
    match_input: MatchInput,
    rcg_metadata: dict[str, Any],
    server_log_metadata: dict[str, Any],
    our_side: str,
) -> tuple[int | None, int | None]:
    if match_input.score_for is not None and match_input.score_against is not None:
        return match_input.score_for, match_input.score_against

    left_score = rcg_metadata["left_score"]
    right_score = rcg_metadata["right_score"]
    if left_score is None or right_score is None:
        left_score = server_log_metadata["left_score"]
        right_score = server_log_metadata["right_score"]
    if left_score is None or right_score is None:
        return None, None
    if our_side == "l":
        return left_score, right_score
    return right_score, left_score


def aggregate_matches(match_reports: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "match_count": len(match_reports),
        "goals_for": 0,
        "goals_against": 0,
        "early_goals_for_300": 0,
        "early_goals_against_300": 0,
        "early_goals_for_1000": 0,
        "early_goals_against_1000": 0,
        "disconnects": 0,
        "timing_warnings": 0,
        "comm_warnings": 0,
        "opponent_actions": 0,
        "health_counts": {},
        "referee_event_counts": {},
        "conceded_channels": {},
        "conceded_restart_contexts": {},
        "conceded_box_entry": {"entered_box": 0, "no_box_entry": 0, "unknown": 0},
    }

    health_counts = Counter()
    referee_counts = Counter()
    conceded_channels = Counter()
    conceded_restart_contexts = Counter()

    for match in match_reports:
        summary["goals_for"] += match["score_for"] or 0
        summary["goals_against"] += match["score_against"] or 0
        summary["early_goals_for_300"] += match["early_goals_for_300"]
        summary["early_goals_against_300"] += match["early_goals_against_300"]
        summary["early_goals_for_1000"] += match["early_goals_for_1000"]
        summary["early_goals_against_1000"] += match["early_goals_against_1000"]
        summary["disconnects"] += match["disconnects"]
        summary["timing_warnings"] += match["timing_warnings"]
        summary["comm_warnings"] += match["comm_warnings"]
        summary["opponent_actions"] += match["opponent_actions"]
        health_counts[match["health"]] += 1
        referee_counts.update(match["referee_event_counts"])

        for window in match["goal_windows"]:
            if window["event_side"] != "against":
                continue
            conceded_channels[window["ball_channel"]] += 1
            conceded_restart_contexts[window["restart_context"]] += 1
            if window["entered_box"] is True:
                summary["conceded_box_entry"]["entered_box"] += 1
            elif window["entered_box"] is False:
                summary["conceded_box_entry"]["no_box_entry"] += 1
            else:
                summary["conceded_box_entry"]["unknown"] += 1

    summary["health_counts"] = dict(sorted(health_counts.items()))
    summary["referee_event_counts"] = dict(sorted(referee_counts.items()))
    summary["conceded_channels"] = dict(sorted(conceded_channels.items()))
    summary["conceded_restart_contexts"] = dict(sorted(conceded_restart_contexts.items()))
    return summary


def analyze_input(input_path: Path, explicit_team_name: str | None, window_size: int) -> dict[str, Any]:
    match_inputs = collect_match_inputs(input_path, explicit_team_name)
    if not match_inputs:
        raise ObservabilityError(f"no match inputs found for {input_path}")

    match_reports: list[dict[str, Any]] = []
    errors: list[str] = []
    for match_input in match_inputs:
        try:
            match_reports.append(summarize_match(match_input, explicit_team_name, window_size))
        except ObservabilityError as exc:
            errors.append(str(exc))
        except Exception as exc:
            errors.append(f"{match_input.match_dir}: {exc}")

    if not match_reports and errors:
        raise ObservabilityError(errors[0])

    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "input_path": str(input_path.resolve()),
        "team_name": explicit_team_name,
        "window_cycles": window_size,
        "matches": match_reports,
        "summary": aggregate_matches(match_reports),
        "errors": errors,
    }


def flatten_value(prefix: str, value: Any, output: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            nested_prefix = f"{prefix}_{key}" if prefix else str(key)
            flatten_value(nested_prefix, nested_value, output)
        return
    if isinstance(value, list):
        output[prefix] = json.dumps(value, ensure_ascii=False)
        return
    output[prefix] = value


def build_csv_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match in report["matches"]:
        base = {
            "match_label": match["match_label"],
            "match_dir": match["match_dir"],
            "team_name": match["team_name"],
            "opponent_team": match["opponent_team"],
            "opponent_key": match["opponent_key"],
            "run_label": match["run_label"],
            "experiment_profile": match["experiment_profile"],
            "score_for": match["score_for"],
            "score_against": match["score_against"],
            "health": match["health"],
            "disconnects": match["disconnects"],
            "timing_warnings": match["timing_warnings"],
            "comm_warnings": match["comm_warnings"],
            "opponent_actions": match["opponent_actions"],
        }
        goal_windows = match["goal_windows"]
        if not goal_windows:
            rows.append(base)
            continue
        for index, window in enumerate(goal_windows, start=1):
            row = dict(base)
            row["goal_window_index"] = index
            flatten_value("goal", window, row)
            rows.append(row)
    return rows


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Match observability report",
        "",
        f"- input: `{report['input_path']}`",
        f"- matches: {summary['match_count']}",
        f"- goals for / against: {summary['goals_for']} / {summary['goals_against']}",
        f"- early 300 GF / GA: {summary['early_goals_for_300']} / {summary['early_goals_against_300']}",
        f"- early 1000 GF / GA: {summary['early_goals_for_1000']} / {summary['early_goals_against_1000']}",
        f"- disconnects: {summary['disconnects']}",
        f"- timing warnings: {summary['timing_warnings']}",
        f"- comm warnings: {summary['comm_warnings']}",
        f"- opponent actions: {summary['opponent_actions']}",
        "",
        "## Health counts",
        "",
    ]

    if summary["health_counts"]:
        for key, value in summary["health_counts"].items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none")

    lines.extend(["", "## Referee event counts", ""])
    if summary["referee_event_counts"]:
        for key, value in summary["referee_event_counts"].items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none")

    lines.extend(["", "## Conceded-goal patterns", ""])
    if summary["conceded_channels"]:
        lines.append("### Channels")
        for key, value in summary["conceded_channels"].items():
            lines.append(f"- {key}: {value}")
        lines.append("")
    if summary["conceded_restart_contexts"]:
        lines.append("### Restart contexts")
        for key, value in summary["conceded_restart_contexts"].items():
            lines.append(f"- {key}: {value}")
        lines.append("")
    lines.append(
        f"- box entry before conceded goals: {summary['conceded_box_entry']['entered_box']} yes, {summary['conceded_box_entry']['no_box_entry']} no, {summary['conceded_box_entry']['unknown']} unknown"
    )

    for match in report["matches"]:
        lines.extend(
            [
                "",
                f"## {match['match_label']}",
                "",
                f"- teams: {match['left_team']} vs {match['right_team']}",
                f"- target team: {match['team_name']} ({match['our_side']})",
                f"- score: {match['score_for']} - {match['score_against']}",
                f"- health: {match['health']}",
                f"- early 300 GF / GA: {match['early_goals_for_300']} / {match['early_goals_against_300']}",
                f"- early 1000 GF / GA: {match['early_goals_for_1000']} / {match['early_goals_against_1000']}",
            ]
        )
        conceded = [window for window in match["goal_windows"] if window["event_side"] == "against"]
        scored = [window for window in match["goal_windows"] if window["event_side"] == "for"]
        if conceded:
            lines.extend(["", "### Goals against", "", "| cycle | score before | restart | channel | box | goalie x,y | nearest our | nearest opp |", "| --- | --- | --- | --- | --- | --- | --- | --- |"])
            for window in conceded:
                goalie = window["goalie"] or {}
                nearest_our = window["nearest_our_player"] or {}
                nearest_opp = window["nearest_opponent_player"] or {}
                lines.append(
                    "| {cycle} | {score_before_for}-{score_before_against} | {restart} | {channel} | {box} | {goalie_xy} | {our_player} | {opp_player} |".format(
                        cycle=window["goal_cycle"],
                        score_before_for=window["score_before"]["for"],
                        score_before_against=window["score_before"]["against"],
                        restart=window["restart_context"],
                        channel=window["ball_channel"],
                        box="yes" if window["entered_box"] is True else "no" if window["entered_box"] is False else "?",
                        goalie_xy=f"{goalie.get('final_x')},{goalie.get('final_y')}" if goalie else "-",
                        our_player=f"#{nearest_our.get('unum')} ({nearest_our.get('distance')})" if nearest_our else "-",
                        opp_player=f"#{nearest_opp.get('unum')} ({nearest_opp.get('distance')})" if nearest_opp else "-",
                    )
                )
        if scored:
            lines.extend(["", f"### Goals for: {len(scored)}"])
        if not conceded and not scored:
            lines.extend(["", "- no goal windows found"])

    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        for error in report["errors"]:
            lines.append(f"- {error}")

    return "\n".join(lines) + "\n"


def write_outputs(report: dict[str, Any], output_dir: Path, stem: str) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}_observability.json"
    csv_path = output_dir / f"{stem}_observability.csv"
    md_path = output_dir / f"{stem}_observability.md"

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    rows = build_csv_rows(report)
    fieldnames: list[str] = []
    if rows:
        ordered_keys: dict[str, None] = {}
        for row in rows:
            for key in row.keys():
                ordered_keys.setdefault(key, None)
        fieldnames = list(ordered_keys.keys())
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(rows)

    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, csv_path, md_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze match logs and emit offline observability reports")
    parser.add_argument("input_path", type=Path, help="Baseline summary, match result file, or match directory")
    parser.add_argument("--team", dest="team_name", default=None, help="Target team name when the input does not already provide it")
    parser.add_argument("--window", dest="window_size", type=int, default=100, help="Goal-window size in cycles")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for JSON/CSV/Markdown outputs")
    parser.add_argument("--print-markdown", action="store_true", help="Print the generated Markdown report to stdout")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    input_path = args.input_path.resolve()
    stem = input_path.stem if input_path.is_file() else input_path.name

    try:
        report = analyze_input(input_path, args.team_name, args.window_size)
        json_path, csv_path, md_path = write_outputs(report, args.output_dir.resolve(), stem)
    except ObservabilityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: unexpected failure: {exc}", file=sys.stderr)
        return 1

    print(f"JSON: {json_path}")
    print(f"CSV: {csv_path}")
    print(f"Markdown: {md_path}")
    if args.print_markdown:
        print()
        print(md_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
