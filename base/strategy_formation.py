from __future__ import annotations

from pathlib import Path

from lib.formation.delaunay_triangulation import Formation
from lib.rcsc.types import GameModeType
from pyrusgeom.vector_2d import Vector2D


class _StrategyFormation:
    def __init__(self):
        formation_path = Path(__file__).resolve().parents[1] / "formations" / "443.conf"
        self.current_formation = Formation(str(formation_path))
        self._poses = [Vector2D(0, 0) for _ in range(11)]
        self._load_positions()

    def _load_positions(self) -> None:
        self._poses = [
            Vector2D(pos.x(), pos.y()) for pos in self.current_formation.get_poses()
        ]

    def update(self, wm):
        self_min = wm.intercept_table().self_reach_cycle()
        teammate_min = wm.intercept_table().teammate_reach_cycle()
        opponent_min = wm.intercept_table().opponent_reach_cycle()
        ball_pos = wm.ball().inertia_point(min(self_min, teammate_min, opponent_min))

        self.current_formation.update(ball_pos)
        self._load_positions()

        if self._must_stay_in_own_half(wm):
            for pos in self._poses:
                pos._x = min(pos.x(), -0.5)

    def get_pos(self, unum: int) -> Vector2D:
        return self._poses[unum - 1]

    @staticmethod
    def _must_stay_in_own_half(wm) -> bool:
        game_mode = wm.game_mode()
        game_mode_type = game_mode.type()

        if game_mode_type in (
            GameModeType.BeforeKickOff,
            GameModeType.AfterGoal_Left,
            GameModeType.AfterGoal_Right,
        ):
            return True

        opponent_restart_modes = {
            GameModeType.KickOff_Left,
            GameModeType.KickOff_Right,
            GameModeType.KickIn_Left,
            GameModeType.KickIn_Right,
            GameModeType.GoalKick_Left,
            GameModeType.GoalKick_Right,
            GameModeType.CornerKick_Left,
            GameModeType.CornerKick_Right,
            GameModeType.FreeKick_Left,
            GameModeType.FreeKick_Right,
            GameModeType.IndFreeKick_Left,
            GameModeType.IndFreeKick_Right,
            GameModeType.GoalieCatchBall_Left,
            GameModeType.GoalieCatchBall_Right,
        }

        return game_mode_type in opponent_restart_modes and game_mode.side() != wm.our_side()


class StrategyFormation:
    _i = _StrategyFormation()

    @staticmethod
    def i() -> _StrategyFormation:
        return StrategyFormation._i
