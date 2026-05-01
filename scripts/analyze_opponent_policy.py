#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.analyze_match_observability import (
    SHOW_LINE_RE,
    collect_match_inputs,
    determine_our_side,
    parse_rcg_metadata,
    parse_rcl_events,
    parse_show_snapshot,
    read_text,
)

TEAM_LINE_RE = re.compile(r"^\(team\s+\d+\s+(\S+)\s+(\S+)\s+(\d+)\s+(\d+)\)")
RESTART_PREFIXES = (
    "kick_off",
    "free_kick",
    "ind_free_kick",
    "indirect_free_kick",
    "corner_kick",
    "kick_in",
    "goal_kick",
    "goalie_catch_ball",
)


def record_paths(match_dir: Path) -> tuple[Path | None, Path | None]:
    record_dir = match_dir / "server_records"
    if not record_dir.is_dir():
        return None, None
    rcg_candidates = sorted(record_dir.glob("*.rcg"))
    rcl_candidates = sorted(record_dir.glob("*.rcl"))
    return (rcg_candidates[-1] if rcg_candidates else None, rcl_candidates[-1] if rcl_candidates else None)


def parse_events(match_dir: Path) -> list[dict[str, Any]]:
    _, rcl_path = record_paths(match_dir)
    return parse_rcl_events(rcl_path)


def parse_team_names(match_dir: Path) -> tuple[str | None, str | None]:
    rcg_path, _ = record_paths(match_dir)
    metadata = parse_rcg_metadata(rcg_path)
    left_team = metadata.get("left_team")
    right_team = metadata.get("right_team")
    if left_team or right_team:
        return left_team, right_team

    for path in sorted((match_dir / "server_records").glob("*.rcl")):
        for line in read_text(path).splitlines():
            match = TEAM_LINE_RE.match(line)
            if match:
                return match.group(1), match.group(2)
    return None, None


def parse_rcg_snapshots(match_dir: Path) -> dict[int, dict[str, Any]]:
    rcg_path, _ = record_paths(match_dir)
    if rcg_path is None or not rcg_path.is_file():
        return {}

    snapshots: dict[int, dict[str, Any]] = {}
    with rcg_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            match = SHOW_LINE_RE.match(line)
            if not match:
                continue
            cycle = int(match.group(1))
            snapshot = parse_show_snapshot(line, cycle, None)
            if snapshot is not None:
                snapshots[cycle] = snapshot
    return snapshots


def side_token(token: str) -> str | None:
    parts = token.split("_")
    for part in reversed(parts):
        if part in {"l", "r"}:
            return part
    return None


def other_side(side: str) -> str:
    return "r" if side == "l" else "l"


def orient_point(point: dict[str, float], reference_side: str) -> tuple[float, float]:
    x = float(point["x"])
    y = float(point["y"])
    return (x, y) if reference_side == "l" else (-x, -y)


def team_points(snapshot: dict[str, Any], team_side: str, reference_side: str) -> list[tuple[float, float]]:
    return [orient_point(player, reference_side) for player in snapshot.get("players", {}).get(team_side, {}).values()]


def nearest_team_distance(snapshot: dict[str, Any], team_side: str, reference_side: str, bx: float, by: float) -> float | None:
    values = [math.hypot(px - bx, py - by) for px, py in team_points(snapshot, team_side, reference_side)]
    return min(values) if values else None


def team_shape(snapshot: dict[str, Any], team_side: str, reference_side: str, bx: float, by: float) -> dict[str, float] | None:
    points = [(x, y) for x, y in team_points(snapshot, team_side, reference_side) if x > -45.0]
    if not points:
        return None
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return {
        "avg_x": statistics.mean(xs),
        "width": max(ys) - min(ys),
        "depth": max(xs) - min(xs),
        "behind_ball": sum(1 for x, _ in points if x < bx - 2.0),
        "near_ball_8": sum(1 for x, y in points if math.hypot(x - bx, y - by) < 8.0),
        "near_ball_12": sum(1 for x, y in points if math.hypot(x - bx, y - by) < 12.0),
        "box_support": sum(1 for x, y in points if x < -30.0 and abs(y) < 25.0),
        "arc_support": sum(1 for x, y in points if -36.0 < x < -18.0 and abs(y) < 20.0),
    }


def nearest_snapshot_cycle(snapshots: dict[int, dict[str, Any]], cycle: int) -> int | None:
    if not snapshots:
        return None
    return min(snapshots, key=lambda value: abs(value - cycle))


def restart_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if str(event["token"]).startswith(RESTART_PREFIXES)]


def restart_family(token: str) -> str:
    for prefix in RESTART_PREFIXES:
        if token.startswith(prefix):
            return prefix
    return "other"


def lane_label(y: float) -> str:
    ay = abs(y)
    if ay < 10.0:
        return "center"
    if ay < 22.0:
        return "half_space"
    return "wide"


def zone_label(x: float) -> str:
    if x < -35.0:
        return "deep_box"
    if x < -20.0:
        return "defensive_third"
    if x < 0.0:
        return "own_half"
    if x < 25.0:
        return "opponent_half"
    return "attacking_third"


def team_name_for_side(left_team: str | None, right_team: str | None, side: str) -> str | None:
    return left_team if side == "l" else right_team


def summarize_restarts(
    match_input: Any,
    left_team: str | None,
    right_team: str | None,
    our_side: str,
    events: list[dict[str, Any]],
    snapshots: dict[int, dict[str, Any]],
    window: int,
) -> list[dict[str, Any]]:
    rows = []
    opponent = match_input.opponent_key or match_input.opponent_team or "unknown"

    for event in restart_events(events):
        event_side = side_token(str(event["token"]))
        if event_side is None:
            continue
        cycle = int(event["cycle"])
        start_cycle = nearest_snapshot_cycle(snapshots, cycle)
        end_cycle = nearest_snapshot_cycle(snapshots, cycle + window)
        if start_cycle is None or end_cycle is None or end_cycle <= start_cycle:
            continue
        start = snapshots[start_cycle]
        end = snapshots[end_cycle]
        start_ball = start.get("ball")
        end_ball = end.get("ball")
        if not start_ball or not end_ball:
            continue

        attack_side = event_side
        defensive_side = other_side(attack_side)
        sx, sy = orient_point(start_ball, attack_side)
        ex, ey = orient_point(end_ball, attack_side)
        dsx, dsy = orient_point(start_ball, defensive_side)
        shape = team_shape(start, defensive_side, defensive_side, dsx, dsy) or {}

        rows.append(
            {
                "opponent": opponent,
                "team_name": team_name_for_side(left_team, right_team, attack_side),
                "team_is_aurora": attack_side == our_side,
                "restart_token": event["token"],
                "restart_family": restart_family(str(event["token"])),
                "cycle": cycle,
                "start_cycle": start_cycle,
                "end_cycle": end_cycle,
                "ball_dx_window": ex - sx,
                "ball_abs_y_start": abs(sy),
                "ball_abs_y_end": abs(ey),
                "ball_abs_y_delta": abs(ey) - abs(sy),
                "landing_x": ex,
                "landing_abs_y": abs(ey),
                "deep_start": int(sx < -30.0),
                "forward_exit": int(ex > -10.0 or ex - sx > 20.0),
                "landing_center": int(lane_label(ey) == "center"),
                "landing_wide": int(lane_label(ey) == "wide"),
                "def_nearest_ball_start": nearest_team_distance(start, defensive_side, defensive_side, dsx, dsy),
                **{f"def_{key}": value for key, value in shape.items()},
            }
        )
    return rows


def summarize_clearance_windows(
    match_input: Any,
    left_team: str | None,
    right_team: str | None,
    our_side: str,
    snapshots: dict[int, dict[str, Any]],
    window: int,
    sample_step: int,
) -> list[dict[str, Any]]:
    rows = []
    cycles = sorted(snapshots)
    if not cycles:
        return rows

    opponent = match_input.opponent_key or match_input.opponent_team or "unknown"
    next_sample_cycle = {"l": -1, "r": -1}
    for cycle in cycles:
        start = snapshots[cycle]
        start_ball = start.get("ball")
        if not start_ball:
            continue
        for side in ("l", "r"):
            if cycle < next_sample_cycle[side]:
                continue
            sx, sy = orient_point(start_ball, side)
            if sx > -30.0 or abs(sy) > 36.0:
                continue
            own_distance = nearest_team_distance(start, side, side, sx, sy)
            opponent_distance = nearest_team_distance(start, other_side(side), side, sx, sy)
            if own_distance is None or own_distance > 7.5:
                continue
            if opponent_distance is not None and opponent_distance + 2.0 < own_distance:
                continue

            end_cycle = nearest_snapshot_cycle(snapshots, cycle + window)
            if end_cycle is None or end_cycle <= cycle:
                continue
            end_ball = snapshots[end_cycle].get("ball")
            if not end_ball:
                continue
            ex, ey = orient_point(end_ball, side)
            dx = ex - sx
            next_sample_cycle[side] = cycle + sample_step

            rows.append(
                {
                    "opponent": opponent,
                    "team_name": team_name_for_side(left_team, right_team, side),
                    "team_is_aurora": side == our_side,
                    "cycle": cycle,
                    "end_cycle": end_cycle,
                    "start_x": sx,
                    "start_abs_y": abs(sy),
                    "landing_x": ex,
                    "landing_abs_y": abs(ey),
                    "ball_dx_window": dx,
                    "own_nearest_ball_start": own_distance,
                    "opp_nearest_ball_start": opponent_distance,
                    "exit_success": int(ex > -20.0 or dx > 18.0),
                    "danger_center_exit": int(ex < 0.0 and abs(ey) < 12.0),
                    "landing_center": int(lane_label(ey) == "center"),
                    "landing_wide": int(lane_label(ey) == "wide"),
                    "start_deep_box": int(zone_label(sx) == "deep_box"),
                }
            )
    return rows


def summarize_match(match_input: Any, team_name: str, window: int, sample_step: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    left_team, right_team = parse_team_names(match_input.match_dir)
    our_side = determine_our_side(team_name, left_team, right_team)
    if our_side is None:
        return [], []
    events = parse_events(match_input.match_dir)
    snapshots = parse_rcg_snapshots(match_input.match_dir)
    restart_rows = summarize_restarts(match_input, left_team, right_team, our_side, events, snapshots, window)
    clearance_rows = summarize_clearance_windows(match_input, left_team, right_team, our_side, snapshots, window, sample_step)
    return restart_rows, clearance_rows


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, bool], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["opponent"]), bool(row["team_is_aurora"]))].append(row)

    numeric_keys = sorted(
        {
            key
            for row in rows
            for key, value in row.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool) and key not in {"cycle", "start_cycle", "end_cycle"}
        }
    )

    output = []
    for (opponent, team_is_aurora), values in sorted(groups.items()):
        row = {"opponent": opponent, "team_is_aurora": team_is_aurora, "samples": len(values)}
        for key in numeric_keys:
            nums = [float(value[key]) for value in values if value.get(key) is not None]
            row[f"avg_{key}"] = statistics.mean(nums) if nums else None
        output.append(row)
    return output


def analyze(source: Path, team_name: str, window: int, sample_step: int) -> dict[str, Any]:
    restart_rows = []
    clearance_rows = []
    for match_input in collect_match_inputs(source, team_name):
        match_restarts, match_clearances = summarize_match(match_input, team_name, window, sample_step)
        restart_rows.extend(match_restarts)
        clearance_rows.extend(match_clearances)
    return {
        "source": str(source),
        "team_name": team_name,
        "window": window,
        "sample_step": sample_step,
        "restart_rows": restart_rows,
        "restart_summary": aggregate(restart_rows),
        "clearance_rows": clearance_rows,
        "clearance_summary": aggregate(clearance_rows),
    }


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    keys = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def tagged_summary_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    rows.extend({"kind": "restart", **row} for row in result["restart_summary"])
    rows.extend({"kind": "clearance", **row} for row in result["clearance_summary"])
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build offline opponent policy restart and clearance profiles.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--team", default="Aurora")
    parser.add_argument("--window", type=int, default=120)
    parser.add_argument("--sample-step", type=int, default=20)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-csv", type=Path)
    parser.add_argument("--output-restart-csv", type=Path)
    parser.add_argument("--output-clearance-csv", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = analyze(args.source, args.team, args.window, args.sample_step)
    if args.output_json:
        args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    if args.output_csv:
        write_csv(tagged_summary_rows(result), args.output_csv)
    if args.output_restart_csv:
        write_csv(result["restart_rows"], args.output_restart_csv)
    if args.output_clearance_csv:
        write_csv(result["clearance_rows"], args.output_clearance_csv)
    if not args.output_json and not args.output_csv and not args.output_restart_csv and not args.output_clearance_csv:
        print(json.dumps({"restart_summary": result["restart_summary"], "clearance_summary": result["clearance_summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
