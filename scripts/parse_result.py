#!/usr/bin/env python3

from __future__ import annotations

import argparse
import pathlib
import re
import sys


TEAM_LINE_RE = re.compile(r"^\(team\s+\d+\s+(\S+)\s+(\S+)\s+(\d+)\s+(\d+)\)\s*$")
RESULT_MSG_RE = re.compile(r"\(result\s+\d+\s+(.*)\)")
RESULT_PAYLOAD_RE = re.compile(r"^(.*)_([0-9]+)-vs-(.*)_([0-9]+)$")


def parse_rcg(path: pathlib.Path) -> tuple[str, int, int, str]:
    last_team_line: tuple[str, int, int, str] | None = None
    last_result_payload: tuple[str, int, int, str] | None = None

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()

            team_match = TEAM_LINE_RE.match(line)
            if team_match:
                left_team = team_match.group(1)
                right_team = team_match.group(2)
                left_score = int(team_match.group(3))
                right_score = int(team_match.group(4))
                last_team_line = (left_team, left_score, right_score, right_team)
                continue

            result_match = RESULT_MSG_RE.search(line)
            if not result_match:
                continue

            payload_match = RESULT_PAYLOAD_RE.match(result_match.group(1))
            if not payload_match:
                continue

            left_team = payload_match.group(1)
            left_score = int(payload_match.group(2))
            right_team = payload_match.group(3)
            right_score = int(payload_match.group(4))
            last_result_payload = (left_team, left_score, right_score, right_team)

    if last_team_line is not None:
        return last_team_line
    if last_result_payload is not None:
        return last_result_payload

    raise ValueError(f"could not find final score in {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse final score from an rcssserver .rcg log")
    parser.add_argument("rcg_file", type=pathlib.Path, help="Path to .rcg file")
    parser.add_argument(
        "--format",
        choices=("text", "tsv"),
        default="text",
        help="Output format. 'text' prints a readable score line, 'tsv' prints tab-separated fields.",
    )
    args = parser.parse_args()

    rcg_path = args.rcg_file.resolve()
    if not rcg_path.is_file():
        print(f"ERROR: file not found: {rcg_path}", file=sys.stderr)
        return 1

    try:
        left_team, left_score, right_score, right_team = parse_rcg(rcg_path)
    except Exception as exc:  # pragma: no cover - defensive CLI path
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.format == "tsv":
        print(f"{left_team}\t{right_team}\t{left_score}\t{right_score}")
    else:
        print(f"{left_team} {left_score} - {right_score} {right_team}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
