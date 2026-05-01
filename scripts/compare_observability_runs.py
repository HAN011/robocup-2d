#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_report(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        report = json.load(handle)
    report["_source_path"] = str(path)
    return report


def profile_name(report: dict[str, Any]) -> str:
    for match in report.get("matches", []):
        value = match.get("experiment_profile")
        if value:
            return str(value)
    source = Path(report.get("_source_path", "report")).stem
    return source.removesuffix("_observability")


def count_back_passes(match: dict[str, Any]) -> int:
    our_side = match.get("our_side")
    suffix = f"_{our_side}" if our_side in {"l", "r"} else None
    events = match.get("referee_events", [])
    if events:
        count = 0
        for event in events:
            token = str(event.get("token", ""))
            if token.startswith("back_pass") and (suffix is None or token.endswith(suffix)):
                count += 1
        return count

    token_counts = match.get("referee_event_tokens", {})
    if isinstance(token_counts, dict):
        count = 0
        for token, value in token_counts.items():
            token_text = str(token)
            if token_text.startswith("back_pass") and (suffix is None or token_text.endswith(suffix)):
                count += int(value or 0)
        return count

    family_counts = match.get("referee_event_counts", {})
    if suffix is None and isinstance(family_counts, dict):
        return int(family_counts.get("back_pass") or 0)
    return 0


def summarize_report(report: dict[str, Any]) -> dict[str, Any]:
    opponents: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "matches": 0,
            "gf": 0,
            "ga": 0,
            "early_ga_300": 0,
            "early_ga_1000": 0,
            "back_pass": 0,
            "disconnects": 0,
            "timing_warnings": 0,
            "suspect": 0,
        }
    )
    total = {
        "matches": 0,
        "gf": 0,
        "ga": 0,
        "early_ga_300": 0,
        "early_ga_1000": 0,
        "back_pass": 0,
        "disconnects": 0,
        "timing_warnings": 0,
        "suspect": 0,
    }

    for match in report.get("matches", []):
        key = match.get("opponent_key") or match.get("opponent_team") or "unknown"
        row = opponents[str(key)]
        score_for = int(match.get("score_for") or 0)
        score_against = int(match.get("score_against") or 0)
        back_pass = count_back_passes(match)
        windows = match.get("goal_windows", [])
        early_300 = sum(1 for window in windows if window.get("cycle", 1000000) <= 300)
        early_1000 = sum(1 for window in windows if window.get("cycle", 1000000) <= 1000)
        disconnects = int(match.get("disconnects") or 0)
        timing_warnings = int(match.get("timing_warnings") or 0)
        suspect = 1 if match.get("health") == "suspect" else 0

        for target in (row, total):
            target["matches"] += 1
            target["gf"] += score_for
            target["ga"] += score_against
            target["early_ga_300"] += early_300
            target["early_ga_1000"] += early_1000
            target["back_pass"] += back_pass
            target["disconnects"] += disconnects
            target["timing_warnings"] += timing_warnings
            target["suspect"] += suspect

    return {
        "profile": profile_name(report),
        "source_path": report.get("_source_path"),
        "total": total,
        "opponents": dict(sorted(opponents.items())),
    }


def delta(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for key in ("matches", "gf", "ga", "early_ga_300", "early_ga_1000", "back_pass", "disconnects", "timing_warnings", "suspect"):
        result[f"delta_{key}"] = candidate.get(key, 0) - baseline.get(key, 0)
    result["delta_gd"] = (candidate.get("gf", 0) - candidate.get("ga", 0)) - (baseline.get("gf", 0) - baseline.get("ga", 0))
    return result


def build_rows(baseline: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    baseline_total = baseline["total"]
    for candidate in candidates:
        candidate_total = candidate["total"]
        row = {
            "scope": "total",
            "profile": candidate["profile"],
            "opponent": "ALL",
            **candidate_total,
            **delta(candidate_total, baseline_total),
        }
        rows.append(row)

        opponents = sorted(set(baseline["opponents"]) | set(candidate["opponents"]))
        for opponent in opponents:
            cand_row = candidate["opponents"].get(opponent, {})
            base_row = baseline["opponents"].get(opponent, {})
            rows.append(
                {
                    "scope": "opponent",
                    "profile": candidate["profile"],
                    "opponent": opponent,
                    **{key: cand_row.get(key, 0) for key in baseline_total},
                    **delta(cand_row, base_row),
                }
            )
    return rows


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "scope",
        "profile",
        "opponent",
        "matches",
        "gf",
        "ga",
        "early_ga_300",
        "early_ga_1000",
        "back_pass",
        "disconnects",
        "timing_warnings",
        "suspect",
        "delta_matches",
        "delta_gf",
        "delta_ga",
        "delta_gd",
        "delta_early_ga_300",
        "delta_early_ga_1000",
        "delta_back_pass",
        "delta_disconnects",
        "delta_timing_warnings",
        "delta_suspect",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict[str, Any]]) -> str:
    selected = [row for row in rows if row["scope"] == "total"]
    lines = [
        "| profile | GF | GA | GD | dGF | dGA | dGD | back-pass | dBackPass | suspect | disconnects |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in selected:
        gd = row["gf"] - row["ga"]
        lines.append(
            f"| {row['profile']} | {row['gf']} | {row['ga']} | {gd} | "
            f"{row['delta_gf']} | {row['delta_ga']} | {row['delta_gd']} | "
            f"{row['back_pass']} | {row['delta_back_pass']} | {row['suspect']} | {row['disconnects']} |"
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare RoboCup observability JSON reports.")
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", action="append", required=True, type=Path)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--markdown", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    baseline = summarize_report(load_report(args.baseline))
    candidates = [summarize_report(load_report(path)) for path in args.candidate]
    rows = build_rows(baseline, candidates)
    markdown = markdown_table(rows)

    if args.csv:
        write_csv(rows, args.csv)
    if args.markdown:
        args.markdown.write_text(markdown + "\n", encoding="utf-8")
    if not args.csv and not args.markdown:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
