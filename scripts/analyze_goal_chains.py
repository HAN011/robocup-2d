#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


UNKNOWN = "unknown"
MISSING_FROM_OBSERVABILITY = "unavailable_in_observability_csv"


@dataclass(frozen=True)
class InputGroup:
    name: str
    paths: tuple[Path, ...]


def parse_bool(value: Any) -> bool | None:
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def parse_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    number = parse_float(value)
    if number is None:
        return None
    return int(number)


def player_band(unum: Any) -> str:
    number = parse_int(unum)
    if number is None:
        return UNKNOWN
    if number == 1:
        return "goalie"
    if 2 <= number <= 5:
        return "defender"
    if 6 <= number <= 8:
        return "midfielder"
    if 9 <= number <= 11:
        return "attacker"
    return UNKNOWN


def sibling_observability_csv(path: Path) -> Path:
    name = path.name
    if name.endswith("_observability.json"):
        return path.with_name(name.removesuffix(".json") + ".csv")
    if name.endswith("_observability.csv"):
        return path
    if path.suffix == ".txt":
        return path.with_name(path.stem + "_observability.csv")
    if path.suffix == ".json":
        return path.with_suffix(".csv")
    return path


def resolve_observability_csv(path: Path) -> Path:
    if path.suffix == ".csv":
        csv_path = path
    else:
        csv_path = sibling_observability_csv(path)
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"missing observability CSV for {path}. "
            "Run scripts/analyze_match_observability.py first or pass an *_observability.csv file."
        )
    return csv_path


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    csv_path = resolve_observability_csv(path)
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["_source_path"] = str(csv_path)
    return rows


def is_against_goal_row(row: dict[str, str]) -> bool:
    return bool(row.get("goal_window_index")) and row.get("goal_event_side") == "against"


def classify_mechanism(row: dict[str, Any]) -> tuple[str, str]:
    channel = str(row.get("ball_channel") or UNKNOWN)
    restart = str(row.get("restart_context") or UNKNOWN)
    entered_box = parse_bool(row.get("entered_box"))
    gap = parse_float(row.get("midfield_defense_gap"))
    nearest_band = str(row.get("nearest_our_band") or UNKNOWN)

    if entered_box is False:
        return "no_confirmed_box_entry", "observability did not find a box entry in the goal window"
    if entered_box is None:
        return "unavailable_goal_window", "goal window geometry was unavailable"

    if channel == "center" and restart == "kick_off" and gap is not None and gap >= 12.0:
        return "center_kickoff_midfield_gap", "center + kick_off with midfield-defense gap >= 12"
    if channel == "center" and restart == "kick_off":
        return "center_kickoff_entry", "center + kick_off box-entry goal"
    if channel == "center" and gap is not None and gap >= 12.0:
        return "center_midfield_gap", "center goal with midfield-defense gap >= 12"
    if channel == "center" and restart == "setplay":
        return "center_setplay_entry", "center + setplay box-entry goal"
    if channel == "center" and nearest_band == "defender":
        return "center_last_line_engaged", "center goal where nearest our player was a defender"
    if channel == "center":
        return "center_box_entry", "center box-entry goal"

    if channel in {"left_flank", "right_flank"} and restart == "kick_off":
        return "flank_kickoff_entry", "flank + kick_off box-entry goal"
    if channel in {"left_flank", "right_flank"} and restart == "setplay":
        return "flank_setplay_entry", "flank + setplay box-entry goal"
    if channel in {"left_flank", "right_flank"}:
        return "flank_box_entry", "flank box-entry goal"

    if restart == "kick_off":
        return "kickoff_other_channel", "kick_off context with non-standard channel"
    if restart == "setplay":
        return "setplay_other_channel", "setplay context with non-standard channel"
    return "other_box_entry", "box-entry goal outside top mechanism labels"


def build_goal_chain_row(group: str, row: dict[str, str]) -> dict[str, Any]:
    nearest_unum = row.get("goal_nearest_our_player_unum", "")
    output = {
        "analysis_group": group,
        "source_path": row.get("_source_path", ""),
        "match_label": row.get("match_label", ""),
        "match_dir": row.get("match_dir", ""),
        "run_label": row.get("run_label", ""),
        "experiment_profile": row.get("experiment_profile", ""),
        "opponent_key": row.get("opponent_key", ""),
        "goal_index": row.get("goal_window_index", ""),
        "goal_cycle": row.get("goal_goal_cycle", ""),
        "score_before_for": row.get("goal_score_before_for", ""),
        "score_before_against": row.get("goal_score_before_against", ""),
        "score_after_for": row.get("goal_score_after_for", ""),
        "score_after_against": row.get("goal_score_after_against", ""),
        "restart_context": row.get("goal_restart_context", UNKNOWN),
        "ball_channel": row.get("goal_ball_channel", UNKNOWN),
        "entered_box": row.get("goal_entered_box", ""),
        "entered_box_front": row.get("goal_entered_box_front", ""),
        "box_entry_cycle": MISSING_FROM_OBSERVABILITY,
        "box_entry_to_goal_cycles": MISSING_FROM_OBSERVABILITY,
        "first_our_touch_cycle": MISSING_FROM_OBSERVABILITY,
        "first_clear_cycle": MISSING_FROM_OBSERVABILITY,
        "nearest_our_unum": nearest_unum,
        "nearest_our_band": player_band(nearest_unum),
        "nearest_our_distance": row.get("goal_nearest_our_player_distance", ""),
        "nearest_opponent_unum": row.get("goal_nearest_opponent_player_unum", ""),
        "nearest_opponent_distance": row.get("goal_nearest_opponent_player_distance", ""),
        "goalie_final_x": row.get("goal_goalie_final_x", ""),
        "goalie_final_y": row.get("goal_goalie_final_y", ""),
        "defenders_avg_depth": row.get("goal_defenders_avg_depth", ""),
        "defenders_avg_width": row.get("goal_defenders_avg_width", ""),
        "midfielders_avg_depth": row.get("goal_midfielders_avg_depth", ""),
        "midfielders_avg_width": row.get("goal_midfielders_avg_width", ""),
        "midfield_defense_gap": row.get("goal_midfield_defense_gap", ""),
    }
    mechanism, basis = classify_mechanism(
        {
            "ball_channel": output["ball_channel"],
            "restart_context": output["restart_context"],
            "entered_box": output["entered_box"],
            "midfield_defense_gap": output["midfield_defense_gap"],
            "nearest_our_band": output["nearest_our_band"],
        }
    )
    output["mechanism_cluster"] = mechanism
    output["mechanism_basis"] = basis
    return output


def load_goal_chain_rows(groups: Iterable[InputGroup]) -> list[dict[str, Any]]:
    goal_rows: list[dict[str, Any]] = []
    for group in groups:
        for path in group.paths:
            for row in load_csv_rows(path):
                if is_against_goal_row(row):
                    goal_rows.append(build_goal_chain_row(group.name, row))
    return goal_rows


def count_field(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field) or UNKNOWN) for row in rows).items()))


def mean_field(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [parse_float(row.get(field)) for row in rows]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 3)


def summarize_group(rows: list[dict[str, Any]], min_improvement_pct: float, baseline_goals: int | None) -> dict[str, Any]:
    source_count = len({row["source_path"] for row in rows})
    total = len(rows)
    avg_per_run = total / source_count if source_count else 0.0
    threshold_per_run = (baseline_goals if baseline_goals is not None else avg_per_run) * min_improvement_pct

    clusters = []
    cluster_counts = Counter(row["mechanism_cluster"] for row in rows)
    for cluster, count in sorted(cluster_counts.items(), key=lambda item: (-item[1], item[0])):
        avg_cluster = count / source_count if source_count else 0.0
        clusters.append(
            {
                "cluster": cluster,
                "count": count,
                "avg_per_run": round(avg_cluster, 3),
                "pct": round(count / total, 4) if total else 0.0,
                "meets_10pct_gate": avg_cluster >= threshold_per_run,
            }
        )

    return {
        "runs": source_count,
        "goals_against": total,
        "avg_goals_against_per_run": round(avg_per_run, 3),
        "minimum_improvement_pct": min_improvement_pct,
        "minimum_cluster_avg_per_run_for_experiment": round(threshold_per_run, 3),
        "counts": {
            "mechanism_cluster": dict(cluster_counts),
            "opponent_key": count_field(rows, "opponent_key"),
            "ball_channel": count_field(rows, "ball_channel"),
            "restart_context": count_field(rows, "restart_context"),
            "nearest_our_band": count_field(rows, "nearest_our_band"),
        },
        "averages": {
            "nearest_our_distance": mean_field(rows, "nearest_our_distance"),
            "goalie_final_x": mean_field(rows, "goalie_final_x"),
            "defenders_avg_depth": mean_field(rows, "defenders_avg_depth"),
            "midfielders_avg_depth": mean_field(rows, "midfielders_avg_depth"),
            "midfield_defense_gap": mean_field(rows, "midfield_defense_gap"),
        },
        "clusters": clusters,
        "experiment_eligible_clusters": [cluster for cluster in clusters if cluster["meets_10pct_gate"]],
    }


def delta_counts(candidate: dict[str, int], baseline: dict[str, int]) -> dict[str, int]:
    keys = sorted(set(candidate) | set(baseline))
    return {key: candidate.get(key, 0) - baseline.get(key, 0) for key in keys}


def build_summary(
    rows: list[dict[str, Any]],
    group_order: list[str],
    min_improvement_pct: float,
    baseline_goals: int | None,
) -> dict[str, Any]:
    groups = {
        group: summarize_group([row for row in rows if row["analysis_group"] == group], min_improvement_pct, baseline_goals)
        for group in group_order
    }
    summary: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_goal_rows": len(rows),
        "groups": groups,
    }

    if len(group_order) == 2:
        baseline_group, candidate_group = group_order
        baseline = groups[baseline_group]["counts"]
        candidate = groups[candidate_group]["counts"]
        summary["group_delta"] = {
            "candidate_group": candidate_group,
            "baseline_group": baseline_group,
            "mechanism_cluster": delta_counts(candidate["mechanism_cluster"], baseline["mechanism_cluster"]),
            "opponent_key": delta_counts(candidate["opponent_key"], baseline["opponent_key"]),
            "ball_channel": delta_counts(candidate["ball_channel"], baseline["ball_channel"]),
            "restart_context": delta_counts(candidate["restart_context"], baseline["restart_context"]),
            "nearest_our_band": delta_counts(candidate["nearest_our_band"], baseline["nearest_our_band"]),
        }
    return summary


def write_goal_chains_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "analysis_group",
        "source_path",
        "match_label",
        "match_dir",
        "run_label",
        "experiment_profile",
        "opponent_key",
        "goal_index",
        "goal_cycle",
        "score_before_for",
        "score_before_against",
        "score_after_for",
        "score_after_against",
        "restart_context",
        "ball_channel",
        "entered_box",
        "entered_box_front",
        "box_entry_cycle",
        "box_entry_to_goal_cycles",
        "first_our_touch_cycle",
        "first_clear_cycle",
        "nearest_our_unum",
        "nearest_our_band",
        "nearest_our_distance",
        "nearest_opponent_unum",
        "nearest_opponent_distance",
        "goalie_final_x",
        "goalie_final_y",
        "defenders_avg_depth",
        "defenders_avg_width",
        "midfielders_avg_depth",
        "midfielders_avg_width",
        "midfield_defense_gap",
        "mechanism_cluster",
        "mechanism_basis",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_markdown(summary: dict[str, Any]) -> str:
    lines = ["# Goal Chain Analysis", ""]
    for group_name, group in summary["groups"].items():
        lines.extend(
            [
                f"## {group_name}",
                "",
                f"- runs: {group['runs']}",
                f"- goals against: {group['goals_against']}",
                f"- avg GA/run: {group['avg_goals_against_per_run']}",
                f"- 10% experiment gate: {group['minimum_cluster_avg_per_run_for_experiment']} GA/run",
                "",
                "| cluster | count | avg/run | pct | eligible |",
                "| --- | ---: | ---: | ---: | --- |",
            ]
        )
        for cluster in group["clusters"][:12]:
            eligible = "yes" if cluster["meets_10pct_gate"] else "no"
            lines.append(
                f"| {cluster['cluster']} | {cluster['count']} | {cluster['avg_per_run']} | {cluster['pct']:.2%} | {eligible} |"
            )
        lines.append("")

    delta = summary.get("group_delta")
    if delta:
        lines.extend(
            [
                "## Group Delta",
                "",
                f"- candidate group: {delta['candidate_group']}",
                f"- baseline group: {delta['baseline_group']}",
                "",
                "| dimension | key | delta |",
                "| --- | --- | ---: |",
            ]
        )
        for dimension in ("mechanism_cluster", "opponent_key", "ball_channel", "restart_context", "nearest_our_band"):
            for key, value in sorted(delta[dimension].items(), key=lambda item: (-abs(item[1]), item[0]))[:12]:
                lines.append(f"| {dimension} | {key} | {value} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_group_spec(raw: str) -> InputGroup:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("group must use NAME=path1,path2 format")
    name, paths_text = raw.split("=", 1)
    name = name.strip()
    if not name:
        raise argparse.ArgumentTypeError("group name cannot be empty")
    paths = tuple(Path(part.strip()) for part in paths_text.split(",") if part.strip())
    if not paths:
        raise argparse.ArgumentTypeError("group must include at least one path")
    return InputGroup(name, paths)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify conceded goals into mechanism-oriented goal-chain clusters.")
    parser.add_argument("inputs", nargs="*", type=Path, help="Summary txt, observability JSON, or observability CSV files.")
    parser.add_argument("--group", action="append", type=parse_group_spec, help="Named input group: NAME=path1,path2")
    parser.add_argument("--output-prefix", type=Path, help="Output path prefix. Writes *_goal_chains.csv/json/md.")
    parser.add_argument("--minimum-improvement-pct", type=float, default=0.10)
    parser.add_argument("--baseline-goals", type=int, help="Fixed baseline GA used for the experiment eligibility gate.")
    return parser.parse_args()


def default_output_prefix() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("results") / f"goal_chains_{stamp}"


def build_groups(args: argparse.Namespace) -> list[InputGroup]:
    groups: list[InputGroup] = list(args.group or [])
    if args.inputs:
        groups.append(InputGroup("all", tuple(args.inputs)))
    if not groups:
        raise SystemExit("provide at least one input or --group")
    return groups


def main() -> int:
    args = parse_args()
    groups = build_groups(args)
    rows = load_goal_chain_rows(groups)
    group_order = [group.name for group in groups]
    summary = build_summary(rows, group_order, args.minimum_improvement_pct, args.baseline_goals)

    output_prefix = args.output_prefix or default_output_prefix()
    csv_path = output_prefix.with_name(output_prefix.name + "_goal_chains.csv")
    json_path = output_prefix.with_name(output_prefix.name + "_goal_chain_summary.json")
    md_path = output_prefix.with_name(output_prefix.name + "_goal_chain_summary.md")

    write_goal_chains_csv(rows, csv_path)
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(summary), encoding="utf-8")

    print(f"CSV: {csv_path.resolve()}")
    print(f"JSON: {json_path.resolve()}")
    print(f"Markdown: {md_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
