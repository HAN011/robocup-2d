#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pyrus2d_bootstrap import bootstrap_pyrus2d


bootstrap_pyrus2d(PROJECT_ROOT)

import team_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a RoboCup 2D field player or goalkeeper")
    parser.add_argument("-t", "--team-name", "--team", dest="team_name", required=True, help="Team name")
    parser.add_argument("--goalie", action="store_true", help="Run as goalkeeper")
    parser.add_argument("--unum", type=int, default=None, help="Requested uniform number")
    parser.add_argument("-H", "--host", dest="host", default=team_config.HOST, help="rcssserver host")
    parser.add_argument("--port", dest="port", type=int, default=None, help="Base player port")
    parser.add_argument("-p", "--player-port", dest="player_port", type=int, default=team_config.PLAYER_PORT, help="player port")
    parser.add_argument("-P", "--coach-port", type=int, default=team_config.COACH_PORT, help="coach port")
    parser.add_argument("--trainer-port", type=int, default=team_config.TRAINER_PORT, help="trainer port")
    parser.add_argument("--log-path", default=None, help="log directory")
    parser.add_argument("--file-log-level", default=None, help="file log level")
    parser.add_argument("--console-log-level", default=None, help="console log level")
    parser.add_argument("--disable-file-log", action="store_true", help="disable file logging")
    return parser


ARGS = build_parser().parse_args()
if ARGS.port is not None:
    ARGS.player_port = ARGS.port
team_config.update_team_config(ARGS)

from lib.debug.debug import log
from player.agent import RoboCupPlayerAgent


def main() -> int:
    _tty_fd = os.fdopen(3, "w", closefd=False) if os.isatty(3) or True else sys.stdout
    _tty_fd.write(f"2026RoboCup机器人世界杯中国赛【{team_config.TEAM_NAME}】\n")
    _tty_fd.flush()
    print(f"2026RoboCup机器人世界杯中国赛【{team_config.TEAM_NAME}】")
    goalie = ARGS.goalie or ARGS.unum == 1
    agent = RoboCupPlayerAgent(goalie=goalie)

    if not agent.handle_start():
        agent.handle_exit()
        return 1

    try:
        agent.run()
    except KeyboardInterrupt:
        agent.handle_exit()
        return 0
    except Exception as exc:
        import traceback

        traceback.print_exc()
        log.os_log().error(f"Player process crashed: {exc}")
        log.os_log().error(traceback.format_exc())
        agent.handle_exit()
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
