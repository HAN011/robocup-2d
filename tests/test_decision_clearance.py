#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pyrus2d_bootstrap import bootstrap_pyrus2d


bootstrap_pyrus2d(PROJECT_ROOT)

from lib.rcsc.game_mode import GameMode
from lib.rcsc.game_time import GameTime
from lib.rcsc.types import GameModeType, SideID
from lib.rcsc.server_param import ServerParam
import player.decision as decision_module
from player.decision import (
    choose_defensive_clearance_label,
    choose_goalie_restart_target,
    choose_restart_safety_punt_target,
    choose_restart_wide_outlet_target,
    central_midfield_gap_plug_active,
    central_restart_terminal_guard_active,
    cyrus_like_opponent,
    decide_off_ball_action,
    decide_guarded_possession_action,
    decide_weak_team_restart_attack_action,
    decide_restart_safety_punt_action,
    decide_restart_wide_outlet_action,
    decide_opponent_central_setplay_wall_action,
    decide_opponent_flank_setplay_wall_action,
    disciplined_screen_active,
    disciplined_screen_retreat_bonus,
    decide_experiment_on_ball_action,
    find_flank_cutback_guard_target,
    find_goalmouth_lane_block_target,
    flank_cutback_guard_active,
    flank_restart_goalmouth_lock_active,
    flank_restart_goalmouth_lock_target,
    foxsy_cyrus_opponent,
    frontline_recovery_screen_active,
    frontline_recovery_screen_target,
    goalie_box_sweeper_intercept_active,
    goalie_flank_box_intercept_active,
    in_shooting_range,
    kickoff_counterpress_active,
    kickoff_counterpress_chaser_unum,
    kickoff_counterpress_target,
    kickoff_central_channel_anchor_active,
    kickoff_central_channel_anchor_target,
    kickoff_central_entry_stopper_active,
    kickoff_central_entry_stopper_target,
    kickoff_central_second_line_screen_active,
    kickoff_central_second_line_screen_target,
    kickoff_flank_goalpost_guard_active,
    kickoff_flank_goalpost_guard_target,
    kickoff_flank_backline_shelf_active,
    kickoff_flank_backline_shelf_target,
    kickoff_lane_lockdown_active,
    kickoff_lane_lockdown_target,
    kickoff_terminal_guard_active,
    narrow_kickoff_center_entry_clear_active,
    opponent_central_setplay_wall_active,
    opponent_central_setplay_wall_target,
    opponent_flank_setplay_wall_active,
    opponent_flank_setplay_wall_target,
    post_our_kickoff_midfield_plug_active,
    post_our_kickoff_recovery_active,
    recent_our_kickoff_context,
    setplay_screen_active,
    setplay_screen_retreat_bonus,
    select_box_entry_owner_unum,
    select_flank_ball_owner_unum,
    select_flank_cutback_guard_unum,
    select_flank_restart_goalmouth_lock_assignment,
    restart_safety_punt_active,
    restart_wide_outlet_active,
    should_avoid_goalie_backpass_catch,
    should_hold_box_entry_owner_lock,
    should_use_one_step_clear,
    update_recent_opp_central_restart,
    update_recent_opp_flank_restart,
    update_recent_our_kickoff,
    weak_team_attack_press_target,
    weak_team_overdrive_active,
    decide_weak_team_overdrive_on_ball_action,
    weak_team_killer_active,
    weak_team_press_only_active,
    weak_team_press_intercept_active,
    weak_team_press_intercept_action,
    weak_team_channel_entry_active,
    decide_weak_team_channel_entry_action,
    weak_team_channel_entry_target,
    choose_weak_team_channel_receiver,
    weak_team_restart_channel_entry_active,
    weak_team_restart_channel_entry_target,
    weak_team_frontline_slots_active,
    weak_team_frontline_slot_target,
    decide_weak_team_front_third_finish_action,
    weak_team_front_third_finish_active,
    weak_team_front_third_finish_target,
    weak_team_frontline_post_finish_active,
    weak_team_frontline_post_finish_target,
    decide_weak_team_natural_channel_feed_action,
    weak_team_natural_channel_feed_active,
    weak_team_natural_channel_feed_target,
    choose_weak_team_natural_channel_receiver,
    decide_weak_team_deep_cutback_action,
    weak_team_deep_cutback_active,
    weak_team_deep_cutback_target,
    choose_weak_team_deep_cutback_receiver,
    decide_weak_team_restart_grounder_action,
    weak_team_restart_grounder_active,
    weak_team_restart_grounder_target,
    choose_weak_team_restart_grounder_receiver,
    decide_weak_team_restart_second_finish_action,
    weak_team_restart_second_finish_active,
    weak_team_restart_second_finish_target,
    decide_weak_team_natural_high_frontline_finish_action,
    weak_team_natural_high_frontline_finish_active,
    weak_team_natural_high_frontline_finish_target,
)
from player.experiment_profile import resolve_experiment_profile
from pyrusgeom.vector_2d import Vector2D


class _NameWorld:
    def __init__(self, name: str):
        self._name = name

    def their_team_name(self) -> str:
        return self._name


class _Opponent:
    def __init__(
        self,
        unum: int,
        x: float,
        y: float,
        tackling: bool = False,
        tackle_count: int = 1000,
        kicking: bool = False,
    ):
        self._unum = unum
        self._pos = Vector2D(x, y)
        self._tackling = tackling
        self._tackle_count = tackle_count
        self._kicking = kicking

    def unum(self) -> int:
        return self._unum

    def pos(self) -> Vector2D:
        return self._pos

    def pos_count(self) -> int:
        return 0

    def is_ghost(self) -> bool:
        return False

    def kick(self) -> bool:
        return self._kicking

    def is_tackling(self) -> bool:
        return self._tackling

    def tackle_count(self) -> int:
        return self._tackle_count


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


class _Self:
    def __init__(self, goalie: bool = True, catch_cycle: int = 0, unum: int = 1, x: float = -50.0, y: float = 0.0):
        self._goalie = goalie
        self._catch_time = GameTime(catch_cycle, 0)
        self._unum = unum
        self._pos = Vector2D(x, y)

    def goalie(self) -> bool:
        return self._goalie

    def catch_time(self) -> GameTime:
        return self._catch_time

    def unum(self) -> int:
        return self._unum

    def pos(self) -> Vector2D:
        return self._pos

    def is_kickable(self) -> bool:
        return True

    def body(self):
        from pyrusgeom.angle_deg import AngleDeg

        return AngleDeg(0.0)


class _BackpassBall:
    def __init__(self, pos: Vector2D, dist_from_self: float, velocity: Vector2D | None = None):
        self._pos = pos
        self._dist_from_self = dist_from_self
        self._velocity = velocity or Vector2D(0.0, 0.0)

    def pos(self) -> Vector2D:
        return self._pos

    def pos_valid(self) -> bool:
        return True

    def dist_from_self(self) -> float:
        return self._dist_from_self

    def vel(self) -> Vector2D:
        return self._velocity

    def inertia_point(self, cycle: int) -> Vector2D:
        return self._pos + self._velocity * cycle


class _PossessionSelf:
    def __init__(self, x: float, y: float, unum: int = 2):
        self._pos = Vector2D(x, y)
        self._unum = unum

    def unum(self) -> int:
        return self._unum

    def pos(self) -> Vector2D:
        return self._pos

    def body(self):
        from pyrusgeom.angle_deg import AngleDeg

        return AngleDeg(0.0)


class _PossessionInterceptTable:
    def __init__(self, self_cycle: int = 2, teammate_cycle: int = 2, opponent_cycle: int = 6):
        self._self_cycle = self_cycle
        self._teammate_cycle = teammate_cycle
        self._opponent_cycle = opponent_cycle

    def self_reach_cycle(self) -> int:
        return self._self_cycle

    def teammate_reach_cycle(self) -> int:
        return self._teammate_cycle

    def opponent_reach_cycle(self) -> int:
        return self._opponent_cycle


class _Goalie(_Opponent):
    def goalie(self) -> bool:
        return True


class _Teammate(_Opponent):
    def __init__(
        self,
        unum: int,
        x: float,
        y: float,
        tackling: bool = False,
        tackle_count: int = 1000,
        kicking: bool = False,
    ):
        super().__init__(unum, x, y, tackling, tackle_count, kicking)

    def goalie(self) -> bool:
        return False


class _PossessionWorld:
    def __init__(
        self,
        me: Vector2D,
        ball: Vector2D,
        teammates=None,
        opponents=None,
        exist_kickable_opponents: bool = False,
        opponent_cycle: int = 6,
    ):
        self._self = _PossessionSelf(me.x(), me.y(), 2)
        self._ball = _BackpassBall(ball, 0.5)
        self._teammates = teammates or []
        self._opponents = opponents or []
        self._exist_kickable_opponents = exist_kickable_opponents
        self._intercept_table = _PossessionInterceptTable(opponent_cycle=opponent_cycle)

    def self(self) -> _PossessionSelf:
        return self._self

    def ball(self) -> _BackpassBall:
        return self._ball

    def our_goalie_unum(self) -> int:
        return 1

    def our_player(self, unum: int):
        if unum == 1:
            for teammate in self._teammates:
                if teammate.unum() == 1:
                    return teammate
        return None

    def teammates(self):
        return self._teammates

    def opponents(self):
        return self._opponents

    def exist_kickable_opponents(self) -> bool:
        return self._exist_kickable_opponents

    def intercept_table(self) -> _PossessionInterceptTable:
        return self._intercept_table


class _BackpassWorld:
    def __init__(
        self,
        last_kicker_side: SideID,
        ball: Vector2D,
        dist_from_self: float,
        mode=GameModeType.PlayOn,
        velocity: Vector2D | None = None,
        opponents=None,
        teammates=None,
        exist_kickable_opponents: bool = False,
        exist_kickable_teammates: bool = False,
        self_goalie: bool = True,
        self_unum: int = 1,
        self_pos: Vector2D | None = None,
        goalie: _Goalie | None = None,
        self_cycle: int = 5,
        teammate_cycle: int = 5,
        opponent_cycle: int = 3,
    ):
        self._last_kicker_side = last_kicker_side
        self._ball = _BackpassBall(ball, dist_from_self, velocity)
        self_pos = self_pos or Vector2D(-50.0, 0.0)
        self._self = _Self(self_goalie, unum=self_unum, x=self_pos.x(), y=self_pos.y())
        self._time = GameTime(200, 0)
        self._mode = GameMode(mode)
        self._opponents = opponents or []
        self._teammates = teammates or []
        self._exist_kickable_opponents = exist_kickable_opponents
        self._exist_kickable_teammates = exist_kickable_teammates
        self._goalie = goalie
        self._intercept_table = _PossessionInterceptTable(self_cycle, teammate_cycle, opponent_cycle)

    def self(self) -> _Self:
        return self._self

    def self_unum(self) -> int:
        return self._self.unum()

    def game_mode(self) -> GameMode:
        return self._mode

    def last_kicker_side(self) -> SideID:
        return self._last_kicker_side

    def our_side(self) -> SideID:
        return SideID.RIGHT

    def our_goalie_unum(self) -> int:
        return 1

    def our_player(self, unum: int):
        if unum == 1:
            return self._goalie
        return None

    def ball(self) -> _BackpassBall:
        return self._ball

    def time(self) -> GameTime:
        return self._time

    def set_cycle(self, cycle: int) -> None:
        self._time = GameTime(cycle, 0)

    def set_mode(self, mode: GameModeType) -> None:
        self._mode = GameMode(mode)

    def set_ball_distance(self, dist_from_self: float) -> None:
        self._ball._dist_from_self = dist_from_self

    def exist_kickable_opponents(self) -> bool:
        return self._exist_kickable_opponents

    def exist_kickable_teammates(self) -> bool:
        return self._exist_kickable_teammates

    def opponents(self):
        return self._opponents

    def teammates(self):
        return self._teammates

    def intercept_table(self) -> _PossessionInterceptTable:
        return self._intercept_table


class _OffBallWorld:
    def __init__(
        self,
        self_unum: int,
        ball: Vector2D,
        players: list[_Teammate],
        self_cycle: int = 5,
        teammate_cycle: int = 5,
        opponent_cycle: int = 1,
        exist_kickable_opponents: bool = True,
        exist_kickable_teammates: bool = False,
        mode=GameModeType.PlayOn,
    ):
        self._players = {player.unum(): player for player in players}
        if self_unum not in self._players:
            self._players[self_unum] = _Teammate(self_unum, ball.x() + 12.0, ball.y())
        self._self = self._players[self_unum]
        self._ball = _BackpassBall(ball, 10.0)
        self._intercept_table = _PossessionInterceptTable(self_cycle, teammate_cycle, opponent_cycle)
        self._exist_kickable_opponents = exist_kickable_opponents
        self._exist_kickable_teammates = exist_kickable_teammates
        self._mode = GameMode(mode)
        self._time = GameTime(200, 0)

    def self(self):
        return self._self

    def self_unum(self) -> int:
        return self._self.unum()

    def ball(self) -> _BackpassBall:
        return self._ball

    def our_player(self, unum: int):
        return self._players.get(unum)

    def intercept_table(self) -> _PossessionInterceptTable:
        return self._intercept_table

    def game_mode(self) -> GameMode:
        return self._mode

    def time(self) -> GameTime:
        return self._time

    def set_cycle(self, cycle: int) -> None:
        self._time = GameTime(cycle, 0)

    def exist_kickable_opponents(self) -> bool:
        return self._exist_kickable_opponents

    def exist_kickable_teammates(self) -> bool:
        return self._exist_kickable_teammates

    def their_team_name(self) -> str:
        return ""


class DecisionClearanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sp = ServerParam.i()
        decision_module._RECENT_TEAMMATE_TOUCH_CYCLE = -1000
        decision_module._RECENT_OUR_KICKOFF_CYCLE = -1000
        decision_module._RECENT_NON_KICKOFF_RESTART_CYCLE = -1000
        decision_module._RECENT_OPP_CENTRAL_RESTART_CYCLE = -1000
        decision_module._RECENT_OPP_FLANK_RESTART_CYCLE = -1000

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

    def test_central_box_one_step_clear_extends_only_new_profile(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 0.0)
        me = Vector2D(ball.x(), 0.0)

        self.assertFalse(should_use_one_step_clear(ball, me, False, self.sp, resolve_experiment_profile("candidate_12")))
        self.assertTrue(should_use_one_step_clear(ball, me, False, self.sp, resolve_experiment_profile("candidate_16")))

    def test_keyed_central_box_one_step_clear_only_targets_selected_opponents(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 0.0)
        me = Vector2D(ball.x(), 0.0)
        profile = resolve_experiment_profile("candidate_17")

        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertTrue(should_use_one_step_clear(ball, me, False, self.sp, profile, _NameWorld("")))
        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "helios"}):
            self.assertFalse(should_use_one_step_clear(ball, me, False, self.sp, profile, _NameWorld("")))

    def test_narrow_central_box_one_step_clear_rejects_half_space_ball(self) -> None:
        me = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 0.0)
        central_ball = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 3.0)
        half_space_ball = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 10.0)
        profile = resolve_experiment_profile("candidate_18")

        self.assertTrue(should_use_one_step_clear(central_ball, me, False, self.sp, profile))
        self.assertFalse(should_use_one_step_clear(half_space_ball, me, False, self.sp, profile))

    def test_keyed_narrow_central_box_one_step_clear_combines_both_guards(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 3.0)
        wide_ball = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 10.0)
        me = Vector2D(ball.x(), 0.0)
        profile = resolve_experiment_profile("candidate_19")

        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertTrue(should_use_one_step_clear(ball, me, False, self.sp, profile, _NameWorld("")))
            self.assertFalse(should_use_one_step_clear(wide_ball, me, False, self.sp, profile, _NameWorld("")))
        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "helios"}):
            self.assertFalse(should_use_one_step_clear(ball, me, False, self.sp, profile, _NameWorld("")))

    def test_cyrus2d_narrow_central_box_one_step_clear_excludes_starter2d(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 3.0)
        wide_ball = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 10.0)
        me = Vector2D(ball.x(), 0.0)
        profile = resolve_experiment_profile("candidate_20")

        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertTrue(should_use_one_step_clear(ball, me, False, self.sp, profile, _NameWorld("")))
            self.assertFalse(should_use_one_step_clear(wide_ball, me, False, self.sp, profile, _NameWorld("")))
        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertFalse(should_use_one_step_clear(ball, me, False, self.sp, profile, _NameWorld("")))

    def test_kickoff_terminal_guard_forces_central_one_step_only_after_our_kickoff(self) -> None:
        profile = resolve_experiment_profile("candidate_38")
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 4.0)
        me = Vector2D(ball.x(), 2.0)
        world = _BackpassWorld(
            SideID.RIGHT,
            ball,
            3.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=3,
            self_pos=me,
        )
        world.set_cycle(9000)

        update_recent_our_kickoff(world)
        self.assertFalse(kickoff_terminal_guard_active(world, profile=profile))

        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(9060)

        self.assertTrue(kickoff_terminal_guard_active(world, profile=profile))
        self.assertTrue(should_use_one_step_clear(ball, me, False, self.sp, profile, world))

        world.set_cycle(9261)
        self.assertFalse(kickoff_terminal_guard_active(world, profile=profile))

    def test_kickoff_terminal_guard_rejects_wide_terminal_clear(self) -> None:
        profile = resolve_experiment_profile("candidate_38")
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 20.0)
        me = Vector2D(ball.x(), 18.0)
        world = _BackpassWorld(
            SideID.RIGHT,
            ball,
            3.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=2,
            self_pos=me,
        )
        world.set_cycle(9400)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(9460)

        self.assertTrue(kickoff_terminal_guard_active(world, profile=profile))
        self.assertFalse(should_use_one_step_clear(ball, me, False, self.sp, profile, world))

    def test_central_restart_terminal_guard_forces_one_step_after_center_setplay(self) -> None:
        profile = resolve_experiment_profile("candidate_42")
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 4.0, 6.0)
        me = Vector2D(ball.x() - 1.0, 4.0)
        world = _BackpassWorld(
            SideID.LEFT,
            ball,
            3.0,
            mode=GameModeType.FreeKick_Left,
            self_goalie=False,
            self_unum=3,
            self_pos=me,
            exist_kickable_opponents=True,
            opponent_cycle=2,
        )
        world.set_cycle(12000)

        update_recent_opp_central_restart(world)
        self.assertFalse(central_restart_terminal_guard_active(world, profile=profile))

        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(12045)

        self.assertTrue(central_restart_terminal_guard_active(world, profile=profile))
        self.assertTrue(should_use_one_step_clear(ball, me, False, self.sp, profile, world))

    def test_central_restart_terminal_guard_rejects_wide_terminal_clear(self) -> None:
        profile = resolve_experiment_profile("candidate_42")
        ball = Vector2D(-22.0, 18.0)
        me = Vector2D(ball.x() - 1.0, 17.0)
        world = _BackpassWorld(
            SideID.LEFT,
            ball,
            3.0,
            mode=GameModeType.FreeKick_Left,
            self_goalie=False,
            self_unum=2,
            self_pos=me,
            exist_kickable_opponents=True,
            opponent_cycle=2,
        )
        world.set_cycle(12100)

        update_recent_opp_central_restart(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(12145)

        self.assertFalse(central_restart_terminal_guard_active(world, profile=profile))
        self.assertFalse(should_use_one_step_clear(ball, me, False, self.sp, profile, world))

    def test_central_restart_terminal_guard_covers_center_kickoff_terminal(self) -> None:
        profile = resolve_experiment_profile("candidate_42")
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 4.0, 5.0)
        me = Vector2D(ball.x(), 4.0)
        world = _BackpassWorld(
            SideID.RIGHT,
            ball,
            3.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=4,
            self_pos=me,
            exist_kickable_opponents=True,
            opponent_cycle=2,
        )
        world.set_cycle(12200)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(12270)

        self.assertTrue(central_restart_terminal_guard_active(world, profile=profile))
        self.assertTrue(should_use_one_step_clear(ball, me, False, self.sp, profile, world))

    def test_post_kickoff_recovery_tracks_only_our_kickoff_window(self) -> None:
        profile = resolve_experiment_profile("candidate_21")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(0.0, 0.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=6,
            self_pos=Vector2D(-10.0, 0.0),
        )
        world.set_cycle(1000)

        update_recent_our_kickoff(world)
        self.assertFalse(post_our_kickoff_recovery_active(world, profile=profile))

        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(1080)
        self.assertTrue(post_our_kickoff_recovery_active(world, profile=profile))

        world.set_cycle(1121)
        self.assertFalse(post_our_kickoff_recovery_active(world, profile=profile))

    def test_post_kickoff_recovery_ignores_opponent_kickoff(self) -> None:
        profile = resolve_experiment_profile("candidate_21")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(0.0, 0.0),
            10.0,
            mode=GameModeType.KickOff_Left,
            self_goalie=False,
            self_unum=6,
            self_pos=Vector2D(-10.0, 0.0),
        )
        world.set_cycle(1000)

        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(1040)

        self.assertFalse(post_our_kickoff_recovery_active(world, profile=profile))

    def test_starter2d_post_kickoff_recovery_is_opponent_gated(self) -> None:
        profile = resolve_experiment_profile("candidate_22")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(0.0, 0.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=6,
            self_pos=Vector2D(-10.0, 0.0),
        )
        world.set_cycle(1000)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(1040)

        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertTrue(post_our_kickoff_recovery_active(world, profile=profile))
        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "helios"}):
            self.assertFalse(post_our_kickoff_recovery_active(world, profile=profile))

    def test_post_kickoff_midfield_plug_tracks_central_window(self) -> None:
        profile = resolve_experiment_profile("candidate_24")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(0.0, 0.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=6,
            self_pos=Vector2D(-10.0, 0.0),
        )
        world.set_cycle(1000)

        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(1060)
        self.assertTrue(post_our_kickoff_midfield_plug_active(world, profile=profile))

        world.ball()._pos = Vector2D(0.0, 24.0)
        self.assertFalse(post_our_kickoff_midfield_plug_active(world, profile=profile))

        world.ball()._pos = Vector2D(0.0, 0.0)
        world.set_cycle(1121)
        self.assertFalse(post_our_kickoff_midfield_plug_active(world, profile=profile))

    def test_central_midfield_gap_plug_tracks_central_pressure_or_deep_ball(self) -> None:
        profile = resolve_experiment_profile("candidate_25")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-10.0, 0.0),
            10.0,
            mode=GameModeType.PlayOn,
            self_goalie=False,
            self_unum=6,
            self_pos=Vector2D(-10.0, 0.0),
        )

        self.assertTrue(central_midfield_gap_plug_active(world, profile=profile))

        world.ball()._pos = Vector2D(-10.0, 22.0)
        self.assertFalse(central_midfield_gap_plug_active(world, profile=profile))

        world.ball()._pos = Vector2D(-6.0, 0.0)
        self.assertFalse(central_midfield_gap_plug_active(world, profile=profile))

        world.ball()._pos = Vector2D(-22.0, 0.0)
        self.assertTrue(central_midfield_gap_plug_active(world, profile=profile))

    def test_central_midfield_gap_plug_stays_off_outside_play_on(self) -> None:
        profile = resolve_experiment_profile("candidate_25")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-20.0, 0.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=6,
            self_pos=Vector2D(-10.0, 0.0),
        )

        self.assertFalse(central_midfield_gap_plug_active(world, profile=profile))

    def test_frontline_recovery_screen_tracks_playon_lost_initiative(self) -> None:
        profile = resolve_experiment_profile("candidate_32")
        world = _OffBallWorld(
            10,
            Vector2D(-4.0, 8.0),
            [_Teammate(10, 8.0, 0.0)],
            self_cycle=6,
            teammate_cycle=5,
            opponent_cycle=4,
        )

        self.assertTrue(frontline_recovery_screen_active(world, profile=profile))

        world.ball()._pos = Vector2D(16.0, 8.0)
        self.assertFalse(frontline_recovery_screen_active(world, profile=profile))

    def test_frontline_recovery_screen_stays_off_when_we_control_or_restart(self) -> None:
        profile = resolve_experiment_profile("candidate_32")
        controlled_world = _OffBallWorld(
            10,
            Vector2D(-4.0, 8.0),
            [_Teammate(10, 8.0, 0.0)],
            exist_kickable_teammates=True,
        )
        restart_world = _OffBallWorld(
            10,
            Vector2D(-4.0, 8.0),
            [_Teammate(10, 8.0, 0.0)],
            mode=GameModeType.KickOff_Left,
        )

        self.assertFalse(frontline_recovery_screen_active(controlled_world, profile=profile))
        self.assertFalse(frontline_recovery_screen_active(restart_world, profile=profile))

    def test_frontline_recovery_screen_targets_three_frontline_lanes(self) -> None:
        ball = Vector2D(-12.0, 18.0)

        left = frontline_recovery_screen_target(9, ball, self.sp)
        center = frontline_recovery_screen_target(10, ball, self.sp)
        right = frontline_recovery_screen_target(11, ball, self.sp)

        self.assertLess(center.x(), -20.0)
        self.assertLess(left.y(), center.y())
        self.assertGreater(right.y(), center.y())
        self.assertGreater(right.y(), 12.0)

    def test_decide_off_ball_action_uses_frontline_recovery_screen(self) -> None:
        world = _OffBallWorld(
            10,
            Vector2D(-6.0, 6.0),
            [_Teammate(10, 8.0, 0.0)],
            self_cycle=6,
            teammate_cycle=5,
            opponent_cycle=4,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_32"}):
            action = decide_off_ball_action(world)

        self.assertEqual(action.label, "frontline_recovery_screen")
        self.assertIsNotNone(action.decision_target)
        self.assertLess(action.decision_target.x(), -15.0)

    def test_kickoff_counterpress_tracks_our_kickoff_window(self) -> None:
        profile = resolve_experiment_profile("candidate_33")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(14.0, 18.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=11,
            self_pos=Vector2D(4.0, 20.0),
        )
        world.set_cycle(2000)

        update_recent_our_kickoff(world)
        self.assertFalse(kickoff_counterpress_active(world, profile=profile))

        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(2080)
        self.assertTrue(kickoff_counterpress_active(world, profile=profile))

        world.set_cycle(2161)
        self.assertFalse(kickoff_counterpress_active(world, profile=profile))

    def test_kickoff_counterpress_ignores_controlled_or_deep_defensive_ball(self) -> None:
        profile = resolve_experiment_profile("candidate_33")
        controlled_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(8.0, 18.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=11,
            self_pos=Vector2D(4.0, 20.0),
            exist_kickable_teammates=True,
        )
        controlled_world.set_cycle(2000)
        update_recent_our_kickoff(controlled_world)
        controlled_world.set_mode(GameModeType.PlayOn)
        controlled_world.set_cycle(2040)

        deep_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-22.0, 18.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=11,
            self_pos=Vector2D(-8.0, 20.0),
        )
        deep_world.set_cycle(3000)
        update_recent_our_kickoff(deep_world)
        deep_world.set_mode(GameModeType.PlayOn)
        deep_world.set_cycle(3040)

        self.assertFalse(kickoff_counterpress_active(controlled_world, profile=profile))
        self.assertFalse(kickoff_counterpress_active(deep_world, profile=profile))

    def test_kickoff_counterpress_targets_ballside_and_inside_lanes(self) -> None:
        wide_ball = Vector2D(18.0, 22.0)

        self.assertEqual(kickoff_counterpress_chaser_unum(wide_ball), 11)
        ballside = kickoff_counterpress_target(11, wide_ball, self.sp)
        center = kickoff_counterpress_target(10, wide_ball, self.sp)
        far_side = kickoff_counterpress_target(9, wide_ball, self.sp)

        self.assertGreater(ballside.y(), center.y())
        self.assertGreater(center.y(), far_side.y())
        self.assertLess(ballside.x(), wide_ball.x())
        self.assertLess(far_side.x(), center.x())

    def test_decide_off_ball_action_uses_kickoff_counterpress_before_frontline_screen(self) -> None:
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(12.0, 18.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=11,
            self_pos=Vector2D(4.0, 20.0),
            self_cycle=10,
            teammate_cycle=6,
            opponent_cycle=4,
        )
        world.set_cycle(4000)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(4060)

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_33"}):
            action = decide_off_ball_action(world)

        self.assertEqual(action.label, "kickoff_counterpress")
        self.assertIsNotNone(action.decision_target)
        self.assertGreater(action.decision_target.x(), -10.0)

    def test_kickoff_lane_lockdown_extends_window_for_defensive_second_line(self) -> None:
        profile = resolve_experiment_profile("candidate_37")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-8.0, 22.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=8,
            self_pos=Vector2D(-12.0, 14.0),
            self_cycle=8,
            teammate_cycle=5,
            opponent_cycle=4,
        )
        world.set_cycle(5000)

        update_recent_our_kickoff(world)
        self.assertFalse(kickoff_lane_lockdown_active(world, profile=profile))

        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(5180)

        target = kickoff_lane_lockdown_target(world, profile=profile)

        self.assertTrue(kickoff_lane_lockdown_active(world, profile=profile))
        self.assertIsNotNone(target)
        self.assertLess(target.x(), -27.0)
        self.assertGreater(target.y(), 10.0)

        world.set_cycle(5221)
        self.assertFalse(kickoff_lane_lockdown_active(world, profile=profile))

    def test_kickoff_lane_lockdown_does_not_pull_fastest_interceptor(self) -> None:
        profile = resolve_experiment_profile("candidate_37")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-8.0, -22.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=6,
            self_pos=Vector2D(-14.0, -16.0),
            self_cycle=2,
            teammate_cycle=6,
            opponent_cycle=5,
        )
        world.set_cycle(6000)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(6060)

        self.assertTrue(kickoff_lane_lockdown_active(world, profile=profile))
        self.assertIsNone(kickoff_lane_lockdown_target(world, profile=profile))

    def test_kickoff_central_channel_anchor_tracks_center_reentry(self) -> None:
        profile = resolve_experiment_profile("candidate_39")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-10.0, 2.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=3,
            self_pos=Vector2D(-32.0, -4.0),
            self_cycle=8,
            teammate_cycle=5,
            opponent_cycle=4,
        )
        world.set_cycle(6500)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(6680)

        target = kickoff_central_channel_anchor_target(world, profile=profile)

        self.assertTrue(kickoff_central_channel_anchor_active(world, profile=profile))
        self.assertIsNotNone(target)
        self.assertLess(target.x(), -27.0)
        self.assertLess(target.y(), 1.0)

        world.ball()._pos = Vector2D(-10.0, 14.0)
        self.assertFalse(kickoff_central_channel_anchor_active(world, profile=profile))

    def test_kickoff_central_channel_anchor_takes_precedence_over_lane_lockdown(self) -> None:
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-12.0, -2.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=7,
            self_pos=Vector2D(-24.0, 0.0),
            self_cycle=8,
            teammate_cycle=5,
            opponent_cycle=4,
        )
        world.set_cycle(6800)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(6980)

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_39"}):
            action = decide_off_ball_action(world)

        self.assertEqual(action.label, "kickoff_central_channel_anchor")
        self.assertIsNotNone(action.decision_target)
        self.assertLess(action.decision_target.x(), -20.0)
        self.assertGreater(action.decision_target.y(), -5.0)
        self.assertLess(action.decision_target.y(), 5.0)

    def test_cyrus_kickoff_central_anchor_is_opponent_gated(self) -> None:
        profile = resolve_experiment_profile("candidate_40")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-12.0, 0.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=3,
            self_pos=Vector2D(-32.0, -4.0),
            self_cycle=8,
            teammate_cycle=5,
            opponent_cycle=4,
        )
        world.set_cycle(6900)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(7080)

        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertTrue(kickoff_central_channel_anchor_active(world, profile=profile))
        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "foxsy_cyrus"}):
            self.assertFalse(kickoff_central_channel_anchor_active(world, profile=profile))
        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "wrighteagle"}):
            self.assertFalse(kickoff_central_channel_anchor_active(world, profile=profile))

    def test_kickoff_flank_goalpost_guard_tracks_deep_wide_reentry(self) -> None:
        profile = resolve_experiment_profile("candidate_41")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-25.0, 18.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=5,
            self_pos=Vector2D(-36.0, 18.0),
            self_cycle=8,
            teammate_cycle=5,
            opponent_cycle=4,
        )
        world.set_cycle(7100)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(7280)

        target = kickoff_flank_goalpost_guard_target(world, profile=profile)

        self.assertTrue(kickoff_flank_goalpost_guard_active(world, profile=profile))
        self.assertIsNotNone(target)
        self.assertLess(target.x(), world.ball().pos().x())
        self.assertGreater(target.y(), 10.0)

        world.ball()._pos = Vector2D(-25.0, 4.0)
        self.assertFalse(kickoff_flank_goalpost_guard_active(world, profile=profile))

    def test_kickoff_flank_goalpost_guard_precedes_lane_lockdown(self) -> None:
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-25.0, -18.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=2,
            self_pos=Vector2D(-36.0, -18.0),
            self_cycle=8,
            teammate_cycle=5,
            opponent_cycle=4,
        )
        world.set_cycle(7200)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(7380)

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_41"}):
            action = decide_off_ball_action(world)

        self.assertEqual(action.label, "kickoff_flank_goalpost_guard")
        self.assertIsNotNone(action.block_target)
        self.assertLess(action.decision_target.x(), -30.0)
        self.assertLess(action.decision_target.y(), -10.0)

    def test_kickoff_central_second_line_screen_tracks_deep_central_kickoff_leak(self) -> None:
        profile = resolve_experiment_profile("candidate_49")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-30.0, 6.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=7,
            self_pos=Vector2D(-24.0, 0.0),
            self_cycle=8,
            teammate_cycle=5,
            opponent_cycle=4,
        )
        world.set_cycle(7250)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(7430)

        target = kickoff_central_second_line_screen_target(world, profile=profile)

        self.assertTrue(kickoff_central_second_line_screen_active(world, profile=profile))
        self.assertIsNotNone(target)
        self.assertLess(target.x(), world.ball().pos().x())
        self.assertLess(abs(target.y()), 5.0)

        world.ball()._pos = Vector2D(-30.0, 14.0)
        self.assertFalse(kickoff_central_second_line_screen_active(world, profile=profile))

    def test_kickoff_central_second_line_screen_does_not_pull_fastest_interceptor(self) -> None:
        profile = resolve_experiment_profile("candidate_49")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-30.0, 4.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=7,
            self_pos=Vector2D(-24.0, 0.0),
            self_cycle=2,
            teammate_cycle=6,
            opponent_cycle=5,
        )
        world.set_cycle(7275)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(7450)

        self.assertTrue(kickoff_central_second_line_screen_active(world, profile=profile))
        self.assertIsNone(kickoff_central_second_line_screen_target(world, profile=profile))

    def test_kickoff_central_entry_stopper_tracks_penalty_arc_leak(self) -> None:
        profile = resolve_experiment_profile("candidate_51")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-28.0, 3.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=4,
            self_pos=Vector2D(-34.0, 5.0),
            self_cycle=8,
            teammate_cycle=5,
            opponent_cycle=4,
        )
        world.set_cycle(8300)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(8490)

        target = kickoff_central_entry_stopper_target(world, profile=profile)

        self.assertTrue(kickoff_central_entry_stopper_active(world, profile=profile))
        self.assertIsNotNone(target)
        self.assertLess(target.x(), world.ball().pos().x())
        self.assertLess(abs(target.y()), 5.0)

        world.ball()._pos = Vector2D(-28.0, 10.0)
        self.assertFalse(kickoff_central_entry_stopper_active(world, profile=profile))

    def test_kickoff_central_entry_stopper_does_not_pull_fastest_interceptor(self) -> None:
        profile = resolve_experiment_profile("candidate_51")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-28.0, -2.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=3,
            self_pos=Vector2D(-34.0, -5.0),
            self_cycle=2,
            teammate_cycle=6,
            opponent_cycle=5,
        )
        world.set_cycle(8325)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(8510)

        self.assertTrue(kickoff_central_entry_stopper_active(world, profile=profile))
        self.assertIsNone(kickoff_central_entry_stopper_target(world, profile=profile))

    def test_decide_off_ball_action_uses_entry_stopper_before_second_line(self) -> None:
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-27.0, 3.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=4,
            self_pos=Vector2D(-34.0, 5.0),
            self_cycle=8,
            teammate_cycle=5,
            opponent_cycle=4,
        )
        world.set_cycle(8350)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(8530)

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_51"}):
            action = decide_off_ball_action(world)

        self.assertEqual(action.label, "kickoff_central_entry_stopper")
        self.assertIsNotNone(action.block_target)
        self.assertLess(action.decision_target.x(), world.ball().pos().x())
        self.assertLess(abs(action.decision_target.y()), 5.0)

    def test_selective_kickoff_entry_stopper_is_opponent_gated(self) -> None:
        profile = resolve_experiment_profile("candidate_52")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-28.0, 3.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=4,
            self_pos=Vector2D(-34.0, 5.0),
            self_cycle=8,
            teammate_cycle=5,
            opponent_cycle=4,
        )
        world.set_cycle(8375)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(8550)

        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "foxsy_cyrus"}):
            self.assertTrue(kickoff_central_entry_stopper_active(world, profile=profile))

        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertTrue(kickoff_central_entry_stopper_active(world, profile=profile))

        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "cyrus_team"}):
            self.assertFalse(kickoff_central_entry_stopper_active(world, profile=profile))

        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertFalse(kickoff_central_entry_stopper_active(world, profile=profile))

    def test_strict_kickoff_context_expires_after_intervening_opponent_restart(self) -> None:
        profile = resolve_experiment_profile("candidate_50")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-18.0, 6.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=7,
            self_pos=Vector2D(-24.0, 0.0),
            self_cycle=8,
            teammate_cycle=5,
            opponent_cycle=4,
        )
        world.set_cycle(8100)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(8160)

        self.assertTrue(recent_our_kickoff_context(world, profile=profile))
        self.assertTrue(kickoff_central_channel_anchor_active(world, profile=profile))

        world.set_mode(GameModeType.FreeKick_Left)
        world.set_cycle(8180)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(8190)

        self.assertFalse(recent_our_kickoff_context(world, profile=profile))
        self.assertFalse(kickoff_central_channel_anchor_active(world, profile=profile))
        self.assertFalse(kickoff_lane_lockdown_active(world, profile=profile))

    def test_decide_off_ball_action_uses_second_line_screen_before_lane_lockdown(self) -> None:
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-30.0, 5.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=6,
            self_pos=Vector2D(-24.0, -8.0),
            self_cycle=8,
            teammate_cycle=5,
            opponent_cycle=4,
        )
        world.set_cycle(7280)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(7460)

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_49"}):
            action = decide_off_ball_action(world)

        self.assertEqual(action.label, "kickoff_central_second_line_screen")
        self.assertIsNotNone(action.decision_target)
        self.assertLess(action.decision_target.x(), world.ball().pos().x())
        self.assertLess(action.decision_target.y(), -4.0)

    def test_kickoff_flank_backline_shelf_tracks_far_side_backline_after_our_kickoff(self) -> None:
        profile = resolve_experiment_profile("candidate_46")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-27.0, 18.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=3,
            self_pos=Vector2D(-35.0, -2.0),
            self_cycle=8,
            teammate_cycle=5,
            opponent_cycle=4,
        )
        world.set_cycle(7300)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(7480)

        target = kickoff_flank_backline_shelf_target(world, profile=profile)

        self.assertTrue(kickoff_flank_backline_shelf_active(world, profile=profile))
        self.assertIsNotNone(target)
        self.assertLess(target.x(), -38.0)
        self.assertLess(target.y(), 0.0)

        world.ball()._pos = Vector2D(-27.0, 5.0)
        self.assertFalse(kickoff_flank_backline_shelf_active(world, profile=profile))

    def test_kickoff_flank_backline_shelf_does_not_pull_fastest_interceptor(self) -> None:
        profile = resolve_experiment_profile("candidate_46")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-27.0, -18.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=4,
            self_pos=Vector2D(-36.0, 1.0),
            self_cycle=2,
            teammate_cycle=6,
            opponent_cycle=5,
        )
        world.set_cycle(7350)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(7530)

        self.assertTrue(kickoff_flank_backline_shelf_active(world, profile=profile))
        self.assertIsNone(kickoff_flank_backline_shelf_target(world, profile=profile))

    def test_decide_off_ball_action_uses_backline_shelf_before_lane_lockdown(self) -> None:
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-27.0, 18.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=3,
            self_pos=Vector2D(-35.0, -2.0),
            self_cycle=8,
            teammate_cycle=5,
            opponent_cycle=4,
        )
        world.set_cycle(7400)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(7580)

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_46"}):
            action = decide_off_ball_action(world)

        self.assertEqual(action.label, "kickoff_flank_backline_shelf")
        self.assertIsNotNone(action.decision_target)
        self.assertLess(action.decision_target.x(), -38.0)
        self.assertLess(action.decision_target.y(), 0.0)

    def test_decide_off_ball_action_uses_kickoff_lane_lockdown_after_counterpress_window(self) -> None:
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-10.0, -20.0),
            10.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=6,
            self_pos=Vector2D(-12.0, -8.0),
            self_cycle=8,
            teammate_cycle=5,
            opponent_cycle=4,
        )
        world.set_cycle(7000)
        update_recent_our_kickoff(world)
        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(7180)

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_37"}):
            action = decide_off_ball_action(world)

        self.assertEqual(action.label, "kickoff_lane_lockdown")
        self.assertIsNotNone(action.decision_target)
        self.assertLess(action.decision_target.x(), -27.0)
        self.assertLess(action.decision_target.y(), -10.0)

    def test_opponent_flank_setplay_wall_tracks_only_opponent_wide_setplay(self) -> None:
        profile = resolve_experiment_profile("candidate_34")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-8.0, 24.0),
            10.0,
            mode=GameModeType.FreeKick_Left,
            self_goalie=False,
            self_unum=6,
            self_pos=Vector2D(-20.0, 18.0),
        )

        self.assertTrue(opponent_flank_setplay_wall_active(world, profile=profile))

        world.set_mode(GameModeType.FreeKick_Right)
        self.assertFalse(opponent_flank_setplay_wall_active(world, profile=profile))

        world.set_mode(GameModeType.FreeKick_Left)
        world.ball()._pos = Vector2D(-8.0, 6.0)
        self.assertFalse(opponent_flank_setplay_wall_active(world, profile=profile))

    def test_opponent_flank_setplay_wall_target_keeps_legal_distance(self) -> None:
        ball = Vector2D(-8.0, 24.0)

        near_side = opponent_flank_setplay_wall_target(6, ball, self.sp)
        cutback = opponent_flank_setplay_wall_target(7, ball, self.sp)
        central = opponent_flank_setplay_wall_target(8, ball, self.sp)

        self.assertGreaterEqual(near_side.dist(ball), 10.0)
        self.assertGreater(near_side.y(), cutback.y())
        self.assertGreater(cutback.y(), central.y())
        self.assertLess(central.x(), ball.x())

    def test_decide_opponent_flank_setplay_wall_action_overrides_setplay_move(self) -> None:
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-8.0, -24.0),
            10.0,
            mode=GameModeType.KickIn_Left,
            self_goalie=False,
            self_unum=6,
            self_pos=Vector2D(-20.0, -18.0),
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_34"}):
            action = decide_opponent_flank_setplay_wall_action(world)

        self.assertIsNotNone(action)
        self.assertEqual(action.label, "opponent_flank_setplay_wall")
        self.assertIsNotNone(action.decision_target)
        self.assertLess(action.decision_target.y(), 0.0)

    def test_opponent_central_setplay_wall_tracks_only_opponent_central_free_kick(self) -> None:
        profile = resolve_experiment_profile("candidate_43")
        world = _BackpassWorld(
            SideID.LEFT,
            Vector2D(-18.0, 4.0),
            8.0,
            mode=GameModeType.FreeKick_Left,
            self_goalie=False,
            self_unum=4,
            self_pos=Vector2D(-35.0, 5.0),
        )

        self.assertTrue(opponent_central_setplay_wall_active(world, profile=profile))

        world.ball()._pos = Vector2D(-18.0, 18.0)
        self.assertFalse(opponent_central_setplay_wall_active(world, profile=profile))

        world.ball()._pos = Vector2D(-18.0, 4.0)
        world.set_mode(GameModeType.KickOff_Left)
        self.assertFalse(opponent_central_setplay_wall_active(world, profile=profile))

    def test_opponent_central_setplay_wall_target_keeps_legal_distance(self) -> None:
        ball = Vector2D(-18.0, 3.0)

        left_center_back = opponent_central_setplay_wall_target(3, ball, self.sp)
        right_center_back = opponent_central_setplay_wall_target(4, ball, self.sp)
        plug = opponent_central_setplay_wall_target(7, ball, self.sp)

        self.assertIsNotNone(left_center_back)
        self.assertIsNotNone(right_center_back)
        self.assertIsNotNone(plug)
        self.assertGreaterEqual(left_center_back.dist(ball), 10.0)
        self.assertGreaterEqual(right_center_back.dist(ball), 10.0)
        self.assertGreaterEqual(plug.dist(ball), 10.0)
        self.assertLess(left_center_back.y(), 0.0)
        self.assertGreater(right_center_back.y(), 0.0)

    def test_decide_opponent_central_setplay_wall_action_overrides_setplay_move(self) -> None:
        world = _BackpassWorld(
            SideID.LEFT,
            Vector2D(-18.0, 4.0),
            8.0,
            mode=GameModeType.FreeKick_Left,
            self_goalie=False,
            self_unum=7,
            self_pos=Vector2D(-30.0, 0.0),
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_43"}):
            action = decide_opponent_central_setplay_wall_action(world)

        self.assertIsNotNone(action)
        self.assertEqual(action.label, "opponent_central_setplay_wall")
        self.assertLess(action.decision_target.x(), world.ball().pos().x())
        self.assertAlmostEqual(action.decision_target.y(), 0.0)

    def test_goalie_flank_box_intercept_tracks_wide_box_race(self) -> None:
        profile = resolve_experiment_profile("candidate_26")
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 3.0, 14.0)
        world = _BackpassWorld(
            SideID.LEFT,
            ball,
            5.0,
            mode=GameModeType.PlayOn,
            self_goalie=True,
            self_pos=Vector2D(-45.0, 10.0),
            self_cycle=4,
            teammate_cycle=6,
            opponent_cycle=5,
        )

        self.assertTrue(goalie_flank_box_intercept_active(world, profile=profile))

        world.ball()._pos = Vector2D(self.sp.our_penalty_area_line_x() + 3.0, 0.0)
        self.assertFalse(goalie_flank_box_intercept_active(world, profile=profile))

        world.ball()._pos = Vector2D(self.sp.our_penalty_area_line_x() + 12.0, 14.0)
        self.assertFalse(goalie_flank_box_intercept_active(world, profile=profile))

    def test_goalie_flank_box_intercept_defers_to_catch_and_mode(self) -> None:
        profile = resolve_experiment_profile("candidate_26")
        ball = Vector2D(self.sp.our_penalty_area_line_x() - 2.0, 12.0)
        catchable_world = _BackpassWorld(
            SideID.LEFT,
            ball,
            self.sp.catchable_area() - 0.2,
            mode=GameModeType.PlayOn,
            self_goalie=True,
            self_cycle=3,
            teammate_cycle=6,
            opponent_cycle=4,
        )
        kickoff_world = _BackpassWorld(
            SideID.LEFT,
            ball,
            5.0,
            mode=GameModeType.KickOff_Left,
            self_goalie=True,
            self_cycle=3,
            teammate_cycle=6,
            opponent_cycle=4,
        )

        self.assertFalse(goalie_flank_box_intercept_active(catchable_world, profile=profile))
        self.assertFalse(goalie_flank_box_intercept_active(kickoff_world, profile=profile))

    def test_non_cyrus2d_goalie_flank_box_intercept_skips_cyrus2d_only(self) -> None:
        profile = resolve_experiment_profile("candidate_27")
        world = _BackpassWorld(
            SideID.LEFT,
            Vector2D(self.sp.our_penalty_area_line_x() + 3.0, 14.0),
            5.0,
            mode=GameModeType.PlayOn,
            self_goalie=True,
            self_cycle=4,
            teammate_cycle=6,
            opponent_cycle=5,
        )

        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertFalse(goalie_flank_box_intercept_active(world, profile=profile))
        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "cyrus_team"}):
            self.assertTrue(goalie_flank_box_intercept_active(world, profile=profile))
        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "foxsy_cyrus"}):
            self.assertTrue(goalie_flank_box_intercept_active(world, profile=profile))

    def test_non_cyrus2d_goalie_box_sweeper_tracks_central_box_race(self) -> None:
        profile = resolve_experiment_profile("candidate_31")
        ball = Vector2D(self.sp.our_penalty_area_line_x() - 4.0, 4.0)
        world = _BackpassWorld(
            SideID.LEFT,
            ball,
            4.5,
            mode=GameModeType.PlayOn,
            self_goalie=True,
            self_pos=Vector2D(-47.0, 1.5),
            self_cycle=4,
            teammate_cycle=6,
            opponent_cycle=5,
        )

        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "helios"}):
            self.assertTrue(goalie_box_sweeper_intercept_active(world, profile=profile))

        world.ball()._pos = Vector2D(self.sp.our_penalty_area_line_x() + 12.0, 4.0)
        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "helios"}):
            self.assertFalse(goalie_box_sweeper_intercept_active(world, profile=profile))

    def test_non_cyrus2d_goalie_box_sweeper_skips_cyrus2d_and_safe_catch(self) -> None:
        profile = resolve_experiment_profile("candidate_31")
        ball = Vector2D(self.sp.our_penalty_area_line_x() - 4.0, 4.0)
        world = _BackpassWorld(
            SideID.LEFT,
            ball,
            4.5,
            mode=GameModeType.PlayOn,
            self_goalie=True,
            self_cycle=4,
            teammate_cycle=6,
            opponent_cycle=5,
        )
        catchable_world = _BackpassWorld(
            SideID.LEFT,
            ball,
            self.sp.catchable_area() - 0.2,
            mode=GameModeType.PlayOn,
            self_goalie=True,
            self_cycle=3,
            teammate_cycle=6,
            opponent_cycle=4,
        )

        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertFalse(goalie_box_sweeper_intercept_active(world, profile=profile))
        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "foxsy_cyrus"}):
            self.assertFalse(goalie_box_sweeper_intercept_active(catchable_world, profile=profile))

    def test_non_cyrus2d_goalie_box_sweeper_requires_pressure_and_play_on(self) -> None:
        profile = resolve_experiment_profile("candidate_31")
        ball = Vector2D(self.sp.our_penalty_area_line_x() - 4.0, 4.0)
        quiet_world = _BackpassWorld(
            SideID.LEFT,
            ball,
            4.5,
            mode=GameModeType.PlayOn,
            self_goalie=True,
            self_cycle=4,
            teammate_cycle=8,
            opponent_cycle=11,
        )
        kickoff_world = _BackpassWorld(
            SideID.LEFT,
            ball,
            4.5,
            mode=GameModeType.KickOff_Left,
            self_goalie=True,
            self_cycle=4,
            teammate_cycle=6,
            opponent_cycle=5,
        )

        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "helios"}):
            self.assertFalse(goalie_box_sweeper_intercept_active(quiet_world, profile=profile))
            self.assertFalse(goalie_box_sweeper_intercept_active(kickoff_world, profile=profile))

    def test_kickoff_safety_punt_only_triggers_on_our_kickoff(self) -> None:
        profile = resolve_experiment_profile("candidate_28")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(0.0, 0.0),
            0.2,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=9,
            self_pos=Vector2D(0.0, 0.0),
        )

        self.assertTrue(restart_safety_punt_active(world, profile=profile))

        world.set_mode(GameModeType.KickOff_Left)
        self.assertFalse(restart_safety_punt_active(world, profile=profile))

        world.set_mode(GameModeType.PlayOn)
        self.assertFalse(restart_safety_punt_active(world, profile=profile))

    def test_kickoff_safety_punt_selects_deep_wide_target(self) -> None:
        profile = resolve_experiment_profile("candidate_28")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(0.0, 0.0),
            0.2,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=9,
            self_pos=Vector2D(0.0, 0.0),
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_28"}):
            action = decide_restart_safety_punt_action(world)
        target = choose_restart_safety_punt_target(world)

        self.assertIsNotNone(action)
        self.assertEqual(action.label, "restart_safety_punt")
        self.assertGreater(target.x(), self.sp.pitch_half_length() - 8.0)
        self.assertGreater(abs(target.y()), self.sp.pitch_half_width() - 8.0)
        self.assertTrue(restart_safety_punt_active(world, profile=profile))

    def test_kickoff_wide_outlet_only_triggers_on_our_kickoff(self) -> None:
        profile = resolve_experiment_profile("candidate_29")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(0.0, 0.0),
            0.2,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=10,
            self_pos=Vector2D(0.0, 0.0),
        )

        self.assertTrue(restart_wide_outlet_active(world, profile=profile))

        world.set_mode(GameModeType.KickOff_Left)
        self.assertFalse(restart_wide_outlet_active(world, profile=profile))

        world.set_mode(GameModeType.PlayOn)
        self.assertFalse(restart_wide_outlet_active(world, profile=profile))

    def test_kickoff_wide_outlet_prefers_teammate_width_without_punt(self) -> None:
        profile = resolve_experiment_profile("candidate_29")
        outlet = _Teammate(11, -6.0, 18.0)
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(0.0, 0.0),
            0.2,
            mode=GameModeType.KickOff_Right,
            teammates=[outlet, _Teammate(9, -6.0, -18.0)],
            self_goalie=False,
            self_unum=10,
            self_pos=Vector2D(0.0, 0.0),
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_29"}):
            action = decide_restart_wide_outlet_action(world)
        target = choose_restart_wide_outlet_target(world)

        self.assertIsNotNone(action)
        self.assertEqual(action.label, "restart_wide_outlet")
        self.assertLess(target.x(), 0.0)
        self.assertLess(target.x(), self.sp.pitch_half_length() - 20.0)
        self.assertAlmostEqual(abs(target.y()), abs(outlet.pos().y()))
        self.assertTrue(restart_wide_outlet_active(world, profile=profile))

    def test_weak_team_killer_is_opponent_gated(self) -> None:
        profile = resolve_experiment_profile("candidate_60")
        world = _NameWorld("")

        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertTrue(weak_team_killer_active(world, profile=profile))
        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "foxsy_cyrus"}):
            self.assertTrue(weak_team_killer_active(world, profile=profile))
        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertFalse(weak_team_killer_active(world, profile=profile))

    def test_weak_team_killer_allows_long_range_shots_only_against_weak_teams(self) -> None:
        profile = resolve_experiment_profile("candidate_60")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(8.0, 0.0),
            0.5,
            self_goalie=False,
            self_unum=10,
            self_pos=Vector2D(14.0, 0.0),
            self_cycle=2,
            teammate_cycle=4,
            opponent_cycle=5,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_60", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertTrue(in_shooting_range(world))

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_60", "ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertFalse(in_shooting_range(world))

    def test_weak_team_killer_direct_shoots_our_kickoff_and_corner(self) -> None:
        kickoff_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(0.0, 0.0),
            0.5,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=10,
            self_pos=Vector2D(0.0, 0.0),
        )
        corner_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(47.0, 32.0),
            0.5,
            mode=GameModeType.CornerKick_Right,
            self_goalie=False,
            self_unum=11,
            self_pos=Vector2D(47.0, 32.0),
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_60", "ROBOCUP_OPPONENT_KEY": "foxsy_cyrus"}):
            kickoff_action = decide_weak_team_restart_attack_action(kickoff_world)
            corner_action = decide_weak_team_restart_attack_action(corner_world)

        self.assertIsNotNone(kickoff_action)
        self.assertEqual(kickoff_action.label, "weak_team_kickoff_direct_shoot")
        self.assertIsNotNone(corner_action)
        self.assertEqual(corner_action.label, "weak_team_corner_direct_shoot")
        self.assertGreater(corner_action.decision_target.x(), 50.0)
        self.assertAlmostEqual(corner_action.decision_target.y(), 3.0)

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_60", "ROBOCUP_OPPONENT_KEY": "helios"}):
            self.assertIsNone(decide_weak_team_restart_attack_action(kickoff_world))

    def test_weak_team_killer_pushes_midfielders_forward_when_ball_is_safe(self) -> None:
        players = [
            _Teammate(6, -12.0, -8.0),
            _Teammate(7, -10.0, 0.0),
            _Teammate(8, -12.0, 8.0),
        ]
        world = _OffBallWorld(
            7,
            Vector2D(8.0, 4.0),
            players,
            self_cycle=10,
            teammate_cycle=5,
            opponent_cycle=8,
            exist_kickable_opponents=False,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_60", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            target = weak_team_attack_press_target(world)
            action = decide_off_ball_action(world)

        self.assertIsNotNone(target)
        self.assertGreater(target.x(), -5.0)
        self.assertEqual(action.label, "weak_team_attack_press")

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_60", "ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertIsNone(weak_team_attack_press_target(world))

    def test_weak_team_overdrive_forces_direct_attack_only_against_weak_teams(self) -> None:
        profile = resolve_experiment_profile("candidate_61")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(8.0, 6.0),
            0.5,
            self_goalie=False,
            self_unum=10,
            self_pos=Vector2D(8.0, 6.0),
            self_cycle=2,
            teammate_cycle=5,
            opponent_cycle=4,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_61", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            action = decide_weak_team_overdrive_on_ball_action(world, profile=profile)

        self.assertIsNotNone(action)
        self.assertEqual(action.label, "weak_team_overdrive_direct_attack")
        self.assertGreater(action.decision_target.x(), 50.0)

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_61", "ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertFalse(weak_team_overdrive_active(world, profile=profile))
            self.assertIsNone(decide_weak_team_overdrive_on_ball_action(world, profile=profile))

    def test_weak_team_overdrive_pushes_frontline_into_attack_slots(self) -> None:
        players = [
            _Teammate(9, -6.0, -14.0),
            _Teammate(10, -2.0, 0.0),
            _Teammate(11, -6.0, 14.0),
        ]
        world = _OffBallWorld(
            10,
            Vector2D(-4.0, 3.0),
            players,
            self_cycle=3,
            teammate_cycle=5,
            opponent_cycle=8,
            exist_kickable_opponents=False,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_61", "ROBOCUP_OPPONENT_KEY": "foxsy_cyrus"}):
            target = weak_team_attack_press_target(world)
            action = decide_off_ball_action(world)

        self.assertIsNotNone(target)
        self.assertGreater(target.x(), 15.0)
        self.assertEqual(action.label, "weak_team_attack_press")

    def test_weak_team_press_only_pushes_frontline_without_forcing_on_ball_shots(self) -> None:
        profile = resolve_experiment_profile("candidate_62")
        players = [
            _Teammate(9, -6.0, -14.0),
            _Teammate(10, -2.0, 0.0),
            _Teammate(11, -6.0, 14.0),
        ]
        off_ball_world = _OffBallWorld(
            10,
            Vector2D(-4.0, 3.0),
            players,
            self_cycle=3,
            teammate_cycle=5,
            opponent_cycle=8,
            exist_kickable_opponents=False,
        )
        on_ball_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(8.0, 6.0),
            0.5,
            self_goalie=False,
            self_unum=10,
            self_pos=Vector2D(8.0, 6.0),
            self_cycle=2,
            teammate_cycle=5,
            opponent_cycle=4,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_62", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            target = weak_team_attack_press_target(off_ball_world, profile=profile)
            off_ball_action = decide_off_ball_action(off_ball_world)
            on_ball_action = decide_experiment_on_ball_action(on_ball_world)
            self.assertTrue(weak_team_press_only_active(off_ball_world, profile=profile))
            self.assertFalse(weak_team_killer_active(off_ball_world, profile=profile))
            self.assertFalse(weak_team_overdrive_active(off_ball_world, profile=profile))
        self.assertIsNotNone(target)
        self.assertGreater(target.x(), 10.0)
        self.assertEqual(off_ball_action.label, "weak_team_attack_press")
        self.assertIsNone(on_ball_action)

    def test_weak_team_press_intercept_lets_frontline_chase_reachable_ball(self) -> None:
        profile = resolve_experiment_profile("candidate_63")
        players = [
            _Teammate(9, 14.0, -8.0),
            _Teammate(10, 12.0, 1.0),
            _Teammate(11, 14.0, 8.0),
        ]
        world = _OffBallWorld(
            10,
            Vector2D(18.0, 2.0),
            players,
            self_cycle=3,
            teammate_cycle=4,
            opponent_cycle=5,
            exist_kickable_opponents=False,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_63", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            action = weak_team_press_intercept_action(world, profile=profile)
            decided = decide_off_ball_action(world)
            self.assertTrue(weak_team_press_intercept_active(world, profile=profile))

        self.assertIsNotNone(action)
        self.assertEqual(action.label, "weak_team_press_intercept")
        self.assertEqual(decided.label, "weak_team_press_intercept")

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_63", "ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertFalse(weak_team_press_intercept_active(world, profile=profile))
            self.assertIsNone(weak_team_press_intercept_action(world, profile=profile))

    def test_weak_team_press_intercept_defers_when_frontliner_is_not_near_fastest(self) -> None:
        profile = resolve_experiment_profile("candidate_63")
        players = [
            _Teammate(9, -6.0, -14.0),
            _Teammate(10, -2.0, 0.0),
            _Teammate(11, -6.0, 14.0),
        ]
        world = _OffBallWorld(
            10,
            Vector2D(10.0, 3.0),
            players,
            self_cycle=9,
            teammate_cycle=4,
            opponent_cycle=7,
            exist_kickable_opponents=False,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_63", "ROBOCUP_OPPONENT_KEY": "foxsy_cyrus"}):
            self.assertIsNone(weak_team_press_intercept_action(world, profile=profile))
            decided = decide_off_ball_action(world)

        self.assertEqual(decided.label, "weak_team_attack_press")

    def test_weak_team_channel_entry_sends_controlled_midfield_touch_into_front_third(self) -> None:
        profile = resolve_experiment_profile("candidate_64")
        teammates = [
            _Teammate(9, 13.0, -14.0),
            _Teammate(10, 16.0, 3.0),
            _Teammate(11, 12.0, 10.0),
        ]
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(10.0, 2.0),
            0.5,
            self_goalie=False,
            self_unum=8,
            self_pos=Vector2D(10.0, 2.0),
            teammates=teammates,
            self_cycle=2,
            teammate_cycle=3,
            opponent_cycle=5,
            exist_kickable_opponents=False,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_64", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertTrue(weak_team_channel_entry_active(world, profile=profile))
            receiver = choose_weak_team_channel_receiver(world)
            target = weak_team_channel_entry_target(world)
            action = decide_weak_team_channel_entry_action(world, profile=profile)

        self.assertIsNotNone(receiver)
        self.assertEqual(receiver.unum(), 10)
        self.assertGreaterEqual(target.x(), 28.0)
        self.assertLessEqual(abs(target.y()), 12.0)
        self.assertIsNotNone(action)
        self.assertEqual(action.label, "weak_team_channel_entry")
        self.assertGreaterEqual(action.decision_target.x(), 28.0)

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_64", "ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertFalse(weak_team_channel_entry_active(world, profile=profile))
            self.assertIsNone(decide_weak_team_channel_entry_action(world, profile=profile))

    def test_weak_team_channel_entry_skips_deep_defensive_touches(self) -> None:
        profile = resolve_experiment_profile("candidate_64")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-12.0, 2.0),
            0.5,
            self_goalie=False,
            self_unum=8,
            self_pos=Vector2D(-12.0, 2.0),
            teammates=[_Teammate(10, 4.0, 0.0)],
            self_cycle=2,
            teammate_cycle=3,
            opponent_cycle=5,
            exist_kickable_opponents=False,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_64", "ROBOCUP_OPPONENT_KEY": "foxsy_cyrus"}):
            self.assertIsNone(decide_weak_team_channel_entry_action(world, profile=profile))

    def test_weak_team_restart_channel_replaces_direct_kickoff_shot(self) -> None:
        profile = resolve_experiment_profile("candidate_65")
        kickoff_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(0.0, 0.0),
            0.5,
            mode=GameModeType.KickOff_Right,
            teammates=[
                _Teammate(10, 8.0, 2.0),
                _Teammate(11, 6.0, 12.0),
            ],
            self_goalie=False,
            self_unum=10,
            self_pos=Vector2D(0.0, 0.0),
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_65", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertTrue(weak_team_restart_channel_entry_active(kickoff_world, profile=profile))
            target = weak_team_restart_channel_entry_target(kickoff_world)
            action = decide_weak_team_restart_attack_action(kickoff_world)

        self.assertGreaterEqual(target.x(), 14.0)
        self.assertLess(target.x(), 30.0)
        self.assertIsNotNone(action)
        self.assertEqual(action.label, "weak_team_kickoff_channel_entry")
        self.assertGreaterEqual(action.decision_target.x(), 14.0)
        self.assertLess(action.decision_target.x(), 30.0)

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_65", "ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertFalse(weak_team_restart_channel_entry_active(kickoff_world, profile=profile))
            self.assertIsNone(decide_weak_team_restart_attack_action(kickoff_world))

    def test_weak_team_frontline_slots_pushes_forward_receivers_when_not_chasing(self) -> None:
        profile = resolve_experiment_profile("candidate_66")
        players = [
            _Teammate(9, 6.0, -12.0),
            _Teammate(10, 8.0, 1.0),
            _Teammate(11, 6.0, 12.0),
        ]
        world = _OffBallWorld(
            10,
            Vector2D(6.0, 2.0),
            players,
            self_cycle=8,
            teammate_cycle=4,
            opponent_cycle=8,
            exist_kickable_opponents=False,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_66", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertTrue(weak_team_frontline_slots_active(world, profile=profile))
            slot = weak_team_frontline_slot_target(world, profile=profile)
            press_target = weak_team_attack_press_target(world, profile=profile)
            action = decide_off_ball_action(world)

        self.assertIsNotNone(slot)
        self.assertGreaterEqual(slot.x(), 32.0)
        self.assertAlmostEqual(slot.y(), 0.0)
        self.assertIsNotNone(press_target)
        self.assertAlmostEqual(press_target.x(), slot.x())
        self.assertEqual(action.label, "weak_team_attack_press")
        self.assertAlmostEqual(action.decision_target.x(), slot.x())

    def test_weak_team_frontline_slots_make_kickoff_target_high(self) -> None:
        profile = resolve_experiment_profile("candidate_66")
        kickoff_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(0.0, 0.0),
            0.5,
            mode=GameModeType.KickOff_Right,
            teammates=[_Teammate(10, 8.0, 2.0)],
            self_goalie=False,
            self_unum=10,
            self_pos=Vector2D(0.0, 0.0),
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_66", "ROBOCUP_OPPONENT_KEY": "foxsy_cyrus"}):
            target = weak_team_restart_channel_entry_target(kickoff_world)
            action = decide_weak_team_restart_attack_action(kickoff_world)

        self.assertGreaterEqual(target.x(), 32.0)
        self.assertIsNotNone(action)
        self.assertEqual(action.label, "weak_team_kickoff_channel_entry")
        self.assertGreaterEqual(action.decision_target.x(), 32.0)

    def test_weak_team_front_third_finish_shoots_from_rare_high_touch(self) -> None:
        profile = resolve_experiment_profile("candidate_67")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(26.0, 6.0),
            0.5,
            self_goalie=False,
            self_unum=10,
            self_pos=Vector2D(26.0, 6.0),
            self_cycle=2,
            teammate_cycle=4,
            opponent_cycle=6,
            exist_kickable_opponents=False,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_67", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertTrue(weak_team_front_third_finish_active(world, profile=profile))
            target = weak_team_front_third_finish_target(world)
            action = decide_weak_team_front_third_finish_action(world, profile=profile)
            decided = decide_experiment_on_ball_action(world)

        self.assertGreater(target.x(), 50.0)
        self.assertLess(abs(target.y()), 3.1)
        self.assertIsNotNone(action)
        self.assertEqual(action.label, "weak_team_front_third_finish")
        self.assertIsNotNone(decided)
        self.assertEqual(decided.label, "weak_team_front_third_finish")

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_67", "ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertFalse(weak_team_front_third_finish_active(world, profile=profile))
            self.assertIsNone(decide_weak_team_front_third_finish_action(world, profile=profile))

    def test_weak_team_front_third_finish_ignores_midfield_touch(self) -> None:
        profile = resolve_experiment_profile("candidate_67")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(18.0, 4.0),
            0.5,
            self_goalie=False,
            self_unum=10,
            self_pos=Vector2D(18.0, 4.0),
            self_cycle=2,
            teammate_cycle=4,
            opponent_cycle=6,
            exist_kickable_opponents=False,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_67", "ROBOCUP_OPPONENT_KEY": "foxsy_cyrus"}):
            self.assertIsNone(decide_weak_team_front_third_finish_action(world, profile=profile))

    def test_weak_team_frontline_post_finish_targets_same_side_post(self) -> None:
        profile = resolve_experiment_profile("candidate_68")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(26.5, 10.0),
            0.5,
            self_goalie=False,
            self_unum=11,
            self_pos=Vector2D(26.5, 10.0),
            self_cycle=2,
            teammate_cycle=4,
            opponent_cycle=6,
            exist_kickable_opponents=False,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_68", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertTrue(weak_team_frontline_post_finish_active(world, profile=profile))
            target = weak_team_frontline_post_finish_target(world)
            action = decide_weak_team_front_third_finish_action(world, profile=profile)
            decided = decide_experiment_on_ball_action(world)

        self.assertGreater(target.x(), 50.0)
        self.assertGreater(target.y(), 3.0)
        self.assertLessEqual(target.y(), 6.6)
        self.assertIsNotNone(action)
        self.assertEqual(action.label, "weak_team_frontline_post_finish")
        self.assertIsNotNone(decided)
        self.assertEqual(decided.label, "weak_team_frontline_post_finish")

    def test_weak_team_frontline_post_finish_rejects_midfielders_and_midfield_touches(self) -> None:
        profile = resolve_experiment_profile("candidate_68")
        midfielder_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(27.0, 2.0),
            0.5,
            self_goalie=False,
            self_unum=7,
            self_pos=Vector2D(27.0, 2.0),
            exist_kickable_opponents=False,
        )
        midfield_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(24.5, 10.0),
            0.5,
            self_goalie=False,
            self_unum=11,
            self_pos=Vector2D(24.5, 10.0),
            exist_kickable_opponents=False,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_68", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertIsNone(decide_weak_team_front_third_finish_action(midfielder_world, profile=profile))
            self.assertIsNone(decide_weak_team_front_third_finish_action(midfield_world, profile=profile))

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_68", "ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertFalse(weak_team_frontline_post_finish_active(midfielder_world, profile=profile))

    def test_weak_team_natural_frontline_finish_does_not_enable_pressure_slots(self) -> None:
        profile = resolve_experiment_profile("candidate_69")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(31.0, 4.0),
            0.5,
            self_goalie=False,
            self_unum=11,
            self_pos=Vector2D(31.0, 4.0),
            exist_kickable_opponents=False,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_69", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertTrue(weak_team_frontline_post_finish_active(world, profile=profile))
            self.assertFalse(weak_team_killer_active(world, profile=profile))
            self.assertFalse(weak_team_press_only_active(world, profile=profile))
            self.assertFalse(weak_team_frontline_slots_active(world, profile=profile))
            action = decide_experiment_on_ball_action(world)

        self.assertIsNotNone(action)
        self.assertEqual(action.label, "weak_team_frontline_post_finish")

    def test_weak_team_natural_channel_feed_sends_ball_ahead_of_natural_frontline(self) -> None:
        profile = resolve_experiment_profile("candidate_70")
        receiver = _Teammate(11, 22.0, 6.0)
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(10.0, 3.0),
            0.5,
            self_goalie=False,
            self_unum=8,
            self_pos=Vector2D(10.0, 3.0),
            teammates=[receiver],
            opponents=[_Opponent(4, 18.0, -8.0), _Opponent(5, 26.0, -10.0)],
            exist_kickable_opponents=False,
            opponent_cycle=7,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_70", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertTrue(weak_team_natural_channel_feed_active(world, profile=profile))
            chosen = choose_weak_team_natural_channel_receiver(world)
            target = weak_team_natural_channel_feed_target(world, receiver)
            action = decide_weak_team_natural_channel_feed_action(world, profile=profile)
            decided = decide_experiment_on_ball_action(world)

        self.assertIs(chosen, receiver)
        self.assertGreater(target.x(), world.ball().pos().x())
        self.assertGreater(target.x(), receiver.pos().x())
        self.assertLess(abs(target.y()), abs(receiver.pos().y()))
        self.assertIsNotNone(action)
        self.assertEqual(action.label, "weak_team_natural_channel_feed")
        self.assertEqual(decided.label, "weak_team_natural_channel_feed")

    def test_weak_team_natural_channel_feed_is_weak_team_and_shape_gated(self) -> None:
        profile = resolve_experiment_profile("candidate_70")
        receiver = _Teammate(11, 22.0, 6.0)
        valid_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(10.0, 3.0),
            0.5,
            self_goalie=False,
            self_unum=8,
            self_pos=Vector2D(10.0, 3.0),
            teammates=[receiver],
            opponents=[_Opponent(4, 18.0, -8.0)],
            exist_kickable_opponents=False,
        )
        deep_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(-4.0, 3.0),
            0.5,
            self_goalie=False,
            self_unum=8,
            self_pos=Vector2D(-4.0, 3.0),
            teammates=[receiver],
            opponents=[_Opponent(4, 18.0, -8.0)],
            exist_kickable_opponents=False,
        )
        no_receiver_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(10.0, 3.0),
            0.5,
            self_goalie=False,
            self_unum=8,
            self_pos=Vector2D(10.0, 3.0),
            teammates=[_Teammate(11, 15.0, 6.0)],
            opponents=[_Opponent(4, 18.0, -8.0)],
            exist_kickable_opponents=False,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_70", "ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertFalse(weak_team_natural_channel_feed_active(valid_world, profile=profile))
            self.assertIsNone(decide_weak_team_natural_channel_feed_action(valid_world, profile=profile))

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_70", "ROBOCUP_OPPONENT_KEY": "foxsy_cyrus"}):
            self.assertIsNone(decide_weak_team_natural_channel_feed_action(deep_world, profile=profile))
            self.assertIsNone(decide_weak_team_natural_channel_feed_action(no_receiver_world, profile=profile))

    def test_weak_team_deep_cutback_uses_natural_front_third_touch(self) -> None:
        profile = resolve_experiment_profile("candidate_71")
        receiver = _Teammate(10, 30.0, 4.0)
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(33.0, 16.0),
            0.5,
            self_goalie=False,
            self_unum=8,
            self_pos=Vector2D(32.8, 15.5),
            teammates=[_Teammate(9, 29.0, -16.0), receiver, _Teammate(11, 38.0, 8.0)],
            opponents=[_Opponent(3, 34.0, -6.0), _Opponent(4, 36.0, 12.0)],
            exist_kickable_opponents=False,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_71", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertTrue(weak_team_deep_cutback_active(world, profile=profile))
            chosen = choose_weak_team_deep_cutback_receiver(world)
            target = weak_team_deep_cutback_target(world, receiver)
            action = decide_weak_team_deep_cutback_action(world, profile=profile)
            decided = decide_experiment_on_ball_action(world)

        self.assertIs(chosen, receiver)
        self.assertLess(abs(target.y()), abs(world.ball().pos().y()))
        self.assertGreaterEqual(target.x(), 27.0)
        self.assertIsNotNone(action)
        self.assertEqual(action.label, "weak_team_deep_cutback")
        self.assertEqual(decided.label, "weak_team_deep_cutback")

    def test_weak_team_deep_cutback_is_weak_team_and_front_third_gated(self) -> None:
        profile = resolve_experiment_profile("candidate_71")
        receiver = _Teammate(10, 30.0, 4.0)
        valid_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(33.0, 16.0),
            0.5,
            self_goalie=False,
            self_unum=8,
            self_pos=Vector2D(32.8, 15.5),
            teammates=[receiver],
            opponents=[_Opponent(3, 34.0, -6.0)],
            exist_kickable_opponents=False,
        )
        midfield_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(24.0, 10.0),
            0.5,
            self_goalie=False,
            self_unum=8,
            self_pos=Vector2D(24.0, 10.0),
            teammates=[receiver],
            opponents=[_Opponent(3, 34.0, -6.0)],
            exist_kickable_opponents=False,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_71", "ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertFalse(weak_team_deep_cutback_active(valid_world, profile=profile))
            self.assertIsNone(decide_weak_team_deep_cutback_action(valid_world, profile=profile))

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_71", "ROBOCUP_OPPONENT_KEY": "foxsy_cyrus"}):
            self.assertIsNone(decide_weak_team_deep_cutback_action(midfield_world, profile=profile))

    def test_weak_team_restart_grounder_uses_only_our_weak_team_restarts(self) -> None:
        profile = resolve_experiment_profile("candidate_72")
        receiver = _Teammate(10, 10.0, 4.0)
        kickoff_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(0.0, 0.0),
            0.5,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=10,
            self_pos=Vector2D(0.0, 0.0),
            teammates=[receiver, _Teammate(11, -6.0, 18.0)],
            opponents=[],
            exist_kickable_opponents=False,
        )
        corner_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(52.0, 28.0),
            0.5,
            mode=GameModeType.CornerKick_Right,
            self_goalie=False,
            self_unum=11,
            self_pos=Vector2D(52.0, 28.0),
            teammates=[receiver],
            opponents=[],
            exist_kickable_opponents=False,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_72", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertTrue(weak_team_restart_grounder_active(kickoff_world, profile=profile))
            chosen = choose_weak_team_restart_grounder_receiver(kickoff_world)
            target = weak_team_restart_grounder_target(kickoff_world)
            kickoff_action = decide_weak_team_restart_grounder_action(kickoff_world, profile=profile)
            corner_action = decide_weak_team_restart_grounder_action(corner_world, profile=profile)

        self.assertIs(chosen, receiver)
        self.assertGreater(target.x(), receiver.pos().x())
        self.assertLess(abs(target.y()), abs(receiver.pos().y()))
        self.assertIsNotNone(kickoff_action)
        self.assertEqual(kickoff_action.label, "weak_team_kickoff_grounder")
        self.assertIsNotNone(corner_action)
        self.assertEqual(corner_action.label, "weak_team_corner_grounder")
        self.assertFalse(weak_team_killer_active(kickoff_world, profile=profile))

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_72", "ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertFalse(weak_team_restart_grounder_active(kickoff_world, profile=profile))
            self.assertIsNone(decide_weak_team_restart_grounder_action(kickoff_world, profile=profile))

        kickoff_world.set_mode(GameModeType.KickOff_Left)
        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_72", "ROBOCUP_OPPONENT_KEY": "foxsy_cyrus"}):
            self.assertFalse(weak_team_restart_grounder_active(kickoff_world, profile=profile))
            self.assertIsNone(decide_weak_team_restart_grounder_action(kickoff_world, profile=profile))

    def test_weak_team_restart_second_finish_shoots_only_after_our_kickoff_window(self) -> None:
        profile = resolve_experiment_profile("candidate_73")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(24.0, 12.0),
            0.5,
            self_goalie=False,
            self_unum=10,
            self_pos=Vector2D(24.0, 12.0),
            opponents=[_Opponent(4, 30.0, -8.0)],
            exist_kickable_opponents=False,
        )

        decision_module._RECENT_OUR_KICKOFF_CYCLE = 100
        world.set_cycle(180)
        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_73", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertTrue(weak_team_restart_second_finish_active(world, profile=profile))
            target = weak_team_restart_second_finish_target(world)
            action = decide_weak_team_restart_second_finish_action(world, profile=profile)
            decided = decide_experiment_on_ball_action(world)

        self.assertGreater(target.x(), world.ball().pos().x())
        self.assertLess(target.y(), 0.0)
        self.assertIsNotNone(action)
        self.assertEqual(action.label, "weak_team_restart_second_finish")
        self.assertEqual(decided.label, "weak_team_restart_second_finish")

        world.set_cycle(300)
        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_73", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertFalse(weak_team_restart_second_finish_active(world, profile=profile))
            self.assertIsNone(decide_weak_team_restart_second_finish_action(world, profile=profile))

        decision_module._RECENT_OUR_KICKOFF_CYCLE = 100
        world.set_cycle(180)
        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_73", "ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertFalse(weak_team_restart_second_finish_active(world, profile=profile))
            self.assertIsNone(decide_weak_team_restart_second_finish_action(world, profile=profile))

    def test_weak_team_natural_high_frontline_finish_preserves_only_late_frontline_chain(self) -> None:
        profile = resolve_experiment_profile("candidate_74")
        world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(38.0, -14.0),
            0.5,
            self_goalie=False,
            self_unum=9,
            self_pos=Vector2D(38.5, -18.0),
            opponents=[_Opponent(3, 35.0, -9.0), _Opponent(4, 41.0, 7.0)],
            exist_kickable_opponents=False,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_74", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertTrue(weak_team_natural_high_frontline_finish_active(world, profile=profile))
            target = weak_team_natural_high_frontline_finish_target(world)
            action = decide_weak_team_natural_high_frontline_finish_action(world, profile=profile)
            decided = decide_experiment_on_ball_action(world)

        self.assertGreater(target.x(), world.ball().pos().x())
        self.assertGreater(target.y(), 0.0)
        self.assertIsNotNone(action)
        self.assertEqual(action.label, "weak_team_natural_high_frontline_finish")
        self.assertEqual(decided.label, "weak_team_natural_high_frontline_finish")

    def test_weak_team_natural_high_frontline_finish_is_tightly_gated(self) -> None:
        profile = resolve_experiment_profile("candidate_74")
        valid_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(38.0, -14.0),
            0.5,
            self_goalie=False,
            self_unum=9,
            self_pos=Vector2D(38.5, -18.0),
            opponents=[_Opponent(3, 35.0, -9.0)],
            exist_kickable_opponents=False,
        )
        midfield_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(28.0, -14.0),
            0.5,
            self_goalie=False,
            self_unum=9,
            self_pos=Vector2D(28.5, -18.0),
            opponents=[_Opponent(3, 35.0, -9.0)],
            exist_kickable_opponents=False,
        )
        central_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(38.0, -3.0),
            0.5,
            self_goalie=False,
            self_unum=9,
            self_pos=Vector2D(38.5, -4.0),
            opponents=[_Opponent(3, 35.0, -9.0)],
            exist_kickable_opponents=False,
        )
        midfielder_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(38.0, -14.0),
            0.5,
            self_goalie=False,
            self_unum=10,
            self_pos=Vector2D(38.5, -18.0),
            opponents=[_Opponent(3, 35.0, -9.0)],
            exist_kickable_opponents=False,
        )
        pressured_world = _BackpassWorld(
            SideID.RIGHT,
            Vector2D(38.0, -14.0),
            0.5,
            self_goalie=False,
            self_unum=9,
            self_pos=Vector2D(38.5, -18.0),
            opponents=[_Opponent(3, 38.2, -14.2)],
            exist_kickable_opponents=True,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_74", "ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertFalse(weak_team_natural_high_frontline_finish_active(valid_world, profile=profile))
            self.assertIsNone(decide_weak_team_natural_high_frontline_finish_action(valid_world, profile=profile))

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_74", "ROBOCUP_OPPONENT_KEY": "starter2d"}):
            self.assertIsNone(decide_weak_team_natural_high_frontline_finish_action(midfield_world, profile=profile))
            self.assertIsNone(decide_weak_team_natural_high_frontline_finish_action(central_world, profile=profile))
            self.assertIsNone(decide_weak_team_natural_high_frontline_finish_action(midfielder_world, profile=profile))
            self.assertIsNone(decide_weak_team_natural_high_frontline_finish_action(pressured_world, profile=profile))

    def test_box_entry_owner_lock_selects_single_nearest_defender(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() - 3.0, 3.0)
        players = [
            _Teammate(3, ball.x() + 0.8, ball.y() + 0.3),
            _Teammate(5, ball.x() + 4.0, ball.y() + 4.0),
            _Teammate(7, ball.x() + 1.1, ball.y() + 0.2),
        ]
        world = _OffBallWorld(7, ball, players)
        profile = resolve_experiment_profile("candidate_14")

        self.assertEqual(select_box_entry_owner_unum(world), 3)
        self.assertTrue(should_hold_box_entry_owner_lock(world, profile=profile, owner_unum=3))

        owner_world = _OffBallWorld(3, ball, players)
        self.assertFalse(should_hold_box_entry_owner_lock(owner_world, profile=profile, owner_unum=3))

    def test_box_entry_owner_lock_stays_off_outside_box_front(self) -> None:
        ball = Vector2D(-20.0, 0.0)
        world = _OffBallWorld(3, ball, [_Teammate(3, -21.0, 0.0)])

        self.assertIsNone(select_box_entry_owner_unum(world))

    def test_goalmouth_lane_block_assigns_non_owner_to_shot_lane(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() - 4.0, 8.0)
        players = [
            _Teammate(3, ball.x() + 0.6, ball.y()),
            _Teammate(4, -45.2, 7.5),
            _Teammate(6, -31.0, -10.0),
        ]
        world = _OffBallWorld(4, ball, players)

        target = find_goalmouth_lane_block_target(world, profile=resolve_experiment_profile("candidate_15"), owner_unum=3)

        self.assertIsNotNone(target)
        self.assertLess(target.x(), ball.x())
        self.assertLess(abs(target.y()), abs(ball.y()) + 1.0)

    def test_goalmouth_lane_block_does_not_pull_owner(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() - 4.0, 8.0)
        players = [
            _Teammate(3, ball.x() + 0.6, ball.y()),
            _Teammate(4, -45.2, 7.5),
        ]
        world = _OffBallWorld(3, ball, players)

        target = find_goalmouth_lane_block_target(world, profile=resolve_experiment_profile("candidate_15"), owner_unum=3)

        self.assertIsNone(target)

    def test_kickoff_terminal_guard_reuses_lane_block_after_our_kickoff(self) -> None:
        profile = resolve_experiment_profile("candidate_38")
        ball = Vector2D(self.sp.our_penalty_area_line_x() - 4.0, 6.0)
        players = [
            _Teammate(3, ball.x() + 0.6, ball.y()),
            _Teammate(4, -45.2, 6.5),
            _Teammate(6, -31.0, -10.0),
        ]
        world = _OffBallWorld(4, ball, players, mode=GameModeType.PlayOn)
        world.set_cycle(10060)
        decision_module._RECENT_OUR_KICKOFF_CYCLE = 10000

        target = find_goalmouth_lane_block_target(world, profile=profile, owner_unum=3)

        self.assertTrue(kickoff_terminal_guard_active(world, profile=profile))
        self.assertIsNotNone(target)
        self.assertLess(target.x(), ball.x())

    def test_narrow_kickoff_center_entry_clear_only_after_our_kickoff_center_entry(self) -> None:
        profile = resolve_experiment_profile("candidate_48")
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 4.0)
        me = Vector2D(ball.x() - 0.5, ball.y())
        world = _BackpassWorld(
            SideID.RIGHT,
            ball,
            3.0,
            mode=GameModeType.KickOff_Right,
            self_goalie=False,
            self_unum=3,
            self_pos=me,
            exist_kickable_opponents=True,
            opponent_cycle=2,
        )
        world.set_cycle(19000)

        update_recent_our_kickoff(world)
        self.assertFalse(narrow_kickoff_center_entry_clear_active(world, profile=profile))

        world.set_mode(GameModeType.PlayOn)
        world.set_cycle(19060)

        self.assertTrue(narrow_kickoff_center_entry_clear_active(world, profile=profile))
        self.assertTrue(should_use_one_step_clear(ball, me, False, self.sp, profile, world))

        wide_ball = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 12.0)
        world.ball()._pos = wide_ball
        self.assertFalse(narrow_kickoff_center_entry_clear_active(world, profile=profile))
        self.assertFalse(should_use_one_step_clear(wide_ball, me, False, self.sp, profile, world))

    def test_narrow_kickoff_center_entry_clear_reuses_lane_block_without_owner(self) -> None:
        profile = resolve_experiment_profile("candidate_48")
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 4.0, 4.0)
        players = [
            _Teammate(3, ball.x() + 0.6, ball.y()),
            _Teammate(4, -44.5, 4.5),
            _Teammate(7, -35.0, 0.0),
        ]
        world = _OffBallWorld(4, ball, players, mode=GameModeType.PlayOn)
        world.set_cycle(20070)
        decision_module._RECENT_OUR_KICKOFF_CYCLE = 20000

        target = find_goalmouth_lane_block_target(world, profile=profile, owner_unum=3)

        self.assertTrue(narrow_kickoff_center_entry_clear_active(world, profile=profile))
        self.assertIsNotNone(target)
        self.assertLess(target.x(), ball.x())

    def test_flank_cutback_guard_assigns_non_owner_to_cutback_lane(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 22.0)
        players = [
            _Teammate(2, ball.x() + 0.5, ball.y() - 0.5),
            _Teammate(4, self.sp.our_penalty_area_line_x() - 2.0, 10.0),
            _Teammate(6, -24.0, 2.0),
        ]
        world = _OffBallWorld(4, ball, players, self_cycle=2, teammate_cycle=4, opponent_cycle=3)
        profile = resolve_experiment_profile("candidate_30")

        target = find_flank_cutback_guard_target(world, profile=profile, owner_unum=2)

        self.assertTrue(flank_cutback_guard_active(world, profile=profile))
        self.assertEqual(select_flank_cutback_guard_unum(world, owner_unum=2), 4)
        self.assertIsNotNone(target)
        self.assertLess(target.x(), ball.x())
        self.assertLess(abs(target.y()), abs(ball.y()))

    def test_flank_cutback_guard_does_not_pull_ball_owner_or_central_mode(self) -> None:
        profile = resolve_experiment_profile("candidate_30")
        flank_ball = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, -22.0)
        players = [
            _Teammate(2, flank_ball.x() + 0.5, flank_ball.y()),
            _Teammate(4, self.sp.our_penalty_area_line_x() - 2.0, -10.0),
        ]
        owner_world = _OffBallWorld(2, flank_ball, players)
        central_world = _OffBallWorld(4, Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 4.0), players)
        kickoff_world = _OffBallWorld(4, flank_ball, players, mode=GameModeType.KickOff_Right)

        self.assertIsNone(find_flank_cutback_guard_target(owner_world, profile=profile, owner_unum=2))
        self.assertFalse(flank_cutback_guard_active(central_world, profile=profile))
        self.assertFalse(flank_cutback_guard_active(kickoff_world, profile=profile))

    def test_flank_cutback_guard_uses_owner_fallback_for_very_wide_ball(self) -> None:
        profile = resolve_experiment_profile("candidate_30")
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 4.0, self.sp.penalty_area_half_width() + 8.0)
        players = [
            _Teammate(2, ball.x() + 0.3, ball.y() - 0.2),
            _Teammate(4, self.sp.our_penalty_area_line_x() - 2.0, 11.0),
        ]
        owner_world = _OffBallWorld(2, ball, players)
        guard_world = _OffBallWorld(4, ball, players)

        self.assertIsNone(select_box_entry_owner_unum(owner_world))
        self.assertEqual(select_flank_ball_owner_unum(owner_world), 2)
        self.assertIsNone(find_flank_cutback_guard_target(owner_world, profile=profile))
        self.assertIsNotNone(find_flank_cutback_guard_target(guard_world, profile=profile))

    def test_flank_cutback_guard_stays_off_when_teammate_controls_ball(self) -> None:
        profile = resolve_experiment_profile("candidate_30")
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 22.0)
        world = _OffBallWorld(
            4,
            ball,
            [_Teammate(2, ball.x() + 0.5, ball.y()), _Teammate(4, self.sp.our_penalty_area_line_x() - 2.0, 10.0)],
            exist_kickable_teammates=True,
        )

        self.assertFalse(flank_cutback_guard_active(world, profile=profile))

    def test_decide_off_ball_action_uses_cutback_guard_before_intercept(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 5.0, 22.0)
        players = [
            _Teammate(2, ball.x() + 0.5, ball.y()),
            _Teammate(4, self.sp.our_penalty_area_line_x() - 2.0, 10.0),
        ]
        world = _OffBallWorld(4, ball, players, self_cycle=2, teammate_cycle=5, opponent_cycle=2)

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_30"}):
            action = decide_off_ball_action(world)

        self.assertEqual(action.label, "flank_cutback_guard")
        self.assertIsNotNone(action.block_target)

    def test_flank_restart_goalmouth_lock_tracks_post_kickoff_wide_terminal(self) -> None:
        profile = resolve_experiment_profile("candidate_44")
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 3.0, 17.0)
        players = [
            _Teammate(5, ball.x() + 0.4, ball.y() - 0.2),
            _Teammate(4, self.sp.our_penalty_area_line_x() - 5.0, 7.5),
            _Teammate(7, self.sp.our_penalty_area_line_x() - 3.0, 3.0),
        ]
        world = _OffBallWorld(4, ball, players, self_cycle=7, teammate_cycle=5, opponent_cycle=3)
        decision_module._RECENT_OUR_KICKOFF_CYCLE = 15000
        world.set_cycle(15140)

        target = flank_restart_goalmouth_lock_target(world, profile=profile, owner_unum=5)

        self.assertTrue(flank_restart_goalmouth_lock_active(world, profile=profile))
        self.assertEqual(select_flank_restart_goalmouth_lock_assignment(world, owner_unum=5)[0], 4)
        self.assertIsNotNone(target)
        self.assertLess(target.x(), ball.x())
        self.assertLess(abs(target.y()), abs(ball.y()))

    def test_flank_restart_goalmouth_lock_rejects_owner_and_central_ball(self) -> None:
        profile = resolve_experiment_profile("candidate_44")
        flank_ball = Vector2D(self.sp.our_penalty_area_line_x() + 3.0, -17.0)
        players = [
            _Teammate(2, flank_ball.x() + 0.4, flank_ball.y() + 0.2),
            _Teammate(3, self.sp.our_penalty_area_line_x() - 5.0, -7.5),
        ]
        owner_world = _OffBallWorld(2, flank_ball, players, self_cycle=7, teammate_cycle=5, opponent_cycle=3)
        guard_world = _OffBallWorld(3, flank_ball, players, self_cycle=7, teammate_cycle=5, opponent_cycle=3)
        central_world = _OffBallWorld(3, Vector2D(flank_ball.x(), -5.0), players)
        decision_module._RECENT_OUR_KICKOFF_CYCLE = 16000
        for world in (owner_world, guard_world, central_world):
            world.set_cycle(16080)

        self.assertIsNone(flank_restart_goalmouth_lock_target(owner_world, profile=profile, owner_unum=2))
        self.assertIsNotNone(flank_restart_goalmouth_lock_target(guard_world, profile=profile, owner_unum=2))
        self.assertFalse(flank_restart_goalmouth_lock_active(central_world, profile=profile))

    def test_flank_restart_goalmouth_lock_precedes_generic_block(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 3.0, 18.0)
        players = [
            _Teammate(5, ball.x() + 0.4, ball.y() - 0.2),
            _Teammate(4, self.sp.our_penalty_area_line_x() - 5.0, 7.5),
            _Teammate(7, self.sp.our_penalty_area_line_x() - 3.0, 3.0),
        ]
        world = _OffBallWorld(4, ball, players, self_cycle=7, teammate_cycle=5, opponent_cycle=3)
        decision_module._RECENT_OUR_KICKOFF_CYCLE = 17000
        world.set_cycle(17230)

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_44"}):
            action = decide_off_ball_action(world)

        self.assertEqual(action.label, "flank_restart_goalmouth_lock")
        self.assertIsNotNone(action.block_target)
        self.assertLess(action.block_target.x(), ball.x())

    def test_opponent_flank_restart_lock_tracks_only_opponent_restart_window(self) -> None:
        profile = resolve_experiment_profile("candidate_45")
        ball = Vector2D(self.sp.our_penalty_area_line_x() + 3.0, -18.0)
        players = [
            _Teammate(2, ball.x() + 0.4, ball.y() + 0.2),
            _Teammate(3, self.sp.our_penalty_area_line_x() - 5.0, -7.5),
            _Teammate(7, self.sp.our_penalty_area_line_x() - 3.0, -3.0),
        ]
        restart_world = _BackpassWorld(
            SideID.LEFT,
            Vector2D(-12.0, -24.0),
            10.0,
            mode=GameModeType.KickIn_Left,
            self_goalie=False,
            self_unum=3,
            self_pos=Vector2D(-28.0, -10.0),
        )
        restart_world.set_cycle(18000)
        update_recent_opp_flank_restart(restart_world)
        world = _OffBallWorld(3, ball, players, self_cycle=7, teammate_cycle=5, opponent_cycle=3)
        world.set_cycle(18080)

        self.assertTrue(flank_restart_goalmouth_lock_active(world, profile=profile))
        self.assertIsNotNone(flank_restart_goalmouth_lock_target(world, profile=profile, owner_unum=2))

        decision_module._RECENT_OPP_FLANK_RESTART_CYCLE = -1000
        decision_module._RECENT_OUR_KICKOFF_CYCLE = 18100
        world.set_cycle(18160)
        self.assertFalse(flank_restart_goalmouth_lock_active(world, profile=profile))

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

    def test_goalie_backpass_catch_guard_blocks_slow_safe_own_last_touch(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() - 2.0, 0.0)
        world = _BackpassWorld(SideID.RIGHT, ball, self.sp.catchable_area() - 0.2)

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "exp_a_setplay_shield"}):
            self.assertTrue(should_avoid_goalie_backpass_catch(world))

    def test_goalie_backpass_catch_guard_allows_fast_or_pressured_own_last_touch(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() - 2.0, 0.0)
        fast_world = _BackpassWorld(
            SideID.RIGHT,
            ball,
            self.sp.catchable_area() - 0.2,
            velocity=Vector2D(1.6, 0.0),
        )
        pressured_world = _BackpassWorld(
            SideID.RIGHT,
            ball,
            self.sp.catchable_area() - 0.2,
            opponents=[_Opponent(9, ball.x() + 2.0, ball.y())],
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_11"}):
            self.assertFalse(should_avoid_goalie_backpass_catch(fast_world))
            self.assertFalse(should_avoid_goalie_backpass_catch(pressured_world))

    def test_goalie_backpass_catch_guard_can_run_without_setplay_shield(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() - 2.0, 0.0)
        world = _BackpassWorld(SideID.RIGHT, ball, self.sp.catchable_area() - 0.2)

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_11"}):
            self.assertTrue(should_avoid_goalie_backpass_catch(world))


    def test_goalie_backpass_catch_guard_ignores_kickable_teammate_race(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() - 2.0, 0.0)
        world = _BackpassWorld(
            SideID.LEFT,
            ball,
            self.sp.catchable_area() - 0.2,
            teammates=[_Teammate(2, ball.x() + 0.4, ball.y())],
            exist_kickable_teammates=True,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_11"}):
            self.assertTrue(world.exist_kickable_teammates())
            self.assertFalse(should_avoid_goalie_backpass_catch(world))

    def test_goalie_backpass_catch_guard_blocks_next_step_own_last_touch(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() - 5.0, 0.0)
        world = _BackpassWorld(
            SideID.RIGHT,
            ball,
            self.sp.catchable_area() + 0.6,
            velocity=Vector2D(0.7, 0.0),
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_11"}):
            self.assertTrue(should_avoid_goalie_backpass_catch(world))

    def test_goalie_backpass_catch_guard_blocks_recent_teammate_tackle(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() - 5.0, 0.0)
        world = _BackpassWorld(
            SideID.LEFT,
            ball,
            self.sp.catchable_area() - 0.2,
            teammates=[_Teammate(2, ball.x() + 0.8, ball.y(), tackling=True, tackle_count=0)],
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_11"}):
            self.assertTrue(should_avoid_goalie_backpass_catch(world))

    def test_goalie_backpass_catch_guard_remembers_teammate_touch_before_catch_window(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() - 5.0, 0.0)
        world = _BackpassWorld(
            SideID.LEFT,
            ball,
            self.sp.catchable_area() + 3.0,
            teammates=[_Teammate(2, ball.x() + 0.8, ball.y(), kicking=True)],
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "candidate_11"}):
            self.assertFalse(should_avoid_goalie_backpass_catch(world))
            world.set_cycle(206)
            world.set_ball_distance(self.sp.catchable_area() - 0.2)
            world._teammates = []
            self.assertTrue(should_avoid_goalie_backpass_catch(world))


    def test_goalie_backpass_catch_guard_allows_fast_or_pressured_opponent_ball(self) -> None:
        ball = Vector2D(self.sp.our_penalty_area_line_x() - 5.0, 0.0)
        fast_world = _BackpassWorld(
            SideID.LEFT,
            ball,
            self.sp.catchable_area() - 0.2,
            velocity=Vector2D(2.5, 0.0),
        )
        pressured_world = _BackpassWorld(
            SideID.LEFT,
            ball,
            self.sp.catchable_area() - 0.2,
            velocity=Vector2D(1.2, 0.0),
            opponents=[_Opponent(9, ball.x() + 1.5, ball.y())],
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "exp_a_setplay_shield"}):
            self.assertFalse(should_avoid_goalie_backpass_catch(fast_world))
            self.assertFalse(should_avoid_goalie_backpass_catch(pressured_world))

    def test_guarded_possession_returns_none_in_deep_defensive_zone(self) -> None:
        world = _PossessionWorld(Vector2D(-24.0, 0.0), Vector2D(-24.0, 0.0))

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "exp_n_shield_guarded_transition"}):
            self.assertIsNone(decide_guarded_possession_action(world))

    def test_guarded_possession_prefers_safe_forward_pass(self) -> None:
        teammate = _Teammate(8, 6.0, 6.0)
        world = _PossessionWorld(Vector2D(0.0, 0.0), Vector2D(0.0, 0.0), teammates=[teammate])

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "exp_n_shield_guarded_transition"}):
            action = decide_guarded_possession_action(world)

        self.assertIsNotNone(action)
        self.assertEqual(action.label, "pass_8")

    def test_guarded_possession_does_not_force_dribble_under_pressure(self) -> None:
        world = _PossessionWorld(
            Vector2D(0.0, 0.0),
            Vector2D(0.0, 0.0),
            opponents=[_Opponent(3, 2.0, 0.0)],
            exist_kickable_opponents=True,
            opponent_cycle=1,
        )

        with patch.dict(os.environ, {"ROBOCUP_EXPERIMENT_PROFILE": "exp_n_shield_guarded_transition"}):
            self.assertIsNone(decide_guarded_possession_action(world))

    def test_cyrus_like_opponent_excludes_foxsy_variant(self) -> None:
        class _World:
            def __init__(self, name):
                self._name = name

            def their_team_name(self):
                return self._name

        self.assertTrue(cyrus_like_opponent(_World("Cyrus2D_base")))
        self.assertTrue(cyrus_like_opponent(_World("CYRUS")))
        self.assertFalse(cyrus_like_opponent(_World("foxsy_cyrus")))
        self.assertFalse(cyrus_like_opponent(_World("HELIOS_base")))
        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "cyrus2d"}):
            self.assertTrue(cyrus_like_opponent(_World("")))
        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "foxsy_cyrus"}):
            self.assertFalse(cyrus_like_opponent(_World("Cyrus2D_base")))

    def test_foxsy_cyrus_opponent_only_matches_foxsy_variant(self) -> None:
        class _World:
            def __init__(self, name):
                self._name = name

            def their_team_name(self):
                return self._name

        self.assertTrue(foxsy_cyrus_opponent(_World("foxsy_cyrus")))
        self.assertFalse(foxsy_cyrus_opponent(_World("Cyrus2D_base")))
        self.assertFalse(foxsy_cyrus_opponent(_World("HELIOS_base")))
        with patch.dict(os.environ, {"ROBOCUP_OPPONENT_KEY": "foxsy_cyrus"}):
            self.assertTrue(foxsy_cyrus_opponent(_World("Cyrus2D_base")))

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
