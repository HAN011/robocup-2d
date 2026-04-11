#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pyrus2d_bootstrap import bootstrap_pyrus2d


bootstrap_pyrus2d(PROJECT_ROOT)

from base.sample_player import SamplePlayer
from base.view_tactical import ViewTactical
from player.decision import get_decision


FORMATION_ROLES = {
    1: "goalkeeper",
    2: "left_back",
    3: "left_center_back",
    4: "right_center_back",
    5: "right_back",
    6: "left_midfielder",
    7: "center_midfielder",
    8: "right_midfielder",
    9: "left_forward",
    10: "center_forward",
    11: "right_forward",
}


class RoboCupPlayerAgent(SamplePlayer):
    def __init__(self, goalie: bool = False):
        super().__init__(goalie=goalie)
        self._aurora_last_action_label = ""
        self._aurora_last_decision_target = None
        self._aurora_last_block_target = None

    @staticmethod
    def role_name(unum: int) -> str:
        return FORMATION_ROLES.get(unum, "player")

    def action_impl(self):
        self._aurora_last_action_label = ""
        self._aurora_last_decision_target = None
        self._aurora_last_block_target = None
        if self.do_preprocess():
            return

        self.set_view_action(ViewTactical())
        get_decision(self).execute(self)

    def handle_exit(self):
        self.effector().log_diagnostics_summary()
        super().handle_exit()
