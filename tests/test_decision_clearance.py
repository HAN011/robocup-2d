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

from lib.rcsc.server_param import ServerParam
from player.decision import (
    choose_defensive_clearance_label,
    choose_goalie_restart_target,
    disciplined_screen_active,
    disciplined_screen_retreat_bonus,
    setplay_screen_active,
    setplay_screen_retreat_bonus,
    should_use_one_step_clear,
)
from player.experiment_profile import resolve_experiment_profile
from pyrusgeom.vector_2d import Vector2D


class _Opponent:
    def __init__(self, unum: int, x: float, y: float):
        self._unum = unum
        self._pos = Vector2D(x, y)

    def unum(self) -> int:
        return self._unum

    def pos(self) -> Vector2D:
        return self._pos

    def pos_count(self) -> int:
        return 0

    def is_ghost(self) -> bool:
        return False


class _Ball:
    def __init__(self, x: float, y: float):
        self._pos = Vector2D(x, y)

    def pos(self) -> Vector2D:
        return self._pos


class _GoalieRestartWorld:
    def __init__(self, ball: Vector2D, opponents):
        self._ball = _Ball(ball.x(), ball.y())
        self._opponents = opponents

    def ball(self) -> _Ball:
        return self._ball

    def opponents(self):
        return self._opponents


class DecisionClearanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sp = ServerParam.i()

    def test_setplay_shield_forces_clearance_in_goalie_risk_box(self) -> None:
        profile = resolve_experiment_profile("exp_a_setplay_shield")
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 2.0, 0.0)
        me = Vector2D(ball.x(), 1.0)

        label = choose_defensive_clearance_label(profile, ball, me, False, self.sp)

        self.assertEqual(label, "shield_clear")

    def test_setplay_shield_does_not_force_clearance_outside_deep_box_without_pressure(self) -> None:
        profile = resolve_experiment_profile("exp_a_setplay_shield")
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 0.0)
        me = Vector2D(ball.x(), 1.0)

        label = choose_defensive_clearance_label(profile, ball, me, False, self.sp)

        self.assertIsNone(label)

    def test_box_clear_keeps_forcing_clearance_anywhere_inside_our_box(self) -> None:
        profile = resolve_experiment_profile("exp_c_box_clear")
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 4.5, 0.0)
        me = Vector2D(ball.x(), -2.0)

        label = choose_defensive_clearance_label(profile, ball, me, False, self.sp)

        self.assertEqual(label, "box_clear")

    def test_one_step_clear_is_forced_in_goalie_risk_box_even_without_pressure(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 2.0, 0.0)
        me = Vector2D(ball.x(), 0.0)

        self.assertTrue(should_use_one_step_clear(ball, me, False, self.sp))

    def test_one_step_clear_stays_off_in_shallow_zone_without_pressure(self) -> None:
        ball = Vector2D(-20.0, 0.0)
        me = Vector2D(-20.0, 0.0)

        self.assertFalse(should_use_one_step_clear(ball, me, False, self.sp))

    def test_goalie_restart_target_prefers_less_crowded_flank(self) -> None:
        world = _GoalieRestartWorld(
            Vector2D(-46.0, -6.0),
            [
                _Opponent(2, self.sp.pitch_half_length() - 7.0, self.sp.pitch_half_width() - 7.0),
                _Opponent(3, self.sp.pitch_half_length() - 12.5, 24.5),
                _Opponent(4, self.sp.pitch_half_length() - 11.0, 22.0),
            ],
        )

        target = choose_goalie_restart_target(world)

        self.assertLess(target.y(), 0.0)
        self.assertGreaterEqual(target.x(), 18.0)

    def test_setplay_screen_activates_when_opponent_can_arrive_first_in_our_half(self) -> None:
        profile = resolve_experiment_profile("exp_a_setplay_shield")

        active = setplay_screen_active(profile, Vector2D(-12.0, 3.0), self_min=5, mate_min=4, opp_min=4)

        self.assertTrue(active)

    def test_setplay_screen_stays_off_when_ball_is_not_deep_enough(self) -> None:
        profile = resolve_experiment_profile("exp_a_setplay_shield")

        active = setplay_screen_active(profile, Vector2D(-6.0, 0.0), self_min=5, mate_min=4, opp_min=4)

        self.assertFalse(active)

    def test_setplay_screen_retreat_bonus_prioritizes_defenders(self) -> None:
        defender_bonus = setplay_screen_retreat_bonus(3, True, -12.0)
        midfielder_bonus = setplay_screen_retreat_bonus(7, True, -12.0)
        forward_bonus = setplay_screen_retreat_bonus(10, True, -12.0)

        self.assertGreater(defender_bonus, midfielder_bonus)
        self.assertGreater(midfielder_bonus, forward_bonus)

    def test_disciplined_screen_only_activates_for_hybrid_shield_box_flank_profile(self) -> None:
        hybrid = resolve_experiment_profile("candidate_09")
        shield_only = resolve_experiment_profile("exp_a_setplay_shield")

        self.assertTrue(disciplined_screen_active(hybrid, Vector2D(-6.0, 2.0), 5, 4, 5))
        self.assertFalse(disciplined_screen_active(shield_only, Vector2D(-6.0, 2.0), 5, 4, 5))

    def test_disciplined_screen_retreat_bonus_favors_defenders(self) -> None:
        defender_bonus = disciplined_screen_retreat_bonus(2, True, -12.0)
        midfielder_bonus = disciplined_screen_retreat_bonus(7, True, -12.0)
        forward_bonus = disciplined_screen_retreat_bonus(10, True, -12.0)

        self.assertGreater(defender_bonus, midfielder_bonus)
        self.assertGreater(midfielder_bonus, forward_bonus)

if __name__ == "__main__":
    unittest.main()
