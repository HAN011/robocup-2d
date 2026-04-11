#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pyrus2d_bootstrap import bootstrap_pyrus2d


bootstrap_pyrus2d(PROJECT_ROOT)

from lib.rcsc.game_mode import GameMode
from lib.rcsc.game_time import GameTime
from lib.rcsc.types import GameModeType, SideID


class GameModeUpdateTest(unittest.TestCase):
    def test_update_refreshes_mode_name_and_side(self) -> None:
        game_mode = GameMode(GameModeType.BeforeKickOff, GameTime(0, 0))

        updated = game_mode.update("kick_off_r)", GameTime(1, 0))

        self.assertTrue(updated)
        self.assertEqual(game_mode.type(), GameModeType.KickOff_Right)
        self.assertEqual(game_mode.mode_name(), "kick_off")
        self.assertEqual(game_mode.side(), SideID.RIGHT)

    def test_time_up_alias_maps_to_time_over(self) -> None:
        game_mode = GameMode(GameModeType.PlayOn, GameTime(10, 0))

        updated = game_mode.update("time_up)", GameTime(11, 0))

        self.assertTrue(updated)
        self.assertEqual(game_mode.type(), GameModeType.TimeOver)
        self.assertEqual(game_mode.mode_name(), "time_over")
        self.assertEqual(game_mode.side(), SideID.NEUTRAL)

    def test_unknown_mode_is_ignored_without_crashing(self) -> None:
        game_mode = GameMode(GameModeType.PlayOn, GameTime(10, 0))

        updated = game_mode.update("mystery_mode)", GameTime(11, 0))

        self.assertFalse(updated)
        self.assertEqual(game_mode.type(), GameModeType.PlayOn)
        self.assertEqual(game_mode.mode_name(), "play_on")
        self.assertEqual(game_mode.side(), SideID.NEUTRAL)


if __name__ == "__main__":
    unittest.main()
