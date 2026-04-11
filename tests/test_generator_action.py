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

from base.generator_action import KickAction, ShootAction
from base.generator_shoot import BhvShhotGen
from pyrusgeom.angle_deg import AngleDeg
from pyrusgeom.vector_2d import Vector2D


class _Opponent:
    def __init__(self, unum: int, x: float, y: float, valid: bool = True):
        self._unum = unum
        self._pos = Vector2D(x, y)
        self._valid = valid

    def unum(self) -> int:
        return self._unum

    def pos(self) -> Vector2D:
        return self._pos

    def pos_valid(self) -> bool:
        return self._valid


class _World:
    def __init__(self, opponents):
        self._opponents = opponents

    def opponents(self):
        return self._opponents


class _Ball:
    def __init__(self, x: float, y: float):
        self._pos = Vector2D(x, y)

    def pos(self) -> Vector2D:
        return self._pos


class _ShootOpponent:
    def __init__(self, unum: int, x: float = -100.0, y: float = 0.0):
        self._unum = unum
        self._pos = Vector2D(x, y)

    def unum(self) -> int:
        return self._unum

    def is_tackling(self) -> bool:
        return False

    def pos(self) -> Vector2D:
        return self._pos

    def goalie(self) -> bool:
        return False

    def pos_count(self) -> int:
        return 0

    def is_ghost(self) -> bool:
        return False


class _ShootWorld:
    def __init__(self):
        self._ball = _Ball(35.0, 0.0)
        self._opponents = {unum: _ShootOpponent(unum) for unum in range(1, 12)}
        self._opponents[1] = None

    def ball(self) -> _Ball:
        return self._ball

    def their_player(self, unum: int):
        return self._opponents.get(unum)

    def get_opponent_goalie(self):
        return None


class KickActionTest(unittest.TestCase):
    def test_min_opponent_distance_returns_zero_for_no_valid_opponents(self) -> None:
        action = KickAction()
        action.target_ball_pos = Vector2D(10.0, 0.0)
        world = _World([None, _Opponent(0, 0.0, 0.0), _Opponent(9, 1.0, 1.0, valid=False)])

        self.assertEqual(action.calculate_min_opp_dist(world), 0.0)

    def test_min_opponent_distance_uses_valid_opponents_only(self) -> None:
        action = KickAction()
        action.target_ball_pos = Vector2D(10.0, 0.0)
        world = _World([_Opponent(3, 8.0, 0.0), _Opponent(4, 20.0, 0.0)])

        self.assertEqual(action.calculate_min_opp_dist(world), 2.0)

    def test_shoot_check_skips_missing_opponents(self) -> None:
        generator = BhvShhotGen()
        generator.total_count = 1
        world = _ShootWorld()
        target_point = Vector2D(52.5, 0.0)
        ball_move_angle = (target_point - world.ball().pos()).th()
        ball_move_dist = world.ball().pos().dist(target_point)

        created = generator.check_shoot(world, target_point, 3.0, ball_move_angle, ball_move_dist)

        self.assertTrue(created)
        self.assertEqual(len(generator.candidates), 1)

    def test_shoot_evaluation_handles_missing_goalie(self) -> None:
        generator = BhvShhotGen()
        course = ShootAction(1, Vector2D(52.5, 0.0), 3.0, AngleDeg(0.0), 17.5, 5)
        generator.candidates = [course]

        generator.evaluate_courses(_ShootWorld())

        self.assertGreater(course.score, 0.0)


if __name__ == "__main__":
    unittest.main()
