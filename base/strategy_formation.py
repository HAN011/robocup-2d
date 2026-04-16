from __future__ import annotations

from pathlib import Path

from lib.formation.delaunay_triangulation import Formation
from lib.debug.debug import log
from lib.rcsc.types import GameModeType
from player.experiment_profile import get_experiment_profile
from pyrusgeom.vector_2d import Vector2D


class _StrategyFormation:
    def __init__(self):
        base_dir = Path(__file__).resolve().parent
        vendor_dt_dir = (base_dir.parent / ".vendor" / "Pyrus2D" / "base" / "formation_dt").resolve()
        offense_path = (vendor_dt_dir / "offense_formation.conf").resolve()
        defense_path = (vendor_dt_dir / "defense_formation.conf").resolve()
        if not offense_path.exists():
            offense_path = (base_dir / "formation_dt" / "offense_formation.conf").resolve()
        if not defense_path.exists():
            defense_path = (base_dir / "formation_dt" / "defense_formation.conf").resolve()

        self._formations = {
            "normal": Formation(str((base_dir.parent / "formations" / "443.conf").resolve())),
            "offense": Formation(str(offense_path)),
            "defense": Formation(str(defense_path)),
            "before_kick_off": Formation(str((base_dir / "formation_dt" / "before_kick_off.conf").resolve())),
            "goalie_kick_our": Formation(str((base_dir / "formation_dt" / "goalie_kick_our_formation.conf").resolve())),
            "goalie_kick_opp": Formation(str((base_dir / "formation_dt" / "goalie_kick_opp_formation.conf").resolve())),
            "kickin_our": Formation(str((base_dir / "formation_dt" / "kickin_our_formation.conf").resolve())),
            "setplay_our": Formation(str((base_dir / "formation_dt" / "setplay_our_formation.conf").resolve())),
            "setplay_opp": Formation(str((base_dir / "formation_dt" / "setplay_opp_formation.conf").resolve())),
        }
        self._poses = [Vector2D(0, 0) for _ in range(12)]
        self._current_key = "normal"

    def _select_formation_key(self, wm) -> str:
        profile = get_experiment_profile()
        gm = wm.game_mode()
        gm_type = gm.type()

        if gm_type in (
            GameModeType.BeforeKickOff,
            GameModeType.AfterGoal_Left,
            GameModeType.AfterGoal_Right,
        ):
            key = "before_kick_off"
        elif gm_type in (
            GameModeType.GoalKick_Left,
            GameModeType.GoalKick_Right,
            GameModeType.GoalieCatchBall_Left,
            GameModeType.GoalieCatchBall_Right,
        ):
            key = "goalie_kick_our" if gm.side() == wm.our_side() else "goalie_kick_opp"
        elif gm_type in (
            GameModeType.KickIn_Left,
            GameModeType.KickIn_Right,
        ):
            key = "kickin_our" if gm.side() == wm.our_side() else "setplay_opp"
        elif gm_type in (
            GameModeType.CornerKick_Left,
            GameModeType.CornerKick_Right,
            GameModeType.FreeKick_Left,
            GameModeType.FreeKick_Right,
            GameModeType.IndFreeKick_Left,
            GameModeType.IndFreeKick_Right,
        ):
            key = "setplay_our" if gm.side() == wm.our_side() else "setplay_opp"
        else:
            ball_x = wm.ball().pos().x() if wm.ball().pos_valid() else 0.0
            ball_y = wm.ball().pos().y() if wm.ball().pos_valid() else 0.0
            self_min = wm.intercept_table().self_reach_cycle()
            teammate_min = wm.intercept_table().teammate_reach_cycle()
            opponent_min = wm.intercept_table().opponent_reach_cycle()

            our_reach = min(self_min, teammate_min)
            has_initiative = our_reach <= opponent_min + (1 if ball_x > 0.0 else 0)
            wide_defense = profile.flank_lock and abs(ball_y) > 18.0 and ball_x < 8.0
            deep_defense = profile.box_clear and ball_x < -30.0

            if ball_x < -18.0 or wide_defense or deep_defense or not has_initiative:
                key = "defense"
            elif ball_x > 10.0 and has_initiative:
                key = "offense"
            else:
                key = "normal"

        if wm.time().cycle() % 100 == 0:
            log.os_log().debug(f"formation_select key={key} mode={gm_type} cycle={wm.time().cycle()}")
        return key

    def update(self, wm):
        self_min = wm.intercept_table().self_reach_cycle()
        teammate_min = wm.intercept_table().teammate_reach_cycle()
        opponent_min = wm.intercept_table().opponent_reach_cycle()
        ball_pos = wm.ball().inertia_point(min(self_min, teammate_min, opponent_min))

        self._current_key = self._select_formation_key(wm)
        formation = self._formations[self._current_key]
        formation.update(ball_pos)

        poses = formation.get_poses()
        for unum in range(1, 12):
            pose = poses[unum - 1]
            self._poses[unum] = Vector2D(pose.x(), pose.y())

        if self._must_stay_in_own_half(wm):
            for unum in range(1, 12):
                self._poses[unum]._x = min(self._poses[unum].x(), -0.5)

    def get_pos(self, unum: int) -> Vector2D:
        if 1 <= unum <= 11:
            return self._poses[unum]
        return Vector2D(0, 0)

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
