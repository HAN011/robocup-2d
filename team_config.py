#!/usr/bin/env python3
from __future__ import annotations

import datetime
import logging
import sys


TEAM_NAME = "Pyrus433"
LOG_PATH = f"logs/{datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}"
FILE_LOG_LEVEL = logging.ERROR
DISABLE_FILE_LOG = False
CONSOLE_LOG_LEVEL = logging.ERROR
HOST = "localhost"
PLAYER_PORT = 6000
TRAINER_PORT = 6001
COACH_PORT = 6002
DEBUG_CLIENT_PORT = 6032

SOCKET_INTERVAL = 0.01
WAIT_TIME_THR_SYNCH_VIEW = 30
WAIT_TIME_THR_NOSYNCH_VIEW = 75

PLAYER_VERSION = 19
COACH_VERSION = 19

WORLD_IS_FULL_WORLD_IF_EXIST = True
WORLD_IS_REAL_WORLD = True
S_WORLD_IS_REAL_WORLD = False

USE_COMMUNICATION = True


def update_team_config(args) -> None:
    module = sys.modules[__name__]

    mapping = {
        "team_name": "TEAM_NAME",
        "host": "HOST",
        "player_port": "PLAYER_PORT",
        "trainer_port": "TRAINER_PORT",
        "coach_port": "COACH_PORT",
        "log_path": "LOG_PATH",
    }

    for arg_name, config_name in mapping.items():
        value = getattr(args, arg_name, None)
        if value is not None:
            setattr(module, config_name, value)

    file_log_level = getattr(args, "file_log_level", None)
    if file_log_level:
        module.FILE_LOG_LEVEL = getattr(logging, file_log_level.upper(), logging.INFO)

    console_log_level = getattr(args, "console_log_level", None)
    if console_log_level:
        module.CONSOLE_LOG_LEVEL = getattr(logging, console_log_level.upper(), logging.INFO)

    if getattr(args, "disable_file_log", False):
        module.DISABLE_FILE_LOG = True
