#!/usr/bin/env python3
from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pyrus2d_bootstrap import bootstrap_pyrus2d


bootstrap_pyrus2d(PROJECT_ROOT)

from base.strategy_formation import StrategyFormation
from lib.action.go_to_point import GoToPoint
from lib.action.intercept import Intercept
from lib.action.neck_turn_to_ball_or_scan import NeckTurnToBallOrScan
from lib.action.scan_field import ScanField
from lib.action.neck_turn_to_ball import NeckTurnToBall
from lib.action.smart_kick import SmartKick
from lib.debug.debug import log
from lib.player.soccer_action import BodyAction, NeckAction
from lib.rcsc.types import GameModeType
from lib.rcsc.server_param import ServerParam
from player.experiment_profile import get_experiment_profile
from pyrusgeom.angle_deg import AngleDeg
from pyrusgeom.vector_2d import Vector2D

if TYPE_CHECKING:
    from lib.player.player_agent import PlayerAgent
    from lib.player.object_player import PlayerObject
    from lib.player.world_model import WorldModel


RL_MODE = os.environ.get("ROBOCUP_RL_MODE", "0") == "1"
RL_CONTROL_UNUM = int(os.environ.get("ROBOCUP_RL_CONTROL_UNUM", "10"))
RL_MODEL_PATH = os.environ.get("ROBOCUP_RL_MODEL_PATH", "").strip()

_RL_POLICY = None
_RL_POLICY_DEVICE = None
_RL_REQUEST_ID = 0
_RL_LAST_ACTION_SOURCE = "reset"
_BHV_MOVE = None
_RECENT_OUR_KICKOFF_CYCLE = -1000
_RECENT_NON_KICKOFF_RESTART_CYCLE = -1000
_RECENT_OPP_CENTRAL_RESTART_CYCLE = -1000
_RECENT_OPP_FLANK_RESTART_CYCLE = -1000


class Body_SmartKick(SmartKick):
    pass


class Body_GoToPoint(GoToPoint):
    pass


class Neck_TurnToBall(NeckTurnToBall):
    pass


class Neck_SafeTurnToBall(NeckAction):
    def execute(self, agent: "PlayerAgent"):
        wm = agent.world()
        if not wm.ball().pos_valid():
            return True

        effector = agent.effector()
        my_next = effector.queued_next_self_pos()
        ball_next = effector.queued_next_ball_pos()
        target_angle = (ball_next - my_next).th()
        neck_moment = target_angle - effector.queued_next_self_body() - wm.self().neck()
        agent.do_turn_neck(AngleDeg(neck_moment.degree()))
        return True


class Body_KickOneStep(BodyAction):
    def __init__(self, target_point: Vector2D, first_speed: float):
        super().__init__()
        self._target_point = target_point.copy()
        self._first_speed = first_speed

    def execute(self, agent: "PlayerAgent"):
        wm = agent.world()
        sp = ServerParam.i()

        if not wm.self().is_kickable():
            return False

        target_vel = self._target_point - wm.ball().pos()
        if target_vel.r() < 1.0e-6:
            return False

        target_vel.set_length(min(self._first_speed, sp.ball_speed_max()))
        kick_accel = target_vel - wm.ball().vel()
        kick_power = min(sp.max_power(), kick_accel.r() / max(wm.self().kick_rate(), 1.0e-6))
        kick_dir = kick_accel.th() - wm.self().body()
        return agent.do_kick(kick_power, kick_dir)


class Body_RestartSafetyPunt(Body_KickOneStep):
    pass


class Body_Dribble(BodyAction):
    def __init__(self, target_point: Vector2D, advance: float = 4.0):
        super().__init__()
        self._target_point = target_point.copy()
        self._advance = advance

    def execute(self, agent: "PlayerAgent"):
        wm = agent.world()

        if not wm.self().is_kickable():
            return False

        direction = self._target_point - wm.self().pos()
        if direction.r() < 1.0e-6:
            direction = Vector2D(1.0, 0.0)

        direction.set_length(self._advance)
        dribble_target = wm.self().pos() + direction
        dribble_target = clamp_to_field(dribble_target, margin_x=1.5, margin_y=1.5)

        return Body_SmartKick(dribble_target, 0.9, 0.6, 2).execute(agent)


class Body_BhvKick(BodyAction):
    def execute(self, agent: "PlayerAgent"):
        from base.bhv_kick import BhvKick

        try:
            if BhvKick().execute(agent):
                return True
        except Exception as exc:
            log.os_log().error(f"BhvKick crashed this cycle, fallback to safe kick: {exc}")

        fallback = decide_on_ball_fallback_action(agent.world())
        fallback.body.execute(agent)
        if fallback.neck is not None:
            agent.set_neck_action(fallback.neck)
        return True


class Body_BhvMove(BodyAction):
    def execute(self, agent: "PlayerAgent"):
        wm = agent.world()
        sp = ServerParam.i()
        label = getattr(agent, "_aurora_last_action_label", "")

        if label == "bhv_move_intercept":
            if Intercept().execute(agent):
                agent.set_neck_action(Neck_TurnToBall())
                return True
            return self._move_to_target(agent, shifted_formation_position(wm), 1.0, sp.max_dash_power())

        target = getattr(agent, "_aurora_last_decision_target", None)
        if target is None:
            target = shifted_formation_position(wm)

        dist_thr = max(wm.ball().dist_from_self() * 0.1, 1.0)
        return self._move_to_target(agent, target, dist_thr, sp.max_dash_power())

    @staticmethod
    def _move_to_target(agent: "PlayerAgent", target: Vector2D, dist_thr: float, dash_power: float) -> bool:
        if Body_GoToPoint(target, dist_thr, dash_power).execute(agent):
            agent.set_neck_action(Neck_SafeTurnToBall())
            return True

        ScanField().execute(agent)
        return True


class Body_BhvSetPlay(BodyAction):
    def execute(self, agent: "PlayerAgent"):
        from base.set_play.bhv_set_play import Bhv_SetPlay

        try:
            if Bhv_SetPlay().execute(agent):
                return True
        except Exception as exc:
            log.os_log().error(f"Bhv_SetPlay crashed, fallback to formation move: {exc}")

        wm = agent.world()
        sp = ServerParam.i()
        target = shifted_formation_position(wm)
        return Body_GoToPoint(target, 1.0, sp.max_dash_power()).execute(agent)


class Body_GoalieDecision(BodyAction):
    def execute(self, agent: "PlayerAgent"):
        if try_safe_goalie_restart(agent):
            return True
        if try_avoid_goalie_backpass_catch(agent):
            return True
        if try_goalie_box_sweeper_intercept(agent):
            return True
        if try_goalie_flank_box_intercept(agent):
            return True

        from base import goalie_decision

        try:
            return goalie_decision.decision(agent)
        except Exception as exc:
            log.os_log().error(f"goalie_decision crashed: {exc}")
            return False


class Body_BhvBlock(BodyAction):
    def execute(self, agent: "PlayerAgent"):
        target = getattr(agent, "_aurora_last_block_target", None)
        if target is not None and Body_GoToPoint(target, 0.1, 100.0).execute(agent):
            agent.set_neck_action(Neck_TurnToBall())
            return True
        return Body_BhvMove().execute(agent)


class Body_BasicTackle(BodyAction):
    def execute(self, agent: "PlayerAgent"):
        from base.basic_tackle import BasicTackle

        try:
            if BasicTackle(0.8, 80).execute(agent):
                return True
        except Exception as exc:
            log.os_log().error(f"BasicTackle crashed, fallback to BhvMove/BhvKick: {exc}")

        if agent.world().self().is_kickable():
            return Body_BhvKick().execute(agent)
        return Body_BhvMove().execute(agent)


@dataclass
class Action:
    body: BodyAction
    neck: NeckAction | None
    label: str
    decision_target: Vector2D | None = None
    block_target: Vector2D | None = None

    def execute(self, agent: "PlayerAgent"):
        log.debug_client().add_message(self.label)
        setattr(agent, "_aurora_last_action_label", self.label)
        setattr(agent, "_aurora_last_decision_target", self.decision_target.copy() if self.decision_target is not None else None)
        setattr(agent, "_aurora_last_block_target", self.block_target.copy() if self.block_target is not None else None)
        self.body.execute(agent)
        if self.neck is not None:
            agent.set_neck_action(self.neck)
        return self


DEFENSIVE_FIELD_UNUMS = (2, 3, 4, 5, 6, 7, 8)


def get_decision(agent: "PlayerAgent") -> Action:
    wm = agent.world()
    update_recent_our_kickoff(wm)
    update_recent_opp_central_restart(wm)
    update_recent_opp_flank_restart(wm)
    StrategyFormation.i().update(wm)

    if RL_MODE and should_use_rl(wm):
        rl_action = get_rl_decision(wm)
        if rl_action is not None:
            return rl_action

    return get_rule_based_decision(agent)


def should_use_rl(wm: "WorldModel") -> bool:
    return not wm.self().goalie() and wm.self().unum() == RL_CONTROL_UNUM


def get_rule_based_decision(agent: "PlayerAgent") -> Action:
    wm = agent.world()

    if wm.self().goalie():
        return Action(body=Body_GoalieDecision(), neck=None, label="goalie_decision")

    if wm.game_mode().type() != GameModeType.PlayOn:
        weak_grounder_restart = decide_weak_team_restart_grounder_action(wm)
        if weak_grounder_restart is not None:
            return weak_grounder_restart
        weak_restart_attack = decide_weak_team_restart_attack_action(wm)
        if weak_restart_attack is not None:
            return weak_restart_attack
        setplay_wall_action = decide_opponent_flank_setplay_wall_action(wm)
        if setplay_wall_action is not None:
            return setplay_wall_action
        central_setplay_wall_action = decide_opponent_central_setplay_wall_action(wm)
        if central_setplay_wall_action is not None:
            return central_setplay_wall_action
        wide_outlet_action = decide_restart_wide_outlet_action(wm)
        if wide_outlet_action is not None:
            return wide_outlet_action
        restart_action = decide_restart_safety_punt_action(wm)
        if restart_action is not None:
            return restart_action
        return Action(body=Body_BhvSetPlay(), neck=None, label="set_play")

    if _should_tackle(wm):
        return Action(body=Body_BasicTackle(), neck=None, label="basic_tackle")

    if wm.self().is_kickable():
        return decide_on_ball_action(agent)

    return decide_off_ball_action(wm)


def decide_weak_team_restart_attack_action(wm: "WorldModel") -> Action | None:
    profile = get_experiment_profile()
    if not weak_team_killer_active(wm, profile=profile):
        return None
    if wm.self().goalie() or not wm.self().is_kickable():
        return None

    game_mode = wm.game_mode()
    if game_mode.side() != wm.our_side():
        return None
    if game_mode.type().is_kick_off():
        if weak_team_restart_channel_entry_active(wm, profile=profile):
            return weak_team_restart_channel_entry_action(wm, "weak_team_kickoff_channel_entry")
        return weak_team_goal_kick_action(wm, "weak_team_kickoff_direct_shoot", speed_scale=1.0)
    if game_mode.type().is_corner_kick():
        if weak_team_restart_channel_entry_active(wm, profile=profile):
            return weak_team_restart_channel_entry_action(wm, "weak_team_corner_channel_entry")
        return weak_team_goal_kick_action(wm, "weak_team_corner_direct_shoot", speed_scale=0.92)
    return None


def weak_team_restart_channel_entry_action(wm: "WorldModel", label: str) -> Action:
    target = weak_team_restart_channel_entry_target(wm)
    speed = clamp(wm.ball().pos().dist(target) * 0.12 + 1.15, 1.8, 2.65)
    return Action(
        body=Body_KickOneStep(target, speed),
        neck=Neck_TurnToBall(),
        label=label,
        decision_target=target,
    )


def weak_team_restart_channel_entry_target(wm: "WorldModel") -> Vector2D:
    profile = get_experiment_profile()
    if weak_team_frontline_slots_active(wm, profile=profile):
        return weak_team_frontline_slot_for_unum(world_self_unum(wm), wm.ball().pos())

    ball = wm.ball().pos()
    receiver = choose_weak_team_channel_receiver(wm)
    if receiver is not None:
        pos = receiver.pos()
        target_x = clamp(max(pos.x() + 8.0, 14.0), 14.0, 26.0)
        target_y = clamp(pos.y() * 0.45, -12.0, 12.0)
    else:
        sign = 1.0 if ball.y() >= 0.0 else -1.0
        if abs(ball.y()) < 2.0:
            sign = 1.0 if world_self_unum(wm) % 2 == 0 else -1.0
        target_x = 18.0 if ball.x() < 8.0 else clamp(ball.x() + 10.0, 18.0, 28.0)
        target_y = sign * (7.0 if abs(ball.y()) < 18.0 else 10.0)
    return clamp_to_field(Vector2D(target_x, target_y), margin_x=8.0, margin_y=3.0)


def weak_team_goal_kick_action(wm: "WorldModel", label: str, speed_scale: float = 1.0) -> Action:
    sp = ServerParam.i()
    ball_y = wm.ball().pos().y()
    target_y = 0.0 if abs(ball_y) < 1.0 else 3.0 if ball_y > 0.0 else -3.0
    target = Vector2D(sp.pitch_half_length(), target_y)
    return Action(
        body=Body_KickOneStep(target, sp.ball_speed_max() * speed_scale),
        neck=Neck_TurnToBall(),
        label=label,
        decision_target=target,
    )


def decide_weak_team_restart_grounder_action(wm: "WorldModel", profile=None) -> Action | None:
    if profile is None:
        profile = get_experiment_profile()
    if not weak_team_restart_grounder_active(wm, profile=profile):
        return None

    game_mode = wm.game_mode()
    if game_mode.type().is_kick_off():
        label = "weak_team_kickoff_grounder"
    elif game_mode.type().is_corner_kick():
        label = "weak_team_corner_grounder"
    else:
        return None

    target = weak_team_restart_grounder_target(wm)
    speed = clamp(wm.ball().pos().dist(target) * 0.11 + 1.15, 1.85, 2.65)
    return Action(
        body=Body_KickOneStep(target, speed),
        neck=Neck_TurnToBall(),
        label=label,
        decision_target=target,
    )


def weak_team_restart_grounder_target(wm: "WorldModel") -> Vector2D:
    ball = wm.ball().pos()
    receiver = choose_weak_team_restart_grounder_receiver(wm)
    if receiver is not None:
        pos = receiver.pos()
        target_x = clamp(max(pos.x() + 3.0, 20.0), 18.0, 30.0)
        target_y = clamp(pos.y() * 0.65, -13.0, 13.0)
        return clamp_to_field(Vector2D(target_x, target_y), margin_x=8.0, margin_y=3.0)

    sign = 1.0 if world_self_unum(wm) in (8, 10, 11) else -1.0
    if abs(ball.y()) > 1.0:
        sign = 1.0 if ball.y() >= 0.0 else -1.0
    return clamp_to_field(Vector2D(22.0, sign * 8.0), margin_x=8.0, margin_y=3.0)


def choose_weak_team_restart_grounder_receiver(wm: "WorldModel"):
    best = None
    best_score = -1.0e9
    ball = wm.ball().pos()
    for teammate in wm.teammates():
        if teammate is None or teammate.unum() not in (9, 10, 11):
            continue
        if teammate.pos_count() > 8 or teammate.is_ghost() or teammate.is_tackling():
            continue
        pos = teammate.pos()
        if pos.x() < -8.0 or pos.x() > 28.0:
            continue
        if abs(pos.y()) > 22.0:
            continue
        space = nearest_valid_opponent_distance(wm, pos)
        if space < 1.8:
            continue
        score = pos.x() * 0.7 + space - abs(pos.y()) * 0.08
        if teammate.unum() == 10:
            score += 1.8
        if pos.x() > ball.x() + 2.0:
            score += 1.5
        if score > best_score:
            best_score = score
            best = teammate
    return best


def decide_weak_team_overdrive_on_ball_action(wm: "WorldModel", profile=None) -> Action | None:
    if profile is None:
        profile = get_experiment_profile()
    if not weak_team_overdrive_active(wm, profile=profile):
        return None
    if wm.self().goalie() or not wm.self().is_kickable():
        return None
    if wm.game_mode().type() != GameModeType.PlayOn:
        return None

    me = wm.self().pos()
    if me.x() < -28.0:
        return None

    target = weak_team_overdrive_shot_target(wm)
    speed = ServerParam.i().ball_speed_max()
    if me.x() < -2.0 and nearest_valid_opponent_distance(wm, me) > 5.0:
        speed = min(speed, 2.65)
    return Action(
        body=Body_KickOneStep(target, speed),
        neck=Neck_TurnToBall(),
        label="weak_team_overdrive_direct_attack",
        decision_target=target,
    )


def weak_team_overdrive_shot_target(wm: "WorldModel") -> Vector2D:
    sp = ServerParam.i()
    me = wm.self().pos()
    ball_y = wm.ball().pos().y()

    if me.x() < 4.0:
        target_x = 35.0
        target_y = clamp(ball_y * 0.35, -10.0, 10.0)
    else:
        target_x = sp.pitch_half_length()
        target_y = clamp(-ball_y * 0.18, -4.0, 4.0)
        if abs(ball_y) < 5.0:
            target_y = 3.0 if world_self_unum(wm) % 2 == 0 else -3.0

    return Vector2D(target_x, target_y)


def decide_weak_team_front_third_finish_action(wm: "WorldModel", profile=None) -> Action | None:
    if profile is None:
        profile = get_experiment_profile()
    if not (
        weak_team_front_third_finish_active(wm, profile=profile)
        or weak_team_frontline_post_finish_active(wm, profile=profile)
    ):
        return None
    if wm.self().goalie() or not wm.self().is_kickable():
        return None
    if wm.game_mode().type() != GameModeType.PlayOn:
        return None

    me = wm.self().pos()
    ball = wm.ball().pos()
    post_finish = weak_team_frontline_post_finish_active(wm, profile=profile)
    if post_finish and world_self_unum(wm) not in (9, 10, 11):
        return None
    if post_finish and max(me.x(), ball.x()) < 26.0:
        return None
    if max(me.x(), ball.x()) < 24.0:
        return None
    if abs(ball.y()) > 24.0:
        return None

    if wm.exist_kickable_opponents() and nearest_valid_opponent_distance(wm, me) < 1.0:
        return None

    target = (
        weak_team_frontline_post_finish_target(wm)
        if post_finish
        else weak_team_front_third_finish_target(wm)
    )
    return Action(
        body=Body_KickOneStep(target, ServerParam.i().ball_speed_max()),
        neck=Neck_TurnToBall(),
        label="weak_team_frontline_post_finish" if post_finish else "weak_team_front_third_finish",
        decision_target=target,
    )


def weak_team_front_third_finish_target(wm: "WorldModel") -> Vector2D:
    sp = ServerParam.i()
    ball_y = wm.ball().pos().y()
    target_y = clamp(-ball_y * 0.15, -3.0, 3.0)
    if abs(target_y) < 0.5 and abs(ball_y) < 6.0:
        target_y = 2.5 if world_self_unum(wm) % 2 == 0 else -2.5
    return Vector2D(sp.pitch_half_length(), target_y)


def weak_team_frontline_post_finish_target(wm: "WorldModel") -> Vector2D:
    sp = ServerParam.i()
    ball_y = wm.ball().pos().y()
    if abs(ball_y) >= 5.0:
        target_y = clamp(ball_y * 0.42, -6.6, 6.6)
    else:
        target_y = 5.8 if world_self_unum(wm) == 11 else -5.8 if world_self_unum(wm) == 9 else 4.8
    return Vector2D(sp.pitch_half_length(), target_y)


def decide_weak_team_natural_channel_feed_action(wm: "WorldModel", profile=None) -> Action | None:
    if profile is None:
        profile = get_experiment_profile()
    if not weak_team_natural_channel_feed_active(wm, profile=profile):
        return None
    if wm.self().goalie() or not wm.self().is_kickable():
        return None
    if wm.game_mode().type() != GameModeType.PlayOn:
        return None

    me = wm.self().pos()
    ball = wm.ball().pos()
    natural_x = max(me.x(), ball.x())
    if natural_x < 6.0 or natural_x > 24.0:
        return None
    if abs(ball.y()) > 24.0:
        return None
    if wm.exist_kickable_opponents() and nearest_valid_opponent_distance(wm, me) < 1.4:
        return None

    receiver = choose_weak_team_natural_channel_receiver(wm)
    if receiver is None:
        return None

    target = weak_team_natural_channel_feed_target(wm, receiver)
    distance = ball.dist(target)
    speed = clamp(distance * 0.10 + 1.15, 1.7, 2.45)
    return Action(
        body=Body_KickOneStep(target, speed),
        neck=Neck_TurnToBall(),
        label="weak_team_natural_channel_feed",
        decision_target=target,
    )


def weak_team_natural_channel_feed_target(wm: "WorldModel", receiver) -> Vector2D:
    ball = wm.ball().pos()
    receiver_pos = receiver.pos()
    target_x = clamp(max(ball.x() + 10.0, receiver_pos.x() + 2.0), 24.0, 34.0)
    target_y = clamp(receiver_pos.y() * 0.75, -14.0, 14.0)
    return clamp_to_field(Vector2D(target_x, target_y), margin_x=8.0, margin_y=3.0)


def choose_weak_team_natural_channel_receiver(wm: "WorldModel"):
    best = None
    best_score = -1.0e9
    ball = wm.ball().pos()
    for teammate in wm.teammates():
        if teammate is None or teammate.unum() not in (9, 10, 11):
            continue
        if teammate.pos_count() > 8 or teammate.is_ghost() or teammate.is_tackling():
            continue
        pos = teammate.pos()
        if pos.x() <= ball.x() + 7.0:
            continue
        if pos.x() < 14.0 or pos.x() > 34.0:
            continue
        if abs(pos.y()) >= 24.0:
            continue
        space = nearest_valid_opponent_distance(wm, pos)
        if space <= 2.0:
            continue
        score = (pos.x() - ball.x()) * 1.7 + space * 1.2 - abs(pos.y()) * 0.15
        if teammate.unum() in (10, 11):
            score += 1.5
        if score > best_score:
            best_score = score
            best = teammate
    return best


def decide_weak_team_deep_cutback_action(wm: "WorldModel", profile=None) -> Action | None:
    if profile is None:
        profile = get_experiment_profile()
    if not weak_team_deep_cutback_active(wm, profile=profile):
        return None
    if wm.self().goalie() or not wm.self().is_kickable():
        return None
    if wm.game_mode().type() != GameModeType.PlayOn:
        return None

    me = wm.self().pos()
    ball = wm.ball().pos()
    if max(me.x(), ball.x()) < 28.0:
        return None
    if abs(ball.y()) > 26.0:
        return None
    if wm.exist_kickable_opponents() and nearest_valid_opponent_distance(wm, me) < 0.9:
        return None

    receiver = choose_weak_team_deep_cutback_receiver(wm)
    if receiver is not None:
        target = weak_team_deep_cutback_target(wm, receiver)
        speed = clamp(ball.dist(target) * 0.12 + 1.2, 1.8, 2.55)
        return Action(
            body=Body_KickOneStep(target, speed),
            neck=Neck_TurnToBall(),
            label="weak_team_deep_cutback",
            decision_target=target,
        )

    if max(me.x(), ball.x()) >= 32.0 and abs(ball.y()) <= 22.0:
        target = weak_team_deep_far_post_target(wm)
        return Action(
            body=Body_KickOneStep(target, ServerParam.i().ball_speed_max()),
            neck=Neck_TurnToBall(),
            label="weak_team_deep_far_post_finish",
            decision_target=target,
        )
    return None


def decide_weak_team_restart_second_finish_action(wm: "WorldModel", profile=None) -> Action | None:
    if profile is None:
        profile = get_experiment_profile()
    if not weak_team_restart_second_finish_active(wm, profile=profile):
        return None
    if wm.self().goalie() or not wm.self().is_kickable():
        return None
    if wm.game_mode().type() != GameModeType.PlayOn:
        return None

    me = wm.self().pos()
    ball = wm.ball().pos()
    if max(me.x(), ball.x()) < 18.0:
        return None
    if abs(ball.y()) > 24.0:
        return None
    if wm.exist_kickable_opponents() and nearest_valid_opponent_distance(wm, me) < 0.9:
        return None

    target = weak_team_restart_second_finish_target(wm)
    return Action(
        body=Body_KickOneStep(target, ServerParam.i().ball_speed_max()),
        neck=Neck_TurnToBall(),
        label="weak_team_restart_second_finish",
        decision_target=target,
    )


def weak_team_restart_second_finish_target(wm: "WorldModel") -> Vector2D:
    sp = ServerParam.i()
    ball_y = wm.ball().pos().y()
    if abs(ball_y) < 5.0:
        target_y = 5.8 if world_self_unum(wm) in (10, 11) else -5.8
    else:
        target_y = clamp(-ball_y * 0.32, -6.4, 6.4)
    return Vector2D(sp.pitch_half_length(), target_y)


def decide_weak_team_natural_high_frontline_finish_action(wm: "WorldModel", profile=None) -> Action | None:
    if profile is None:
        profile = get_experiment_profile()
    if not weak_team_natural_high_frontline_finish_active(wm, profile=profile):
        return None
    if wm.self().goalie() or not wm.self().is_kickable():
        return None
    if wm.game_mode().type() != GameModeType.PlayOn:
        return None

    unum = world_self_unum(wm)
    if unum not in (9, 11):
        return None

    me = wm.self().pos()
    ball = wm.ball().pos()
    natural_x = max(me.x(), ball.x())
    if natural_x < 34.0:
        return None
    if abs(ball.y()) < 7.0 or abs(ball.y()) > 24.0:
        return None
    if me.y() * ball.y() < 0.0 and abs(me.y() - ball.y()) > 8.0:
        return None
    if wm.exist_kickable_opponents() and nearest_valid_opponent_distance(wm, me) < 1.0:
        return None
    if nearest_valid_opponent_distance(wm, ball) < 0.8:
        return None

    target = weak_team_natural_high_frontline_finish_target(wm)
    return Action(
        body=Body_KickOneStep(target, ServerParam.i().ball_speed_max()),
        neck=Neck_TurnToBall(),
        label="weak_team_natural_high_frontline_finish",
        decision_target=target,
    )


def weak_team_natural_high_frontline_finish_target(wm: "WorldModel") -> Vector2D:
    sp = ServerParam.i()
    ball_y = wm.ball().pos().y()
    post_y = -6.4 if ball_y > 0.0 else 6.4
    if abs(ball_y) >= 15.0:
        post_y = -5.6 if ball_y > 0.0 else 5.6
    return Vector2D(sp.pitch_half_length(), post_y)


def choose_weak_team_deep_cutback_receiver(wm: "WorldModel"):
    best = None
    best_score = -1.0e9
    ball = wm.ball().pos()
    for teammate in wm.teammates():
        if teammate is None or teammate.unum() not in (9, 10, 11):
            continue
        if teammate.pos_count() > 8 or teammate.is_ghost() or teammate.is_tackling():
            continue
        if teammate.unum() == world_self_unum(wm):
            continue
        pos = teammate.pos()
        if pos.x() < 24.0 or pos.x() > 38.0:
            continue
        if abs(pos.y()) > 22.0:
            continue
        if pos.x() > ball.x() + 8.0:
            continue
        if pos.x() < ball.x() - 10.0:
            continue
        if ball.y() * pos.y() > 0.0 and abs(ball.y()) > 8.0 and abs(pos.y()) > 8.0:
            continue
        space = nearest_valid_opponent_distance(wm, pos)
        if space < 2.2:
            continue
        score = space * 1.3 + pos.x() * 0.25 - abs(pos.y()) * 0.2
        if abs(pos.y()) < abs(ball.y()) - 4.0:
            score += 3.0
        if teammate.unum() == 10:
            score += 1.0
        if score > best_score:
            best_score = score
            best = teammate
    return best


def weak_team_deep_cutback_target(wm: "WorldModel", receiver) -> Vector2D:
    ball = wm.ball().pos()
    receiver_pos = receiver.pos()
    target_x = clamp(receiver_pos.x() + 1.5, 27.0, 37.0)
    target_y = clamp(receiver_pos.y() * 0.55, -10.0, 10.0)
    if abs(ball.y()) > 10.0 and abs(target_y) > 7.0:
        target_y = 6.0 if target_y > 0.0 else -6.0
    return clamp_to_field(Vector2D(target_x, target_y), margin_x=8.0, margin_y=3.0)


def weak_team_deep_far_post_target(wm: "WorldModel") -> Vector2D:
    sp = ServerParam.i()
    ball_y = wm.ball().pos().y()
    if abs(ball_y) < 4.0:
        target_y = 5.6 if world_self_unum(wm) in (10, 11) else -5.6
    else:
        target_y = clamp(-ball_y * 0.38, -6.2, 6.2)
    return Vector2D(sp.pitch_half_length(), target_y)


def decide_weak_team_channel_entry_action(wm: "WorldModel", profile=None) -> Action | None:
    if profile is None:
        profile = get_experiment_profile()
    if not weak_team_channel_entry_active(wm, profile=profile):
        return None
    if wm.self().goalie() or not wm.self().is_kickable():
        return None
    if wm.game_mode().type() != GameModeType.PlayOn:
        return None

    me = wm.self().pos()
    ball = wm.ball().pos()
    if me.x() < -6.0 or ball.x() < -8.0:
        return None
    if ball.x() > 30.0:
        return None
    if abs(ball.y()) > 24.0:
        return None
    if wm.exist_kickable_opponents() and nearest_valid_opponent_distance(wm, me) < 1.6:
        return None

    our_min = min(wm.intercept_table().self_reach_cycle(), wm.intercept_table().teammate_reach_cycle())
    opp_min = wm.intercept_table().opponent_reach_cycle()
    if our_min > opp_min + 2:
        return None

    target = weak_team_channel_entry_target(wm)
    distance = ball.dist(target)
    speed = clamp(distance * 0.12 + 1.25, 2.1, ServerParam.i().ball_speed_max())
    return Action(
        body=Body_KickOneStep(target, speed),
        neck=Neck_TurnToBall(),
        label="weak_team_channel_entry",
        decision_target=target,
    )


def weak_team_channel_entry_target(wm: "WorldModel") -> Vector2D:
    ball = wm.ball().pos()
    receiver = choose_weak_team_channel_receiver(wm)
    if receiver is not None:
        receiver_pos = receiver.pos()
        target_x = clamp(max(receiver_pos.x() + 8.0, ball.x() + 14.0, 28.0), 28.0, 38.0)
        target_y = clamp(receiver_pos.y() * 0.55, -12.0, 12.0)
    else:
        sign = 1.0 if ball.y() >= 0.0 else -1.0
        if abs(ball.y()) < 3.0:
            sign = 1.0 if world_self_unum(wm) % 2 == 0 else -1.0
        target_x = clamp(max(ball.x() + 16.0, 30.0), 30.0, 38.0)
        target_y = sign * 7.0

    return clamp_to_field(Vector2D(target_x, target_y), margin_x=8.0, margin_y=3.0)


def choose_weak_team_channel_receiver(wm: "WorldModel"):
    best = None
    best_score = -1.0e9
    ball = wm.ball().pos()
    for teammate in wm.teammates():
        if teammate is None or teammate.unum() not in (9, 10, 11):
            continue
        if teammate.pos_count() > 8 or teammate.is_ghost() or teammate.is_tackling():
            continue
        pos = teammate.pos()
        if pos.x() < ball.x() - 4.0 or pos.x() > 34.0:
            continue
        if abs(pos.y()) > 23.0:
            continue
        space = nearest_valid_opponent_distance(wm, pos)
        if space < 2.0:
            continue
        score = (pos.x() - ball.x()) * 1.4 + pos.x() * 0.35 + space - abs(pos.y()) * 0.12
        if teammate.unum() in (10, 11):
            score += 2.0
        if score > best_score:
            best_score = score
            best = teammate
    return best


def get_rl_decision(wm: "WorldModel") -> Action | None:
    global _RL_LAST_ACTION_SOURCE

    action_id = get_bridge_action_id(wm)
    if action_id is not None:
        _RL_LAST_ACTION_SOURCE = "bridge"
        return action_from_rl_id(action_id, wm)

    action_id = get_model_action_id(wm)
    if action_id is not None:
        _RL_LAST_ACTION_SOURCE = "model"
        return action_from_rl_id(action_id, wm)

    _RL_LAST_ACTION_SOURCE = "rule_fallback"
    return None


def get_bridge_action_id(wm: "WorldModel") -> int | None:
    from train import bridge, config
    from train.state import build_bridge_state_message

    episode_id = os.environ.get(config.EPISODE_ID_ENV, "").strip()
    if not episode_id:
        return None

    try:
        bridge.ensure_bridge_client_from_env()
    except Exception as exc:
        log.os_log().warn(f"RL bridge connect failed: {exc}")
        return None

    global _RL_REQUEST_ID
    request_id = _RL_REQUEST_ID
    _RL_REQUEST_ID += 1

    state_message = build_bridge_state_message(
        wm,
        episode_id=episode_id,
        request_id=request_id,
        prev_action_source=_RL_LAST_ACTION_SOURCE,
    )
    if not bridge.put_state_message(state_message, timeout=config.ACTION_TIMEOUT_SEC):
        log.os_log().warn("RL state queue put timed out")
        return None

    action_message = bridge.get_action_message(
        episode_id=episode_id,
        request_id=request_id,
        timeout=config.ACTION_TIMEOUT_SEC,
    )
    if action_message is None:
        log.os_log().warn(f"RL action queue get timed out at cycle {wm.time().cycle()}")
        return None

    try:
        return int(action_message.get("action_id", 16))
    except (TypeError, ValueError):
        return 16


def get_model_action_id(wm: "WorldModel") -> int | None:
    if not RL_MODEL_PATH:
        return None

    try:
        import torch

        from train.state import extract_state_vector

        policy, device = load_rl_policy()
        observation = torch.as_tensor(extract_state_vector(wm), dtype=torch.float32, device=device).unsqueeze(0)
        with torch.no_grad():
            action_probs, _ = policy(observation)
        return int(torch.argmax(action_probs, dim=-1).item())
    except Exception as exc:
        log.os_log().warn(f"RL model inference failed: {exc}")
        return None


def load_rl_policy():
    global _RL_POLICY
    global _RL_POLICY_DEVICE

    if _RL_POLICY is not None:
        return _RL_POLICY, _RL_POLICY_DEVICE

    import torch

    from train.policy_net import ActorCriticPolicy

    device_name = os.environ.get("ROBOCUP_RL_MODEL_DEVICE", "cpu")
    if device_name == "auto":
        device_name = "cuda" if torch.cuda.is_available() else "cpu"

    _RL_POLICY_DEVICE = torch.device(device_name)
    _RL_POLICY = ActorCriticPolicy.load(RL_MODEL_PATH, map_location=_RL_POLICY_DEVICE).to(_RL_POLICY_DEVICE)
    _RL_POLICY.eval()
    return _RL_POLICY, _RL_POLICY_DEVICE


def _get_bhv_move():
    global _BHV_MOVE
    if _BHV_MOVE is None:
        from base.bhv_move import BhvMove

        _BHV_MOVE = BhvMove()
    return _BHV_MOVE


def action_from_rl_id(action_id: int, wm: "WorldModel") -> Action:
    from train.action import action_to_decision

    return action_to_decision(action_id, wm)


def decide_on_ball_action(agent: "PlayerAgent") -> Action:
    wm = agent.world()
    experiment_action = decide_experiment_on_ball_action(wm)
    if experiment_action is not None:
        return experiment_action

    return Action(
        body=Body_BhvKick(),
        neck=None,
        label="bhv_kick",
    )


def decide_on_ball_fallback_action(wm: "WorldModel") -> Action:
    if in_shooting_range(wm):
        return shoot_action(wm)

    teammate = find_best_pass_target(wm)
    if teammate is not None:
        return pass_action(wm, teammate)

    return dribble_action(wm)


def decide_experiment_on_ball_action(wm: "WorldModel") -> Action | None:
    profile = get_experiment_profile()
    overdrive_action = decide_weak_team_overdrive_on_ball_action(wm, profile=profile)
    if overdrive_action is not None:
        return overdrive_action

    front_third_finish = decide_weak_team_front_third_finish_action(wm, profile=profile)
    if front_third_finish is not None:
        return front_third_finish

    restart_second_finish = decide_weak_team_restart_second_finish_action(wm, profile=profile)
    if restart_second_finish is not None:
        return restart_second_finish

    natural_high_frontline_finish = decide_weak_team_natural_high_frontline_finish_action(wm, profile=profile)
    if natural_high_frontline_finish is not None:
        return natural_high_frontline_finish

    deep_cutback = decide_weak_team_deep_cutback_action(wm, profile=profile)
    if deep_cutback is not None:
        return deep_cutback

    natural_channel_feed = decide_weak_team_natural_channel_feed_action(wm, profile=profile)
    if natural_channel_feed is not None:
        return natural_channel_feed

    channel_entry = decide_weak_team_channel_entry_action(wm, profile=profile)
    if channel_entry is not None:
        return channel_entry

    clearance_label = defensive_clearance_label(wm)
    if clearance_label is not None:
        return clearance_action(wm, clearance_label)

    if weak_team_killer_active(wm, profile=profile) and in_shooting_range(wm):
        return shoot_action(wm)
    if profile.key == "exp_n_shield_guarded_transition":
        possession_action = decide_guarded_possession_action(wm)
        if possession_action is not None:
            return possession_action
    if profile.transition_unlock:
        transition_action = decide_transition_unlock_action(wm)
        if transition_action is not None:
            return transition_action

    return None


def decide_restart_safety_punt_action(wm: "WorldModel") -> Action | None:
    profile = get_experiment_profile()
    if not restart_safety_punt_active(wm, profile=profile):
        return None

    sp = ServerParam.i()
    target = choose_restart_safety_punt_target(wm)
    return Action(
        body=Body_RestartSafetyPunt(target, sp.ball_speed_max()),
        neck=Neck_TurnToBall(),
        label="restart_safety_punt",
        decision_target=target,
    )


def decide_opponent_flank_setplay_wall_action(wm: "WorldModel") -> Action | None:
    profile = get_experiment_profile()
    if not opponent_flank_setplay_wall_active(wm, profile=profile):
        return None

    unum = wm.self().unum()
    if unum not in DEFENSIVE_FIELD_UNUMS or wm.self().goalie():
        return None

    target = opponent_flank_setplay_wall_target(unum, wm.ball().pos(), ServerParam.i())
    return Action(
        body=Body_BhvMove(),
        neck=None,
        label="opponent_flank_setplay_wall",
        decision_target=target,
    )


def opponent_flank_setplay_wall_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.opponent_flank_setplay_wall:
        return False
    if not wm.ball().pos_valid():
        return False

    gm = wm.game_mode()
    if gm.side() == wm.our_side():
        return False
    if gm.type() not in (
        GameModeType.KickIn_Left,
        GameModeType.KickIn_Right,
        GameModeType.CornerKick_Left,
        GameModeType.CornerKick_Right,
        GameModeType.FreeKick_Left,
        GameModeType.FreeKick_Right,
        GameModeType.IndFreeKick_Left,
        GameModeType.IndFreeKick_Right,
    ):
        return False

    ball = wm.ball().pos()
    return ball.x() < 12.0 and abs(ball.y()) > 12.0


def opponent_flank_setplay_wall_target(unum: int, ball: Vector2D, sp: "ServerParam") -> Vector2D:
    sign = 1.0 if ball.y() >= 0.0 else -1.0
    near_x = clamp(ball.x() - 10.0, -39.0, -18.0)
    cutback_x = clamp(ball.x() - 15.0, -36.0, -20.0)

    if unum in (2, 5):
        target_y = sign * 18.0 if ((unum == 5) == (sign > 0.0)) else -sign * 8.0
        target = Vector2D(-40.0, target_y)
    elif unum in (3, 4):
        target_y = sign * 6.0 if ((unum == 4) == (sign > 0.0)) else -sign * 3.0
        target = Vector2D(-43.0, target_y)
    elif unum == 6:
        target = Vector2D(near_x, sign * 16.0)
    elif unum == 7:
        target = Vector2D(cutback_x, sign * 8.0)
    elif unum == 8:
        target = Vector2D(cutback_x - 2.0, 0.0)
    else:
        target = Vector2D(cutback_x, sign * 10.0)

    return keep_setplay_distance(clamp_to_field(target, margin_x=3.0, margin_y=1.5), ball, min_dist=10.0)


def decide_opponent_central_setplay_wall_action(wm: "WorldModel") -> Action | None:
    profile = get_experiment_profile()
    if not opponent_central_setplay_wall_active(wm, profile=profile):
        return None

    unum = wm.self().unum()
    if unum not in DEFENSIVE_FIELD_UNUMS or wm.self().goalie():
        return None

    target = opponent_central_setplay_wall_target(unum, wm.ball().pos(), ServerParam.i())
    if target is None:
        return None
    return Action(
        body=Body_BhvMove(),
        neck=None,
        label="opponent_central_setplay_wall",
        decision_target=target,
    )


def opponent_central_setplay_wall_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.opponent_central_setplay_wall:
        return False
    if not wm.ball().pos_valid():
        return False

    gm = wm.game_mode()
    if gm.side() == wm.our_side():
        return False
    if gm.type() not in (
        GameModeType.FreeKick_Left,
        GameModeType.FreeKick_Right,
        GameModeType.IndFreeKick_Left,
        GameModeType.IndFreeKick_Right,
    ):
        return False

    ball = wm.ball().pos()
    return -38.0 <= ball.x() <= 4.0 and abs(ball.y()) <= 12.0


def opponent_central_setplay_wall_target(unum: int, ball: Vector2D, sp: "ServerParam") -> Vector2D | None:
    anchor_x = clamp(ball.x() - 11.0, -43.0, -27.0)
    if unum == 3:
        target = Vector2D(anchor_x - 1.5, -5.5)
    elif unum == 4:
        target = Vector2D(anchor_x - 1.5, 5.5)
    elif unum == 6:
        target = Vector2D(clamp(ball.x() - 8.0, -35.0, -20.0), -9.5)
    elif unum == 8:
        target = Vector2D(clamp(ball.x() - 8.0, -35.0, -20.0), 9.5)
    elif unum == 7:
        target = Vector2D(clamp(ball.x() - 14.0, -38.0, -24.0), 0.0)
    elif unum == 2:
        target = Vector2D(-42.0, -12.5)
    elif unum == 5:
        target = Vector2D(-42.0, 12.5)
    else:
        return None
    return keep_setplay_distance(clamp_to_field(target, margin_x=3.0, margin_y=1.5), ball, min_dist=10.0)


def keep_setplay_distance(target: Vector2D, ball: Vector2D, min_dist: float) -> Vector2D:
    offset = target - ball
    if offset.r() >= min_dist:
        return target
    if offset.r() < 1.0e-6:
        offset = Vector2D(-1.0, -0.2 if ball.y() >= 0.0 else 0.2)
    offset.set_length(min_dist)
    return clamp_to_field(ball + offset, margin_x=3.0, margin_y=1.5)


def decide_restart_wide_outlet_action(wm: "WorldModel") -> Action | None:
    profile = get_experiment_profile()
    if not restart_wide_outlet_active(wm, profile=profile):
        return None

    target = choose_restart_wide_outlet_target(wm)
    speed = clamp(wm.ball().pos().dist(target) * 0.16 + 1.1, 2.2, ServerParam.i().ball_speed_max())
    return Action(
        body=Body_KickOneStep(target, speed),
        neck=Neck_TurnToBall(),
        label="restart_wide_outlet",
        decision_target=target,
    )


def restart_wide_outlet_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.kickoff_wide_outlet:
        return False
    if wm.self().goalie() or not wm.self().is_kickable():
        return False

    game_mode = wm.game_mode()
    return game_mode.type().is_kick_off() and game_mode.side() == wm.our_side()


def choose_restart_wide_outlet_target(wm: "WorldModel") -> Vector2D:
    sign = 1.0 if ((wm.time().cycle() // 200) % 2 == 0) else -1.0
    preferred_unums = (11, 8, 10) if sign > 0.0 else (9, 6, 10)
    fallback = Vector2D(-6.0, sign * 18.0)

    for unum in preferred_unums:
        for teammate in wm.teammates():
            if teammate is None or teammate.unum() != unum:
                continue
            if teammate.pos_count() > 8 or teammate.is_ghost() or teammate.is_tackling():
                continue
            return teammate.pos().copy()
    return fallback


def restart_safety_punt_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.kickoff_safety_punt:
        return False
    if wm.self().goalie() or not wm.self().is_kickable():
        return False

    game_mode = wm.game_mode()
    return game_mode.type().is_kick_off() and game_mode.side() == wm.our_side()


def choose_restart_safety_punt_target(wm: "WorldModel") -> Vector2D:
    sp = ServerParam.i()
    sign = 1.0 if ((wm.time().cycle() // 200) % 2 == 0) else -1.0
    if abs(wm.ball().pos().y()) > 1.0:
        sign = 1.0 if wm.ball().pos().y() >= 0.0 else -1.0
    return Vector2D(sp.pitch_half_length() - 5.0, sign * (sp.pitch_half_width() - 5.0))


def decide_guarded_possession_action(wm: "WorldModel") -> Action | None:
    sp = ServerParam.i()
    me = wm.self().pos()
    ball = wm.ball().pos()

    if me.x() < -20.0 or in_our_penalty_support_zone(ball, sp, x_pad=6.0, y_pad=5.0):
        return None

    if in_shooting_range(wm):
        return shoot_action(wm)

    teammate = find_best_pass_target(wm)
    if teammate is not None:
        return pass_action(wm, teammate)

    pressure = (
        wm.exist_kickable_opponents()
        or wm.intercept_table().opponent_reach_cycle() <= 2
        or nearest_valid_opponent_distance(wm, me) < 4.5
    )
    if pressure:
        return None

    return dribble_action(wm, advance=4.0)


def decide_off_ball_action(wm: "WorldModel") -> Action:
    profile = get_experiment_profile()
    sp = ServerParam.i()
    unum = wm.self().unum()
    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    ball = wm.ball().pos()
    ball_near_sideline = abs(ball.y()) > sp.pitch_half_width() - 8.0
    flank_lock_alert = profile.flank_lock and ball.x() < 8.0 and abs(ball.y()) > 18.0
    disciplined_screen = disciplined_screen_active(profile, ball, self_min, mate_min, opp_min)
    urgent_defense = (
        ball.x() < -12.0
        and self_min <= mate_min + 1
        and self_min <= opp_min + 2
    )

    weak_press_intercept = weak_team_press_intercept_action(wm, profile=profile)
    if weak_press_intercept is not None:
        return weak_press_intercept

    weak_press_target = weak_team_attack_press_target(wm, profile=profile)
    if weak_press_target is not None:
        return Action(
            body=Body_BhvMove(),
            neck=None,
            label="weak_team_attack_press",
            decision_target=weak_press_target,
        )

    owner_unum = None
    if (
        profile.box_entry_owner_lock
        or profile.goalmouth_lane_block
        or profile.flank_cutback_guard
        or profile.central_restart_terminal_guard
        or profile.narrow_kickoff_center_entry_clear
        or profile.flank_restart_goalmouth_lock
        or profile.opponent_flank_restart_goalmouth_lock
    ):
        owner_unum = select_box_entry_owner_unum(wm)
        if owner_unum is None and (
            profile.flank_cutback_guard
            or profile.flank_restart_goalmouth_lock
            or profile.opponent_flank_restart_goalmouth_lock
        ):
            owner_unum = select_flank_ball_owner_unum(wm)
    kickoff_recovery = post_our_kickoff_recovery_active(wm, profile=profile)

    if (
        disciplined_screen
        and unum in (2, 3, 4, 5, 6, 7, 8)
        and wm.self().pos().x() < 8.0
        and self_min > min(mate_min, opp_min)
    ):
        return decide_off_ball_formation_only(wm)

    if (
        kickoff_recovery
        and unum in DEFENSIVE_FIELD_UNUMS
        and wm.self().pos().x() < 8.0
        and self_min > min(mate_min, opp_min)
    ):
        return decide_off_ball_formation_only(wm)

    if (
        profile.kickoff_counterpress
        and unum in (9, 10, 11)
        and kickoff_counterpress_active(wm, profile=profile)
    ):
        if (
            unum == kickoff_counterpress_chaser_unum(ball)
            and self_min <= opp_min + 4
            and self_min <= mate_min + 4
        ):
            return Action(
                body=Body_BhvMove(),
                neck=None,
                label="bhv_move_intercept",
                decision_target=wm.ball().inertia_point(self_min),
            )
        target = kickoff_counterpress_target(unum, ball, sp)
        return Action(
            body=Body_BhvMove(),
            neck=None,
            label="kickoff_counterpress",
            decision_target=target,
        )

    if (
        profile.frontline_recovery_screen
        and unum in (9, 10, 11)
        and self_min > 2
        and frontline_recovery_screen_active(wm, profile=profile)
    ):
        target = frontline_recovery_screen_target(unum, ball, sp)
        return Action(
            body=Body_BhvMove(),
            neck=None,
            label="frontline_recovery_screen",
            decision_target=target,
        )

    entry_stopper_target = kickoff_central_entry_stopper_target(wm, profile=profile)
    if entry_stopper_target is not None:
        return Action(
            body=Body_BhvBlock(),
            neck=None,
            label="kickoff_central_entry_stopper",
            decision_target=entry_stopper_target.copy(),
            block_target=entry_stopper_target,
        )

    central_anchor_target = kickoff_central_channel_anchor_target(wm, profile=profile)
    if central_anchor_target is not None:
        return Action(
            body=Body_BhvBlock(),
            neck=None,
            label="kickoff_central_channel_anchor",
            decision_target=central_anchor_target.copy(),
            block_target=central_anchor_target,
        )

    second_line_target = kickoff_central_second_line_screen_target(wm, profile=profile)
    if second_line_target is not None:
        return Action(
            body=Body_BhvMove(),
            neck=None,
            label="kickoff_central_second_line_screen",
            decision_target=second_line_target,
        )

    flank_post_target = kickoff_flank_goalpost_guard_target(wm, profile=profile)
    if flank_post_target is not None:
        return Action(
            body=Body_BhvBlock(),
            neck=None,
            label="kickoff_flank_goalpost_guard",
            decision_target=flank_post_target.copy(),
            block_target=flank_post_target,
        )

    flank_shelf_target = kickoff_flank_backline_shelf_target(wm, profile=profile)
    if flank_shelf_target is not None:
        return Action(
            body=Body_BhvMove(),
            neck=None,
            label="kickoff_flank_backline_shelf",
            decision_target=flank_shelf_target,
        )

    lane_lock_target = kickoff_lane_lockdown_target(wm, profile=profile)
    if lane_lock_target is not None:
        return Action(
            body=Body_BhvMove(),
            neck=None,
            label="kickoff_lane_lockdown",
            decision_target=lane_lock_target,
        )

    cutback_target = find_flank_cutback_guard_target(wm, profile=profile, owner_unum=owner_unum)
    if cutback_target is not None:
        return Action(
            body=Body_BhvBlock(),
            neck=None,
            label="flank_cutback_guard",
            decision_target=cutback_target.copy(),
            block_target=cutback_target,
        )

    restart_lock_target = flank_restart_goalmouth_lock_target(wm, profile=profile, owner_unum=owner_unum)
    if restart_lock_target is not None:
        return Action(
            body=Body_BhvBlock(),
            neck=None,
            label="flank_restart_goalmouth_lock",
            decision_target=restart_lock_target.copy(),
            block_target=restart_lock_target,
        )

    if should_hold_box_entry_owner_lock(wm, profile=profile, owner_unum=owner_unum):
        block_target = find_goalmouth_lane_block_target(wm, profile=profile, owner_unum=owner_unum)
        if block_target is not None:
            return Action(
                body=Body_BhvBlock(),
                neck=None,
                label="box_entry_lane_block",
                decision_target=block_target.copy(),
                block_target=block_target,
            )
        return decide_off_ball_formation_only(wm)

    if (
        not wm.exist_kickable_teammates()
        and (
            urgent_defense
            or
            self_min <= 3
            or (self_min <= mate_min and self_min < opp_min + 3)
            or (ball_near_sideline and self_min <= mate_min + 1)
            or (flank_lock_alert and self_min <= mate_min + 2 and self_min <= opp_min + 3)
        )
    ):
        return Action(
            body=Body_BhvMove(),
            neck=None,
            label="bhv_move_intercept",
            decision_target=wm.ball().inertia_point(self_min),
        )

    if opp_min < mate_min:
        block_target = flank_restart_goalmouth_lock_target(wm, profile=profile, owner_unum=owner_unum)
        block_label = "flank_restart_goalmouth_lock" if block_target is not None else ""
        if block_target is None:
            block_target = find_goalmouth_lane_block_target(wm, profile=profile, owner_unum=owner_unum)
            block_label = "goalmouth_lane_block" if block_target is not None else "bhv_block"
        if block_target is None:
            block_target = find_block_target(wm)
        if block_target is None and flank_lock_alert:
            block_target = flank_lock_block_target(wm)
        return Action(
            body=Body_BhvBlock(),
            neck=None,
            label=block_label,
            decision_target=block_target.copy() if block_target is not None else None,
            block_target=block_target,
        )

    return Action(
        body=Body_BhvMove(),
        neck=None,
        label="bhv_move",
        decision_target=StrategyFormation.i().get_pos(wm.self().unum()).copy(),
    )


def weak_team_press_intercept_action(wm: "WorldModel", profile=None) -> Action | None:
    if profile is None:
        profile = get_experiment_profile()
    if not weak_team_press_intercept_active(wm, profile=profile):
        return None
    if wm.game_mode().type() != GameModeType.PlayOn:
        return None
    if not wm.ball().pos_valid() or wm.exist_kickable_teammates():
        return None

    unum = world_self_unum(wm)
    if unum not in (9, 10, 11):
        return None

    ball = wm.ball().pos()
    if ball.x() < -8.0 or ball.x() > 44.0:
        return None
    if abs(ball.y()) > ServerParam.i().pitch_half_width() - 1.0:
        return None

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    if self_min > 8:
        return None
    if self_min > mate_min + 1:
        return None
    if self_min > opp_min + 4:
        return None

    return Action(
        body=Body_BhvMove(),
        neck=None,
        label="weak_team_press_intercept",
        decision_target=wm.ball().inertia_point(self_min),
    )


def weak_team_frontline_slot_target(wm: "WorldModel", profile=None) -> Vector2D | None:
    if profile is None:
        profile = get_experiment_profile()
    if not weak_team_frontline_slots_active(wm, profile=profile):
        return None
    if wm.game_mode().type() != GameModeType.PlayOn:
        return None
    if not wm.ball().pos_valid():
        return None

    unum = world_self_unum(wm)
    if unum not in (9, 10, 11):
        return None

    ball = wm.ball().pos()
    if ball.x() < -12.0:
        return None

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    if self_min <= mate_min + 1:
        return None

    return weak_team_frontline_slot_for_unum(unum, ball)


def weak_team_frontline_slot_for_unum(unum: int, ball: Vector2D) -> Vector2D:
    base_y = -11.0 if unum == 9 else 0.0 if unum == 10 else 11.0
    if abs(ball.y()) > 12.0:
        base_y += clamp((ball.y() - base_y) * 0.25, -5.0, 5.0)

    if unum == 10:
        x = 35.0 if ball.x() > 6.0 else 32.0
    else:
        x = 33.0 if ball.x() > 6.0 else 30.0
    if ball.x() > 20.0:
        x = min(x + 4.0, 40.0)

    return clamp_to_field(Vector2D(x, clamp(base_y, -16.0, 16.0)), margin_x=8.0, margin_y=3.0)


def weak_team_attack_press_target(wm: "WorldModel", profile=None) -> Vector2D | None:
    if profile is None:
        profile = get_experiment_profile()
    if not weak_team_pressure_active(wm, profile=profile):
        return None
    if wm.game_mode().type() != GameModeType.PlayOn:
        return None
    if not wm.ball().pos_valid():
        return None

    unum = world_self_unum(wm)
    overdrive = weak_team_overdrive_active(wm, profile=profile)
    press_only = weak_team_press_only_active(wm, profile=profile)
    attack_unums = (6, 7, 8, 9, 10, 11) if overdrive or press_only else (6, 7, 8)
    if unum not in attack_unums:
        return None

    frontline_slot = weak_team_frontline_slot_target(wm, profile=profile)
    if frontline_slot is not None:
        return frontline_slot

    ball = wm.ball().pos()
    min_ball_x = -12.0 if press_only else -18.0 if overdrive else -10.0
    if ball.x() <= min_ball_x:
        return None

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    if not overdrive and not press_only and self_min <= mate_min + 3:
        return None
    if press_only and unum in (6, 7, 8) and self_min <= mate_min + 1:
        return None

    target = shifted_formation_position(wm)
    if overdrive and unum in (9, 10, 11):
        x_boost = 22.0
        x_cap = 46.0
    elif press_only and unum in (9, 10, 11):
        x_boost = 16.0
        x_cap = 43.0
    elif overdrive:
        x_boost = 18.0
        x_cap = 42.0
    elif press_only:
        x_boost = 12.0
        x_cap = 34.0
    else:
        x_boost = 15.0
        x_cap = 35.0
    target._x = min(target.x() + x_boost, x_cap)
    if ball.x() > 10.0 and not press_only:
        target._x = min(target.x() + 7.0, x_cap)
    y_pull = 0.45 if press_only else 0.50 if overdrive else 0.35
    y_limit = 7.0 if press_only else 8.0 if overdrive else 6.0
    target._y += clamp((ball.y() - target.y()) * y_pull, -y_limit, y_limit)
    return clamp_to_field(target, margin_x=3.0, margin_y=1.5)


def decide_off_ball_formation_only(wm: "WorldModel") -> Action:
    sp = ServerParam.i()
    target = shifted_formation_position(wm)
    return Action(
        body=Body_GoToPoint(target, 1.0, sp.max_dash_power()),
        neck=Neck_TurnToBall(),
        label="move_to_formation",
        decision_target=target,
    )


def _should_tackle(wm: "WorldModel") -> bool:
    from pyrusgeom.line_2d import Line2D
    from pyrusgeom.ray_2d import Ray2D
    from lib.rcsc.types import Card

    sp = ServerParam.i()
    profile = get_experiment_profile()
    tackle_prob = wm.self().tackle_probability()

    if (
        wm.self().card() == Card.NO_CARD
        and (
            wm.ball().pos().x() > sp.our_penalty_area_line_x() + 0.5
            or wm.ball().pos().abs_y() > sp.penalty_area_half_width() + 0.5
        )
        and tackle_prob < wm.self().foul_probability()
    ):
        tackle_prob = wm.self().foul_probability()

    if tackle_prob < 0.8:
        return False

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    self_reach_point = wm.ball().inertia_point(self_min)
    screen_active = setplay_screen_active(profile, wm.ball().pos(), self_min, mate_min, opp_min)

    self_goal = False
    if self_reach_point.x() < -sp.pitch_half_length():
        ball_ray = Ray2D(wm.ball().pos(), wm.ball().vel().th())
        goal_line = Line2D(Vector2D(-sp.pitch_half_length(), 10.0), Vector2D(-sp.pitch_half_length(), -10.0))
        intersect = ball_ray.intersection(goal_line)
        if intersect and intersect.is_valid() and intersect.abs_y() < sp.goal_half_width() + 1.0:
            self_goal = True

    if not self_goal and (profile.setplay_shield or profile.box_clear):
        in_our_box = (
            wm.ball().pos().x() < sp.our_penalty_area_line_x() + 8.0
            and abs(wm.ball().pos().y()) < sp.penalty_area_half_width() + 6.0
        )
        deep_defense = wm.ball().pos().x() < -18.0 or wm.self().pos().x() < -20.0
        if in_our_box or deep_defense:
            return False
    if not self_goal and screen_active and wm.self().pos().x() < -10.0:
        return False

    return bool(
        wm.kickable_opponent()
        or self_goal
        or (opp_min < self_min - 3 and opp_min < mate_min - 3)
        or (
            self_min >= 5
            and wm.ball().pos().dist2(sp.their_team_goal_pos()) < 10**2
            and ((sp.their_team_goal_pos() - wm.self().pos()).th() - wm.self().body()).abs() < 45.0
        )
    )


def shoot_action(wm: "WorldModel") -> Action:
    sp = ServerParam.i()
    target = Vector2D(sp.pitch_half_length(), 0.0)
    return Action(
        body=Body_SmartKick(target, sp.ball_speed_max(), sp.ball_speed_max() - 0.4, 3),
        neck=Neck_TurnToBall(),
        label="shoot",
        decision_target=target,
    )


def pass_action(wm: "WorldModel", teammate: "PlayerObject", aggressive: bool = False) -> Action:
    start_speed = clamp(wm.self().pos().dist(teammate.pos()) * 0.18 + 1.0, 1.2, 2.7)
    if aggressive:
        start_speed = clamp(start_speed + 0.35, 1.4, 3.0)
    return Action(
        body=Body_KickOneStep(teammate.pos(), start_speed),
        neck=Neck_TurnToBall(),
        label=f"{'direct_' if aggressive else ''}pass_{teammate.unum()}",
        decision_target=teammate.pos().copy(),
    )


def dribble_action(wm: "WorldModel", advance: float | None = None) -> Action:
    goal_target = choose_dribble_target(wm)
    if advance is None:
        advance = 6.0 if transition_attack_enabled(wm) and wm.self().pos().x() > -5.0 else 4.0
    return Action(
        body=Body_Dribble(goal_target, advance=advance),
        neck=Neck_TurnToBall(),
        label="dribble",
        decision_target=goal_target,
    )


def in_shooting_range(wm: "WorldModel") -> bool:
    sp = ServerParam.i()
    goal_center = Vector2D(sp.pitch_half_length(), 0.0)
    goal_vector = goal_center - wm.self().pos()
    goal_distance = goal_vector.r()
    goal_angle = (goal_vector.th() - wm.self().body()).abs()
    if weak_team_killer_active(wm):
        return goal_distance < 40.0 and goal_angle < 70.0
    attack_unlocked = transition_attack_enabled(wm) or finish_attack_enabled(wm)
    max_distance = 24.0 if attack_unlocked else 20.0
    max_angle = 38.0 if attack_unlocked else 30.0
    return goal_distance < max_distance and goal_angle < max_angle


def find_best_pass_target(wm: "WorldModel"):
    profile = get_experiment_profile()
    attack_unlocked = transition_attack_enabled(wm)
    me = wm.self()
    candidates: list[tuple[float, "PlayerObject"]] = []
    under_pressure = (
        wm.exist_kickable_opponents()
        or wm.intercept_table().opponent_reach_cycle() <= 2
        or nearest_valid_opponent_distance(wm, me.pos()) < 6.0
    )
    allow_reset_pass = under_pressure or me.pos().x() < -5.0
    if (profile.setplay_shield or profile.box_clear) and me.pos().x() < -25.0:
        allow_reset_pass = False

    for teammate in wm.teammates():
        if teammate is None:
            continue
        if teammate.unum() <= 0 or teammate.pos_count() > 8 or teammate.is_ghost():
            continue
        if teammate.goalie():
            continue
        if attack_unlocked and me.pos().x() > -5.0 and teammate.pos().x() < me.pos().x() - 2.0:
            continue
        if teammate.pos().x() < me.pos().x() - 10.0 and not allow_reset_pass:
            continue
        if me.pos().x() < -25.0 and teammate.pos().x() < me.pos().x() - 4.0:
            continue
        if (profile.setplay_shield or profile.box_clear) and me.pos().x() < -25.0 and teammate.pos().x() < me.pos().x() + 2.0:
            continue
        lane_margin = pass_lane_margin(wm, me.pos(), teammate.pos())
        if not pass_lane_clear(wm, teammate, lane_margin=lane_margin):
            continue
        if not receiver_goal_lane_clear(wm, teammate):
            continue
        receiver_space = nearest_valid_opponent_distance(wm, teammate.pos())
        if receiver_space < 3.0:
            continue

        progress = teammate.pos().x() - me.pos().x()
        score = (
            progress * 2.2
            + lane_margin * 1.5
            + receiver_space
            - abs(teammate.pos().y()) * 0.08
        )
        if attack_unlocked:
            score += max(progress, 0.0) * 1.4
            score += max(teammate.pos().x(), 0.0) * 0.08
            score -= abs(teammate.pos().y()) * 0.03
        if profile.setplay_shield or profile.box_clear:
            if teammate.pos().x() < me.pos().x():
                score -= 8.0
            if me.pos().x() < -20.0 and abs(teammate.pos().y()) < 8.0:
                score -= 1.5
        if teammate.pos().x() > me.pos().x():
            score += 3.0
        if allow_reset_pass and teammate.pos().x() < me.pos().x():
            score += min(receiver_space, 4.0)

        candidates.append((score, teammate))

    if not candidates:
        return None

    return max(candidates, key=lambda item: item[0])[1]

def pass_lane_clear(wm: "WorldModel", teammate: "PlayerObject", lane_margin: float | None = None) -> bool:
    profile = get_experiment_profile()
    attack_unlocked = transition_attack_enabled(wm)
    start = wm.self().pos()
    end = teammate.pos()
    margin = pass_lane_margin(wm, start, end) if lane_margin is None else lane_margin
    threshold = 3.0
    if start.x() < -15.0:
        threshold = 3.5
    if end.x() < start.x():
        threshold += 0.5
    if (profile.setplay_shield or profile.box_clear) and start.x() < -20.0:
        threshold += 0.4
        if end.x() <= start.x():
            threshold += 0.8
    if attack_unlocked and end.x() > start.x():
        threshold -= 0.4
    return margin >= threshold


def receiver_goal_lane_clear(wm: "WorldModel", teammate: "PlayerObject") -> bool:
    sp = ServerParam.i()
    teammate_pos = teammate.pos()
    goal_pos = Vector2D(sp.pitch_half_length(), 0.0)

    for opponent in wm.opponents():
        if opponent is None or opponent.unum() <= 0 or opponent.pos_count() > 8 or opponent.is_ghost():
            continue

        if point_to_segment_distance(opponent.pos(), teammate_pos, goal_pos) < 3.0:
            return False

    return True


def pass_lane_margin(wm: "WorldModel", start: Vector2D, end: Vector2D) -> float:
    min_margin = float("inf")

    for opponent in wm.opponents():
        if opponent is None or opponent.unum() <= 0 or opponent.pos_count() > 8 or opponent.is_ghost():
            continue
        min_margin = min(min_margin, point_to_segment_distance(opponent.pos(), start, end))

    return min_margin if min_margin != float("inf") else 99.0


def nearest_valid_opponent_distance(wm: "WorldModel", point: Vector2D) -> float:
    min_dist = float("inf")

    for opponent in wm.opponents():
        if opponent is None or opponent.unum() <= 0 or opponent.pos_count() > 8 or opponent.is_ghost():
            continue
        min_dist = min(min_dist, opponent.pos().dist(point))

    return min_dist if min_dist != float("inf") else 99.0


def world_self_unum(wm: "WorldModel") -> int:
    try:
        return wm.self_unum()
    except AttributeError:
        return wm.self().unum()


def our_field_player(wm: "WorldModel", unum: int):
    if unum == wm.self().unum():
        return wm.self()
    try:
        return wm.our_player(unum)
    except AttributeError:
        return None


def is_valid_defensive_field_player(player) -> bool:
    if player is None:
        return False
    try:
        unum = player.unum()
    except AttributeError:
        return False
    if unum not in DEFENSIVE_FIELD_UNUMS:
        return False
    if getattr(player, "goalie", lambda: False)():
        return False
    if getattr(player, "is_ghost", lambda: False)():
        return False
    if getattr(player, "pos_count", lambda: 0)() > 8:
        return False
    return True


def in_our_box_entry_zone(ball: Vector2D, sp: "ServerParam") -> bool:
    return (
        ball.x() < sp.our_penalty_area_line_x() + 8.0
        and abs(ball.y()) < sp.penalty_area_half_width() + 7.0
    )


def select_box_entry_owner_unum(wm: "WorldModel") -> int | None:
    sp = ServerParam.i()
    ball = wm.ball().pos()
    if not in_our_box_entry_zone(ball, sp):
        return None

    reach_cycle = min(
        wm.intercept_table().self_reach_cycle(),
        wm.intercept_table().teammate_reach_cycle(),
        wm.intercept_table().opponent_reach_cycle(),
    )
    ball_point = wm.ball().inertia_point(max(0, min(reach_cycle, 6)))
    best_unum = None
    best_score = float("inf")

    for unum in DEFENSIVE_FIELD_UNUMS:
        player = our_field_player(wm, unum)
        if not is_valid_defensive_field_player(player):
            continue

        score = player.pos().dist(ball_point)
        if unum in (6, 7, 8):
            score += 0.6
        if player.pos().x() > ball_point.x() + 4.0:
            score += 0.8

        if score < best_score:
            best_score = score
            best_unum = unum

    return best_unum


def should_hold_box_entry_owner_lock(wm: "WorldModel", profile=None, owner_unum: int | None = None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.box_entry_owner_lock:
        return False
    unum = world_self_unum(wm)
    if unum not in DEFENSIVE_FIELD_UNUMS:
        return False
    if owner_unum is None:
        owner_unum = select_box_entry_owner_unum(wm)
    return owner_unum is not None and owner_unum != unum


def kickoff_terminal_guard_active(wm: "WorldModel", profile=None, window: int = 260) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.kickoff_terminal_guard:
        return False

    if wm.game_mode().type() != GameModeType.PlayOn:
        return False
    if not wm.ball().pos_valid():
        return False
    if not recent_our_kickoff_context(wm, profile=profile, window=window):
        return False

    ball = wm.ball().pos()
    sp = ServerParam.i()
    if ball.x() < sp.our_penalty_area_line_x() + 10.0 and abs(ball.y()) < sp.penalty_area_half_width() + 10.0:
        return True
    return ball.x() < -26.0 and abs(ball.y()) < 18.0


def update_recent_opp_central_restart(wm: "WorldModel") -> None:
    global _RECENT_OPP_CENTRAL_RESTART_CYCLE
    cycle = wm.time().cycle()
    if cycle < _RECENT_OPP_CENTRAL_RESTART_CYCLE:
        _RECENT_OPP_CENTRAL_RESTART_CYCLE = -1000

    if not wm.ball().pos_valid():
        return
    gm = wm.game_mode()
    try:
        our_side = wm.our_side()
    except AttributeError:
        return
    if gm.side() == our_side:
        return
    if gm.type() not in (
        GameModeType.FreeKick_Left,
        GameModeType.FreeKick_Right,
        GameModeType.IndFreeKick_Left,
        GameModeType.IndFreeKick_Right,
        GameModeType.KickIn_Left,
        GameModeType.KickIn_Right,
    ):
        return

    ball = wm.ball().pos()
    if -40.0 <= ball.x() <= 2.0 and abs(ball.y()) <= 14.0:
        _RECENT_OPP_CENTRAL_RESTART_CYCLE = cycle


def update_recent_opp_flank_restart(wm: "WorldModel") -> None:
    global _RECENT_OPP_FLANK_RESTART_CYCLE
    cycle = wm.time().cycle()
    if cycle < _RECENT_OPP_FLANK_RESTART_CYCLE:
        _RECENT_OPP_FLANK_RESTART_CYCLE = -1000

    if not wm.ball().pos_valid():
        return
    gm = wm.game_mode()
    try:
        our_side = wm.our_side()
    except AttributeError:
        return
    if gm.side() == our_side:
        return
    if gm.type() not in (
        GameModeType.KickIn_Left,
        GameModeType.KickIn_Right,
        GameModeType.CornerKick_Left,
        GameModeType.CornerKick_Right,
        GameModeType.FreeKick_Left,
        GameModeType.FreeKick_Right,
        GameModeType.IndFreeKick_Left,
        GameModeType.IndFreeKick_Right,
    ):
        return

    ball = wm.ball().pos()
    if ball.x() <= 12.0 and abs(ball.y()) >= 12.0:
        _RECENT_OPP_FLANK_RESTART_CYCLE = cycle


def central_restart_terminal_guard_active(wm: "WorldModel", profile=None, window: int = 180) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.central_restart_terminal_guard:
        return False

    update_recent_our_kickoff(wm)
    update_recent_opp_central_restart(wm)
    if wm.game_mode().type() != GameModeType.PlayOn:
        return False
    if not wm.ball().pos_valid():
        return False

    cycle = wm.time().cycle()
    elapsed_kickoff = cycle - _RECENT_OUR_KICKOFF_CYCLE
    elapsed_restart = cycle - _RECENT_OPP_CENTRAL_RESTART_CYCLE
    if not (0 <= elapsed_kickoff <= window or 0 <= elapsed_restart <= window):
        return False

    ball = wm.ball().pos()
    sp = ServerParam.i()
    if not in_our_box_entry_zone(ball, sp):
        return False
    if abs(ball.y()) > 13.5:
        return False

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    return wm.exist_kickable_opponents() or opp_min <= min(self_min, mate_min) + 4


def narrow_kickoff_center_entry_clear_active(wm: "WorldModel", profile=None, window: int = 190) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.narrow_kickoff_center_entry_clear:
        return False

    update_recent_our_kickoff(wm)
    if wm.game_mode().type() != GameModeType.PlayOn:
        return False
    if not wm.ball().pos_valid():
        return False

    elapsed = wm.time().cycle() - _RECENT_OUR_KICKOFF_CYCLE
    if elapsed < 0 or elapsed > window:
        return False

    ball = wm.ball().pos()
    sp = ServerParam.i()
    if ball.x() < sp.our_penalty_area_line_x() - 2.0 or ball.x() > sp.our_penalty_area_line_x() + 9.0:
        return False
    if abs(ball.y()) > 9.0:
        return False

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    return wm.exist_kickable_opponents() or opp_min <= min(self_min, mate_min) + 3


def flank_restart_goalmouth_lock_active(wm: "WorldModel", profile=None, window: int = 240) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not (profile.flank_restart_goalmouth_lock or profile.opponent_flank_restart_goalmouth_lock):
        return False

    update_recent_our_kickoff(wm)
    update_recent_opp_flank_restart(wm)
    if wm.game_mode().type() != GameModeType.PlayOn:
        return False
    if wm.exist_kickable_teammates():
        return False
    if not wm.ball().pos_valid():
        return False

    ball = wm.ball().pos()
    sp = ServerParam.i()
    if ball.x() > sp.our_penalty_area_line_x() + 14.0 or ball.x() < -44.0:
        return False
    if abs(ball.y()) < 8.0 or abs(ball.y()) > sp.penalty_area_half_width() + 10.0:
        return False

    recent_our_kickoff = recent_our_kickoff_context(wm, profile=profile, window=window)
    elapsed_opp_flank = wm.time().cycle() - _RECENT_OPP_FLANK_RESTART_CYCLE
    recent_opp_flank = 0 <= elapsed_opp_flank <= window
    if profile.opponent_flank_restart_goalmouth_lock and not profile.flank_restart_goalmouth_lock:
        restart_leak = recent_opp_flank
    else:
        restart_leak = recent_our_kickoff or recent_opp_flank or recent_flank_restart_context(wm)
    if not restart_leak:
        return False

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    return ball.x() < sp.our_penalty_area_line_x() + 4.0 or wm.exist_kickable_opponents() or opp_min <= min(self_min, mate_min) + 4


def recent_flank_restart_context(wm: "WorldModel") -> bool:
    gm = wm.game_mode()
    if gm.type() != GameModeType.PlayOn:
        return False

    ball = wm.ball().pos()
    if abs(ball.y()) < 8.0:
        return False

    try:
        last_side = wm.last_kicker_side()
    except AttributeError:
        return False
    if last_side == wm.our_side():
        return False

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    return opp_min <= min(self_min, mate_min) + 4


def flank_restart_goalmouth_lock_target(
    wm: "WorldModel", profile=None, owner_unum: int | None = None
) -> Vector2D | None:
    if profile is None:
        profile = get_experiment_profile()
    if not flank_restart_goalmouth_lock_active(wm, profile=profile):
        return None

    self_unum = world_self_unum(wm)
    if self_unum not in DEFENSIVE_FIELD_UNUMS:
        return None
    if owner_unum is None:
        owner_unum = select_box_entry_owner_unum(wm)
    if owner_unum is None:
        owner_unum = select_flank_ball_owner_unum(wm)
    if owner_unum == self_unum:
        return None

    guard_unum, target = select_flank_restart_goalmouth_lock_assignment(wm, owner_unum=owner_unum)
    if guard_unum == self_unum and target is not None:
        return target.copy()
    return None


def select_flank_restart_goalmouth_lock_assignment(
    wm: "WorldModel", owner_unum: int | None = None
) -> tuple[int | None, Vector2D | None]:
    ball = wm.ball().pos()
    candidates = flank_restart_goalmouth_lock_candidates(ball, ServerParam.i())
    best_unum = None
    best_target = None
    best_score = float("inf")

    for unum in DEFENSIVE_FIELD_UNUMS:
        if owner_unum is not None and unum == owner_unum:
            continue
        player = our_field_player(wm, unum)
        if not is_valid_defensive_field_player(player):
            continue
        for target in candidates:
            score = player.pos().dist(target)
            if unum in (3, 4):
                score -= 1.1
            elif unum == 7:
                score -= 0.6
            elif unum in (6, 8):
                score += 0.7
            if player.pos().x() > ball.x() + 4.0:
                score += 1.2
            if abs(player.pos().y()) > abs(ball.y()) + 8.0:
                score += 1.0
            if score < best_score:
                best_score = score
                best_unum = unum
                best_target = target

    if best_score <= 24.0:
        return best_unum, best_target
    return None, None


def flank_restart_goalmouth_lock_candidates(ball: Vector2D, sp: "ServerParam") -> list[Vector2D]:
    sign = 1.0 if ball.y() >= 0.0 else -1.0
    goal_x = -sp.pitch_half_length() + 1.0
    near_post = Vector2D(goal_x, sign * sp.goal_half_width())
    center_post = Vector2D(goal_x, 0.0)
    cutback = Vector2D(sp.our_penalty_area_line_x() - 6.0, sign * 6.0)

    candidates = [
        interpolate_point(ball, near_post, 0.58),
        interpolate_point(ball, near_post, 0.72),
        interpolate_point(ball, center_post, 0.58),
        cutback,
    ]
    return [clamp_to_field(target, margin_x=1.5, margin_y=1.5) for target in candidates]


def find_goalmouth_lane_block_target(wm: "WorldModel", profile=None, owner_unum: int | None = None) -> Vector2D | None:
    if profile is None:
        profile = get_experiment_profile()
    if not (
        profile.goalmouth_lane_block
        or kickoff_terminal_guard_active(wm, profile=profile)
        or central_restart_terminal_guard_active(wm, profile=profile)
        or narrow_kickoff_center_entry_clear_active(wm, profile=profile)
    ):
        return None

    sp = ServerParam.i()
    ball = wm.ball().pos()
    if not in_our_box_entry_zone(ball, sp):
        return None

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    terminal_guard = central_restart_terminal_guard_active(wm, profile=profile)
    narrow_kickoff_center = narrow_kickoff_center_entry_clear_active(wm, profile=profile)
    pressure_margin = 4 if terminal_guard else 3 if narrow_kickoff_center else 2
    opponent_pressure = wm.exist_kickable_opponents() or opp_min <= min(self_min, mate_min) + pressure_margin
    if not opponent_pressure:
        return None

    self_unum = world_self_unum(wm)
    if self_unum not in DEFENSIVE_FIELD_UNUMS:
        return None
    if owner_unum is None:
        owner_unum = select_box_entry_owner_unum(wm)
    if owner_unum == self_unum:
        return None

    candidates = goalmouth_block_candidates(ball, sp)
    best_unum = None
    best_target = None
    best_score = float("inf")

    for unum in DEFENSIVE_FIELD_UNUMS:
        if unum == owner_unum:
            continue
        player = our_field_player(wm, unum)
        if not is_valid_defensive_field_player(player):
            continue
        for target in candidates:
            score = player.pos().dist(target)
            if unum in (6, 7, 8):
                score += 0.8
            if player.pos().x() > ball.x() + 2.0:
                score += 1.0
            if score < best_score:
                best_score = score
                best_unum = unum
                best_target = target

    if best_unum == self_unum and best_target is not None and best_score <= 18.0:
        return best_target.copy()
    return None


def goalmouth_block_candidates(ball: Vector2D, sp: "ServerParam") -> list[Vector2D]:
    goal_x = -sp.pitch_half_length() + 1.0
    near_post_y = sp.goal_half_width() if ball.y() >= 0.0 else -sp.goal_half_width()
    goal_points = [Vector2D(goal_x, near_post_y), Vector2D(goal_x, 0.0)]
    if abs(ball.y()) < 6.0:
        goal_points.append(Vector2D(goal_x, -near_post_y))

    candidates = []
    for goal_point in goal_points:
        target = interpolate_point(ball, goal_point, 0.45)
        candidates.append(clamp_to_field(target, margin_x=1.5, margin_y=1.5))
    return candidates


def flank_cutback_guard_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.flank_cutback_guard:
        return False
    if wm.game_mode().type() != GameModeType.PlayOn:
        return False
    if not wm.ball().pos_valid():
        return False
    if wm.exist_kickable_teammates():
        return False

    sp = ServerParam.i()
    ball = wm.ball().pos()
    if ball.x() > sp.our_penalty_area_line_x() + 12.0:
        return False
    if abs(ball.y()) < 12.0 or abs(ball.y()) > sp.pitch_half_width() - 2.0:
        return False
    if abs(ball.y()) > sp.penalty_area_half_width() + 9.0:
        return False

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    opponent_pressure = wm.exist_kickable_opponents() or opp_min <= min(self_min, mate_min) + 3
    return opponent_pressure or ball.x() < sp.our_penalty_area_line_x() + 2.0


def flank_cutback_guard_base_target(ball: Vector2D, sp: "ServerParam") -> Vector2D:
    sign = 1.0 if ball.y() >= 0.0 else -1.0
    target_x = clamp(ball.x() - 6.0, sp.our_penalty_area_line_x() - 7.0, sp.our_penalty_area_line_x() + 1.0)
    target_y = sign * clamp(abs(ball.y()) * 0.45, 7.0, 12.0)
    return clamp_to_field(Vector2D(target_x, target_y), margin_x=3.0, margin_y=1.5)


def select_flank_ball_owner_unum(wm: "WorldModel") -> int | None:
    reach_cycle = min(
        wm.intercept_table().self_reach_cycle(),
        wm.intercept_table().teammate_reach_cycle(),
        wm.intercept_table().opponent_reach_cycle(),
    )
    ball_point = wm.ball().inertia_point(max(0, min(reach_cycle, 6)))
    best_unum = None
    best_score = float("inf")

    for unum in DEFENSIVE_FIELD_UNUMS:
        player = our_field_player(wm, unum)
        if not is_valid_defensive_field_player(player):
            continue
        score = player.pos().dist(ball_point)
        if unum in (6, 7, 8):
            score += 0.4
        if score < best_score:
            best_score = score
            best_unum = unum

    if best_score <= 14.0:
        return best_unum
    return None


def select_flank_cutback_guard_unum(wm: "WorldModel", owner_unum: int | None = None) -> int | None:
    sp = ServerParam.i()
    ball = wm.ball().pos()
    target = flank_cutback_guard_base_target(ball, sp)
    best_unum = None
    best_score = float("inf")

    for unum in DEFENSIVE_FIELD_UNUMS:
        if owner_unum is not None and unum == owner_unum:
            continue
        player = our_field_player(wm, unum)
        if not is_valid_defensive_field_player(player):
            continue

        score = player.pos().dist(target)
        if unum in (6, 7, 8):
            score -= 0.8
        if player.pos().x() > ball.x() + 6.0:
            score += 1.2
        if abs(player.pos().y()) > abs(ball.y()) + 6.0:
            score += 1.0
        if score < best_score:
            best_score = score
            best_unum = unum

    if best_score <= 22.0:
        return best_unum
    return None


def find_flank_cutback_guard_target(wm: "WorldModel", profile=None, owner_unum: int | None = None) -> Vector2D | None:
    if profile is None:
        profile = get_experiment_profile()
    if not flank_cutback_guard_active(wm, profile=profile):
        return None

    self_unum = world_self_unum(wm)
    if self_unum not in DEFENSIVE_FIELD_UNUMS:
        return None
    if owner_unum is None:
        owner_unum = select_box_entry_owner_unum(wm)
    if owner_unum is None:
        owner_unum = select_flank_ball_owner_unum(wm)
    if owner_unum == self_unum:
        return None

    guard_unum = select_flank_cutback_guard_unum(wm, owner_unum=owner_unum)
    if guard_unum != self_unum:
        return None
    return flank_cutback_guard_base_target(wm.ball().pos(), ServerParam.i())


def interpolate_point(start: Vector2D, end: Vector2D, ratio: float) -> Vector2D:
    return Vector2D(
        start.x() + (end.x() - start.x()) * ratio,
        start.y() + (end.y() - start.y()) * ratio,
    )


def find_block_target(wm: "WorldModel") -> Vector2D | None:
    from base.tools import Tools

    opp_min = wm.intercept_table().opponent_reach_cycle()
    ball_pos = wm.ball().inertia_point(opp_min)
    dribble_speed_estimate = 0.7
    dribble_angle_estimate = (Vector2D(-52.0, 0) - ball_pos).th()
    blocker = 0
    block_cycle = 1000
    block_pos = None

    for unum in range(1, 12):
        tm = wm.our_player(unum)
        if tm is None:
            continue
        if tm.unum() < 1:
            continue
        for c in range(1, 40):
            dribble_pos = ball_pos + Vector2D.polar2vector(c * dribble_speed_estimate, dribble_angle_estimate)
            turn_cycle = Tools.predict_player_turn_cycle(
                tm.player_type(),
                tm.body(),
                tm.vel().r(),
                tm.pos().dist(dribble_pos),
                (dribble_pos - tm.pos()).th(),
                0.2,
                False,
            )
            tm_cycle = tm.player_type().cycles_to_reach_distance(tm.inertia_point(opp_min).dist(dribble_pos)) + turn_cycle
            if tm_cycle <= opp_min + c:
                if tm_cycle < block_cycle:
                    block_cycle = tm_cycle
                    blocker = unum
                    block_pos = dribble_pos
                break

    if blocker == wm.self_unum() and block_pos is not None:
        return block_pos.copy()
    return None


def flank_lock_block_target(wm: "WorldModel") -> Vector2D:
    sp = ServerParam.i()
    ball = wm.ball().pos()
    sign = 1.0 if ball.y() >= 0.0 else -1.0
    return clamp_to_field(
        Vector2D(ball.x() - 4.0, sign * max(14.0, abs(ball.y()) - 4.0)),
        margin_x=3.0,
        margin_y=1.5,
    )


def setplay_screen_active(profile, ball: Vector2D, self_min: int, mate_min: int, opp_min: int) -> bool:
    if not profile.setplay_shield:
        return False
    if ball.x() > -8.0:
        return False
    our_min = min(self_min, mate_min)
    return opp_min <= our_min + 1


def setplay_screen_retreat_bonus(unum: int, screen_active: bool, ball_x: float) -> float:
    if not screen_active:
        return 0.0
    if unum in (2, 3, 4, 5):
        return 1.4 if ball_x < -18.0 else 0.9
    if unum in (6, 7, 8):
        return 0.9 if ball_x < -18.0 else 0.6
    return 0.0


def setplay_screen_cover_bias_bonus(unum: int, screen_active: bool) -> float:
    if not screen_active:
        return 0.0
    if unum in (2, 3, 4, 5):
        return 0.08
    if unum in (6, 7, 8):
        return 0.05
    return 0.0



def disciplined_screen_active(profile, ball: Vector2D, self_min: int, mate_min: int, opp_min: int) -> bool:
    if not (profile.setplay_shield and profile.box_clear and profile.flank_lock):
        return False
    if ball.x() > 2.0:
        return False
    return opp_min <= min(self_min, mate_min) + 2


def disciplined_screen_retreat_bonus(unum: int, screen_active: bool, ball_x: float) -> float:
    if not screen_active:
        return 0.0
    if unum in (2, 3, 4, 5):
        return 1.8 if ball_x < -8.0 else 1.2
    if unum in (6, 7, 8):
        return 1.1 if ball_x < -8.0 else 0.7
    return 0.0


def disciplined_screen_cover_bias_bonus(unum: int, screen_active: bool) -> float:
    if not screen_active:
        return 0.0
    if unum in (2, 3, 4, 5):
        return 0.10
    if unum in (6, 7, 8):
        return 0.07
    return 0.0



def opponent_key_or_name(wm: "WorldModel") -> str:
    return (os.environ.get("ROBOCUP_OPPONENT_KEY") or wm.their_team_name() or "").lower()


def cyrus_like_opponent(wm: "WorldModel") -> bool:
    name = opponent_key_or_name(wm)
    return "cyrus" in name and "foxsy" not in name


def foxsy_cyrus_opponent(wm: "WorldModel") -> bool:
    name = opponent_key_or_name(wm)
    return "foxsy" in name and "cyrus" in name


def weak_team_opponent(wm: "WorldModel") -> bool:
    name = opponent_key_or_name(wm)
    return "starter" in name or "foxsy" in name


def weak_team_killer_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    return profile.weak_team_killer and weak_team_opponent(wm)


def weak_team_overdrive_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    return profile.weak_team_overdrive and weak_team_opponent(wm)


def weak_team_press_only_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    return profile.weak_team_press_only and weak_team_opponent(wm)


def weak_team_press_intercept_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    return profile.weak_team_press_intercept and weak_team_opponent(wm)


def weak_team_channel_entry_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    return profile.weak_team_channel_entry and weak_team_opponent(wm)


def weak_team_restart_channel_entry_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    return profile.weak_team_restart_channel_entry and weak_team_opponent(wm)


def weak_team_frontline_slots_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    return profile.weak_team_frontline_slots and weak_team_opponent(wm)


def weak_team_front_third_finish_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    return profile.weak_team_front_third_finish and weak_team_opponent(wm)


def weak_team_frontline_post_finish_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    return profile.weak_team_frontline_post_finish and weak_team_opponent(wm)


def weak_team_natural_channel_feed_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    return profile.weak_team_natural_channel_feed and weak_team_opponent(wm)


def weak_team_deep_cutback_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    return profile.weak_team_deep_cutback and weak_team_opponent(wm)


def weak_team_restart_grounder_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.weak_team_restart_grounder or not weak_team_opponent(wm):
        return False
    if wm.self().goalie() or not wm.self().is_kickable():
        return False
    game_mode = wm.game_mode()
    return game_mode.side() == wm.our_side() and (
        game_mode.type().is_kick_off() or game_mode.type().is_corner_kick()
    )


def weak_team_restart_second_finish_active(wm: "WorldModel", profile=None, window: int = 170) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.weak_team_restart_second_finish or not weak_team_opponent(wm):
        return False
    update_recent_our_kickoff(wm)
    elapsed = wm.time().cycle() - _RECENT_OUR_KICKOFF_CYCLE
    return 0 <= elapsed <= window


def weak_team_natural_high_frontline_finish_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    return profile.weak_team_natural_high_frontline_finish and weak_team_opponent(wm)


def weak_team_pressure_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    return (profile.weak_team_killer or profile.weak_team_press_only) and weak_team_opponent(wm)


def update_recent_our_kickoff(wm: "WorldModel") -> None:
    global _RECENT_OUR_KICKOFF_CYCLE
    global _RECENT_NON_KICKOFF_RESTART_CYCLE
    cycle = wm.time().cycle()
    if cycle < _RECENT_OUR_KICKOFF_CYCLE:
        _RECENT_OUR_KICKOFF_CYCLE = -1000
    if cycle < _RECENT_NON_KICKOFF_RESTART_CYCLE:
        _RECENT_NON_KICKOFF_RESTART_CYCLE = -1000

    gm = wm.game_mode()
    gm_type = gm.type()
    if gm_type.is_kick_off() and gm.side() == wm.our_side():
        _RECENT_OUR_KICKOFF_CYCLE = cycle
        return

    if gm_type != GameModeType.PlayOn and not gm_type.is_kick_off():
        _RECENT_NON_KICKOFF_RESTART_CYCLE = cycle


def recent_our_kickoff_context(wm: "WorldModel", profile=None, window: int = 220) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    update_recent_our_kickoff(wm)

    elapsed = wm.time().cycle() - _RECENT_OUR_KICKOFF_CYCLE
    if elapsed < 0 or elapsed > window:
        return False
    if not profile.strict_kickoff_context:
        return True
    return _RECENT_NON_KICKOFF_RESTART_CYCLE < _RECENT_OUR_KICKOFF_CYCLE


def post_our_kickoff_recovery_active(wm: "WorldModel", profile=None, window: int = 120) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.post_kickoff_recovery_screen:
        return False
    if profile.starter2d_only_post_kickoff_recovery_screen and opponent_key_or_name(wm) != "starter2d":
        return False

    update_recent_our_kickoff(wm)
    if wm.game_mode().type() != GameModeType.PlayOn:
        return False

    elapsed = wm.time().cycle() - _RECENT_OUR_KICKOFF_CYCLE
    return 0 <= elapsed <= window and wm.ball().pos().x() < 15.0


def post_our_kickoff_midfield_plug_active(wm: "WorldModel", profile=None, window: int = 120) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.post_kickoff_midfield_plug:
        return False

    update_recent_our_kickoff(wm)
    if wm.game_mode().type() != GameModeType.PlayOn:
        return False

    ball = wm.ball().pos()
    elapsed = wm.time().cycle() - _RECENT_OUR_KICKOFF_CYCLE
    return 0 <= elapsed <= window and ball.x() < 15.0 and abs(ball.y()) < 20.0


def central_midfield_gap_plug_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.central_midfield_gap_plug:
        return False
    if wm.game_mode().type() != GameModeType.PlayOn:
        return False

    ball = wm.ball().pos()
    if ball.x() >= -8.0 or abs(ball.y()) >= 18.0:
        return False

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    return ball.x() < -18.0 or opp_min <= min(self_min, mate_min) + 3


def frontline_recovery_screen_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.frontline_recovery_screen:
        return False
    if wm.game_mode().type() != GameModeType.PlayOn:
        return False
    if wm.exist_kickable_teammates():
        return False

    ball = wm.ball().pos()
    if ball.x() > 12.0:
        return False

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    return ball.x() < -8.0 or opp_min <= min(self_min, mate_min) + 3


def frontline_recovery_screen_target(unum: int, ball: Vector2D, sp: "ServerParam") -> Vector2D:
    base_x = clamp(ball.x() * 0.45 - 18.0, -36.0, -16.0)
    if unum == 10:
        target = Vector2D(base_x - 2.0, clamp(ball.y() * 0.25, -6.0, 6.0))
    elif unum == 9:
        target_y = -18.0 if ball.y() < -12.0 else -10.0 if ball.y() > 12.0 else -14.0
        target = Vector2D(base_x + 1.0, target_y)
    elif unum == 11:
        target_y = 18.0 if ball.y() > 12.0 else 10.0 if ball.y() < -12.0 else 14.0
        target = Vector2D(base_x + 1.0, target_y)
    else:
        target = Vector2D(base_x, clamp(ball.y() * 0.25, -8.0, 8.0))
    return clamp_to_field(target, margin_x=3.0, margin_y=1.5)


def kickoff_counterpress_active(wm: "WorldModel", profile=None, window: int = 160) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.kickoff_counterpress:
        return False

    if wm.game_mode().type() != GameModeType.PlayOn:
        return False
    if wm.exist_kickable_teammates():
        return False
    if not wm.ball().pos_valid():
        return False
    if not recent_our_kickoff_context(wm, profile=profile, window=window):
        return False

    ball = wm.ball().pos()
    if ball.x() < -18.0 or ball.x() > 36.0:
        return False

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    return ball.x() > -6.0 or abs(ball.y()) > 12.0 or opp_min <= min(self_min, mate_min) + 4


def kickoff_counterpress_chaser_unum(ball: Vector2D) -> int:
    if ball.y() > 10.0:
        return 11
    if ball.y() < -10.0:
        return 9
    return 10


def kickoff_counterpress_target(unum: int, ball: Vector2D, sp: "ServerParam") -> Vector2D:
    sign = 1.0 if ball.y() >= 0.0 else -1.0
    if abs(ball.y()) >= 10.0:
        ball_side_unum = 11 if sign > 0.0 else 9
        if unum == ball_side_unum:
            target = Vector2D(
                clamp(ball.x() - 2.0, -8.0, 28.0),
                clamp(ball.y() - sign * 4.0, -28.0, 28.0),
            )
        elif unum == 10:
            target = Vector2D(
                clamp(ball.x() - 8.0, -14.0, 18.0),
                clamp(sign * 8.0, -10.0, 10.0),
            )
        else:
            target = Vector2D(
                clamp(ball.x() - 12.0, -18.0, 10.0),
                clamp(-sign * 4.0, -8.0, 8.0),
            )
    elif unum == 10:
        target = Vector2D(clamp(ball.x() - 3.0, -8.0, 24.0), clamp(ball.y(), -6.0, 6.0))
    elif unum == 9:
        target = Vector2D(clamp(ball.x() - 8.0, -14.0, 16.0), -12.0)
    elif unum == 11:
        target = Vector2D(clamp(ball.x() - 8.0, -14.0, 16.0), 12.0)
    else:
        target = Vector2D(clamp(ball.x() - 6.0, -12.0, 18.0), clamp(ball.y(), -8.0, 8.0))
    return clamp_to_field(target, margin_x=3.0, margin_y=1.5)


def kickoff_lane_lockdown_active(wm: "WorldModel", profile=None, window: int = 220) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.kickoff_lane_lockdown:
        return False

    if wm.game_mode().type() != GameModeType.PlayOn:
        return False
    if wm.exist_kickable_teammates():
        return False
    if not wm.ball().pos_valid():
        return False
    if not recent_our_kickoff_context(wm, profile=profile, window=window):
        return False

    ball = wm.ball().pos()
    if ball.x() > 24.0 or ball.x() < -44.0:
        return False
    return abs(ball.y()) > 9.0 or ball.x() < -6.0


def kickoff_central_channel_anchor_active(wm: "WorldModel", profile=None, window: int = 220) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.kickoff_central_channel_anchor:
        return False
    if profile.cyrus_like_kickoff_central_channel_anchor and not cyrus_like_opponent(wm):
        return False

    if wm.game_mode().type() != GameModeType.PlayOn:
        return False
    if wm.exist_kickable_teammates():
        return False
    if not wm.ball().pos_valid():
        return False
    if not recent_our_kickoff_context(wm, profile=profile, window=window):
        return False

    ball = wm.ball().pos()
    if ball.x() > 8.0 or ball.x() < -44.0 or abs(ball.y()) > 11.0:
        return False

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    return ball.x() < -8.0 or opp_min <= min(self_min, mate_min) + 3


def kickoff_central_channel_anchor_target(wm: "WorldModel", profile=None) -> Vector2D | None:
    if profile is None:
        profile = get_experiment_profile()
    if not kickoff_central_channel_anchor_active(wm, profile=profile):
        return None

    unum = world_self_unum(wm)
    if unum not in (3, 4, 7):
        return None

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    if self_min <= 3 or (self_min <= mate_min and self_min <= opp_min + 2):
        return None

    ball = wm.ball().pos()
    ball_x = clamp(ball.x(), -36.0, 6.0)
    target_x = clamp(ball_x - 14.0, -43.0, -28.0)
    target_y = clamp(ball.y() * 0.35, -4.0, 4.0)
    if unum == 3:
        target = Vector2D(target_x - 1.5, target_y - 4.0)
    elif unum == 4:
        target = Vector2D(target_x - 1.5, target_y + 4.0)
    else:
        target = Vector2D(clamp(ball_x - 10.0, -36.0, -24.0), target_y)
    return clamp_to_field(target, margin_x=3.0, margin_y=1.5)


def kickoff_central_second_line_screen_active(wm: "WorldModel", profile=None, window: int = 260) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.kickoff_central_second_line_screen:
        return False

    if wm.game_mode().type() != GameModeType.PlayOn:
        return False
    if wm.exist_kickable_teammates():
        return False
    if not wm.ball().pos_valid():
        return False
    if not recent_our_kickoff_context(wm, profile=profile, window=window):
        return False

    ball = wm.ball().pos()
    sp = ServerParam.i()
    if ball.x() < -44.0 or ball.x() > sp.our_penalty_area_line_x() + 12.0:
        return False
    if abs(ball.y()) > 11.0:
        return False

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    return ball.x() < -8.0 or opp_min <= min(self_min, mate_min) + 4


def kickoff_central_second_line_screen_target(wm: "WorldModel", profile=None) -> Vector2D | None:
    if profile is None:
        profile = get_experiment_profile()
    if not kickoff_central_second_line_screen_active(wm, profile=profile):
        return None

    unum = world_self_unum(wm)
    if unum not in (6, 7, 8):
        return None

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    if self_min <= 3 or (self_min <= mate_min and self_min <= opp_min + 2):
        return None

    ball = wm.ball().pos()
    sp = ServerParam.i()
    ball_x = clamp(ball.x(), -36.0, sp.our_penalty_area_line_x() + 8.0)
    screen_x = clamp(ball_x - 9.0, -37.5, -24.0)
    center_y = clamp(ball.y() * 0.35, -4.0, 4.0)
    if unum == 7:
        target = Vector2D(screen_x, center_y)
    elif unum == 6:
        target = Vector2D(screen_x - 1.5, clamp(center_y - 7.0, -12.0, -4.5))
    else:
        target = Vector2D(screen_x - 1.5, clamp(center_y + 7.0, 4.5, 12.0))
    return clamp_to_field(target, margin_x=3.0, margin_y=1.5)


def kickoff_central_entry_stopper_active(wm: "WorldModel", profile=None, window: int = 230) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.kickoff_central_entry_stopper:
        return False
    if profile.selective_kickoff_central_entry_stopper and not (
        foxsy_cyrus_opponent(wm) or opponent_key_or_name(wm) == "starter2d"
    ):
        return False

    if wm.game_mode().type() != GameModeType.PlayOn:
        return False
    if wm.exist_kickable_teammates():
        return False
    if not wm.ball().pos_valid():
        return False
    if not recent_our_kickoff_context(wm, profile=profile, window=window):
        return False

    ball = wm.ball().pos()
    sp = ServerParam.i()
    if ball.x() < sp.our_penalty_area_line_x() - 2.0:
        return False
    if ball.x() > sp.our_penalty_area_line_x() + 11.0:
        return False
    if abs(ball.y()) > 8.5:
        return False

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    return ball.x() < sp.our_penalty_area_line_x() + 6.0 or opp_min <= min(self_min, mate_min) + 4


def kickoff_central_entry_stopper_target(wm: "WorldModel", profile=None) -> Vector2D | None:
    if profile is None:
        profile = get_experiment_profile()
    if not kickoff_central_entry_stopper_active(wm, profile=profile):
        return None

    unum = world_self_unum(wm)
    if unum not in (3, 4):
        return None

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    if self_min <= 3 or (self_min <= mate_min and self_min <= opp_min + 2):
        return None

    ball = wm.ball().pos()
    sp = ServerParam.i()
    left_stop = Vector2D(sp.our_penalty_area_line_x() - 4.0, -3.5)
    right_stop = Vector2D(sp.our_penalty_area_line_x() - 4.0, 3.5)
    target = left_stop if unum == 3 else right_stop

    our_player = our_field_player(wm, unum)
    mate = our_field_player(wm, 4 if unum == 3 else 3)
    if is_valid_defensive_field_player(our_player) and is_valid_defensive_field_player(mate):
        own_score = our_player.pos().dist(target)
        mate_score = mate.pos().dist(target)
        if mate_score + 1.0 < own_score:
            return None

    if ball.y() < -2.0 and unum == 4:
        target = Vector2D(sp.our_penalty_area_line_x() - 5.0, 1.5)
    elif ball.y() > 2.0 and unum == 3:
        target = Vector2D(sp.our_penalty_area_line_x() - 5.0, -1.5)

    return clamp_to_field(target, margin_x=3.0, margin_y=1.5)


def kickoff_flank_goalpost_guard_active(wm: "WorldModel", profile=None, window: int = 220) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.kickoff_flank_goalpost_guard:
        return False

    if wm.game_mode().type() != GameModeType.PlayOn:
        return False
    if wm.exist_kickable_teammates():
        return False
    if not wm.ball().pos_valid():
        return False
    if not recent_our_kickoff_context(wm, profile=profile, window=window):
        return False

    ball = wm.ball().pos()
    sp = ServerParam.i()
    if ball.x() > sp.our_penalty_area_line_x() + 14.0 or ball.x() < -44.0:
        return False
    if abs(ball.y()) < 10.0 or abs(ball.y()) > sp.penalty_area_half_width() + 8.0:
        return False

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    return wm.exist_kickable_opponents() or opp_min <= min(self_min, mate_min) + 4


def kickoff_flank_goalpost_guard_target(wm: "WorldModel", profile=None) -> Vector2D | None:
    if profile is None:
        profile = get_experiment_profile()
    if not kickoff_flank_goalpost_guard_active(wm, profile=profile):
        return None

    self_unum = world_self_unum(wm)
    if self_unum not in (2, 3, 4, 5, 7):
        return None

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    if self_min <= 3 or (self_min <= mate_min and self_min <= opp_min + 2):
        return None

    ball = wm.ball().pos()
    sign = 1.0 if ball.y() >= 0.0 else -1.0
    near_fullback = 5 if sign > 0.0 else 2
    near_cb = 4 if sign > 0.0 else 3
    if self_unum not in (near_fullback, near_cb, 7):
        return None

    sp = ServerParam.i()
    if self_unum == near_fullback:
        target = Vector2D(sp.our_penalty_area_line_x() - 2.5, sign * 13.5)
    elif self_unum == near_cb:
        target = Vector2D(sp.our_penalty_area_line_x() - 5.5, sign * 6.5)
    else:
        target = Vector2D(sp.our_penalty_area_line_x() + 2.0, sign * 9.5)
    return clamp_to_field(target, margin_x=3.0, margin_y=1.5)


def kickoff_flank_backline_shelf_active(wm: "WorldModel", profile=None, window: int = 260) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.kickoff_flank_backline_shelf:
        return False

    if wm.game_mode().type() != GameModeType.PlayOn:
        return False
    if wm.exist_kickable_teammates():
        return False
    if not wm.ball().pos_valid():
        return False
    if not recent_our_kickoff_context(wm, profile=profile, window=window):
        return False

    ball = wm.ball().pos()
    sp = ServerParam.i()
    if ball.x() > sp.our_penalty_area_line_x() + 16.0 or ball.x() < -46.0:
        return False
    if abs(ball.y()) < 12.0 or abs(ball.y()) > sp.penalty_area_half_width() + 11.0:
        return False

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    return ball.x() < sp.our_penalty_area_line_x() + 6.0 or opp_min <= min(self_min, mate_min) + 5


def kickoff_flank_backline_shelf_target(wm: "WorldModel", profile=None) -> Vector2D | None:
    if profile is None:
        profile = get_experiment_profile()
    if not kickoff_flank_backline_shelf_active(wm, profile=profile):
        return None

    unum = world_self_unum(wm)
    if unum not in DEFENSIVE_FIELD_UNUMS:
        return None

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    if self_min <= 3 or (self_min <= mate_min and self_min <= opp_min + 2):
        return None

    ball = wm.ball().pos()
    sign = 1.0 if ball.y() >= 0.0 else -1.0
    ball_x = clamp(ball.x(), -38.0, -18.0)
    sp = ServerParam.i()
    near_fullback = 5 if sign > 0.0 else 2
    near_cb = 4 if sign > 0.0 else 3
    far_cb = 3 if sign > 0.0 else 4
    far_fullback = 2 if sign > 0.0 else 5

    if unum == near_fullback:
        target = Vector2D(clamp(ball_x - 10.0, -43.5, -35.0), sign * 16.5)
    elif unum == near_cb:
        target = Vector2D(clamp(ball_x - 14.0, -44.5, -38.5), sign * 7.0)
    elif unum == far_cb:
        target = Vector2D(clamp(ball_x - 15.0, -45.0, -39.5), -sign * 2.5)
    elif unum == far_fullback:
        target = Vector2D(clamp(ball_x - 12.0, -43.5, -36.5), -sign * 10.5)
    elif unum == 7:
        target = Vector2D(clamp(ball_x - 7.0, -37.5, -29.0), sign * 4.0)
    elif unum == 6:
        target = Vector2D(clamp(ball_x - 6.0, -36.5, -28.5), -sign * 8.0)
    elif unum == 8:
        target = Vector2D(clamp(ball_x - 6.0, -36.5, -28.5), sign * 12.0)
    else:
        return None

    if ball.x() < sp.our_penalty_area_line_x() + 4.0 and unum in (near_cb, far_cb):
        target._x = min(target.x(), sp.our_penalty_area_line_x() - 5.5)
    return clamp_to_field(target, margin_x=3.0, margin_y=1.5)


def kickoff_lane_lockdown_target(wm: "WorldModel", profile=None) -> Vector2D | None:
    if profile is None:
        profile = get_experiment_profile()
    if not kickoff_lane_lockdown_active(wm, profile=profile):
        return None

    unum = world_self_unum(wm)
    if unum not in DEFENSIVE_FIELD_UNUMS:
        return None

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    if self_min <= 3 or (self_min <= mate_min and self_min <= opp_min + 2):
        return None

    sp = ServerParam.i()
    ball = wm.ball().pos()
    sign = 1.0 if ball.y() >= 0.0 else -1.0
    ball_x = clamp(ball.x(), -36.0, 18.0)
    abs_ball_y = abs(ball.y())

    if unum in (2, 5):
        near_side = (unum == 5 and sign > 0.0) or (unum == 2 and sign < 0.0)
        if near_side:
            target = Vector2D(clamp(ball_x - 18.0, -42.0, -30.0), sign * clamp(abs_ball_y * 0.65, 13.0, 20.0))
        else:
            target = Vector2D(-42.0, -sign * 8.0)
    elif unum in (3, 4):
        near_side = (unum == 4 and sign > 0.0) or (unum == 3 and sign < 0.0)
        target_y = sign * 5.5 if near_side else -sign * 3.5
        target = Vector2D(-43.5, target_y)
    elif unum == 6:
        target = Vector2D(clamp(ball_x - 16.0, -36.0, -28.0), -14.0)
    elif unum == 7:
        target = Vector2D(clamp(ball_x - 18.0, -36.0, -30.0), clamp(ball.y() * 0.25, -5.0, 5.0))
    elif unum == 8:
        target = Vector2D(clamp(ball_x - 16.0, -36.0, -28.0), 14.0)
    else:
        return None

    if abs(ball.y()) <= 9.0:
        target._y = clamp(target.y(), -8.0, 8.0)
    return clamp_to_field(target, margin_x=3.0, margin_y=1.5)


def shifted_formation_position(wm: "WorldModel") -> Vector2D:
    profile = get_experiment_profile()
    StrategyFormation.i().update(wm)
    base = StrategyFormation.i().get_pos(wm.self().unum()).copy()
    ball = wm.ball().pos()
    unum = wm.self().unum()
    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    screen_active = setplay_screen_active(profile, ball, self_min, mate_min, opp_min)
    disciplined_screen = disciplined_screen_active(profile, ball, self_min, mate_min, opp_min)
    kickoff_recovery = post_our_kickoff_recovery_active(wm, profile=profile)
    kickoff_midfield_plug = post_our_kickoff_midfield_plug_active(wm, profile=profile)
    central_gap_plug = central_midfield_gap_plug_active(wm, profile=profile)
    kickoff_central_anchor = kickoff_central_channel_anchor_active(wm, profile=profile)
    kickoff_second_line_screen = kickoff_central_second_line_screen_active(wm, profile=profile)
    kickoff_flank_post_guard = kickoff_flank_goalpost_guard_active(wm, profile=profile)
    kickoff_lane_lockdown = kickoff_lane_lockdown_active(wm, profile=profile)
    kickoff_entry_stopper = kickoff_central_entry_stopper_active(wm, profile=profile)

    x_shift = clamp(ball.x() * 0.35, -15.0, 15.0)

    # Shift more aggressively toward the sideline so players follow the ball
    if profile.flank_lock and abs(ball.y()) > 18.0:
        y_coeff = 0.42
    else:
        y_coeff = 0.30 if abs(ball.y()) > 25.0 else 0.15
    y_shift = clamp(ball.y() * y_coeff, -12.0, 12.0)

    target = Vector2D(base.x() + x_shift, base.y() + y_shift)
    if opp_min + 1 < min(self_min, mate_min) or ball.x() < -18.0 or screen_active:
        retreat = defensive_retreat(unum)
        retreat += setplay_screen_retreat_bonus(unum, screen_active, ball.x())
        retreat += disciplined_screen_retreat_bonus(unum, disciplined_screen, ball.x())
        if profile.box_clear and ball.x() < -36.0 and unum in (2, 3, 4, 5, 6, 7, 8):
            retreat += 1.5 if unum in (2, 3, 4, 5) else 1.0
        if profile.box_hold and ball.x() < -32.0 and unum in (2, 3, 4, 5, 6, 7, 8):
            retreat += 0.8 if unum in (2, 3, 4, 5) else 0.5
        if profile.box_hold_light and ball.x() < -34.0 and unum in (2, 3, 4, 5, 6, 7, 8):
            retreat += 0.4 if unum in (2, 3, 4, 5) else 0.25
        if profile.flank_lock and ball.x() < 8.0 and abs(ball.y()) > 18.0 and unum in (2, 3, 4, 5, 6, 7, 8):
            retreat += 1.5 if unum in (2, 3, 4, 5) else 1.0
        target._x -= retreat
        cover_bias = 0.45 if unum in (2, 3, 4, 5) else 0.30 if unum in (6, 7, 8) else 0.15
        cover_bias += setplay_screen_cover_bias_bonus(unum, screen_active)
        cover_bias += disciplined_screen_cover_bias_bonus(unum, disciplined_screen)
        if profile.box_hold and ball.x() < -28.0 and unum in (2, 3, 4, 5, 6, 7, 8):
            cover_bias += 0.05
        if profile.box_hold_light and ball.x() < -30.0 and unum in (2, 3, 4, 5, 6, 7, 8):
            cover_bias += 0.03
        if (
            (
                (profile.cyrus_arc_second_ball and cyrus_like_opponent(wm))
                or (profile.foxsy_arc_second_ball and foxsy_cyrus_opponent(wm))
            )
            and -36.0 < ball.x() < -18.0
            and abs(ball.y()) < 18.0
            and unum in (6, 7, 8)
        ):
            cover_bias += 0.10
            target._x = min(target.x(), -24.0)
        if profile.flank_lock and abs(ball.y()) > 18.0:
            cover_bias += 0.20 if unum in (2, 3, 4, 5) else 0.15 if unum in (6, 7, 8) else 0.05
        target._y += clamp((ball.y() - target.y()) * cover_bias, -6.0, 6.0)

    if kickoff_recovery and unum in DEFENSIVE_FIELD_UNUMS:
        if unum in (2, 3, 4, 5):
            target._x = min(target.x() - 2.0, -24.0)
        else:
            target._x = min(target.x() - 1.0, -16.0)
        if abs(ball.y()) < 18.0:
            target._y += clamp((ball.y() - target.y()) * 0.18, -3.0, 3.0)

    if kickoff_midfield_plug and unum in (6, 7, 8):
        target._x = min(target.x(), -30.0)
        target._y += clamp((ball.y() - target.y()) * 0.25, -4.0, 4.0)

    if central_gap_plug and unum in (6, 7, 8):
        slot_x = -30.0 if ball.x() < -18.0 else -28.0
        target._x = min(target.x(), slot_x)
        target._y += clamp((ball.y() - target.y()) * 0.30, -5.0, 5.0)

    central_anchor_target = (
        kickoff_central_channel_anchor_target(wm, profile=profile) if kickoff_central_anchor else None
    )
    if central_anchor_target is not None:
        target = central_anchor_target

    entry_stopper_target = (
        kickoff_central_entry_stopper_target(wm, profile=profile)
        if kickoff_entry_stopper and central_anchor_target is None
        else None
    )
    if entry_stopper_target is not None:
        target = entry_stopper_target

    second_line_target = (
        kickoff_central_second_line_screen_target(wm, profile=profile)
        if kickoff_second_line_screen and central_anchor_target is None and entry_stopper_target is None
        else None
    )
    if second_line_target is not None:
        target = second_line_target

    flank_post_target = (
        kickoff_flank_goalpost_guard_target(wm, profile=profile) if kickoff_flank_post_guard else None
    )
    if flank_post_target is not None:
        target = flank_post_target

    flank_shelf_target = (
        kickoff_flank_backline_shelf_target(wm, profile=profile)
        if profile.kickoff_flank_backline_shelf and flank_post_target is None
        else None
    )
    if flank_shelf_target is not None:
        target = flank_shelf_target

    lane_lock_target = kickoff_lane_lockdown_target(wm, profile=profile) if kickoff_lane_lockdown else None
    if lane_lock_target is not None and central_anchor_target is None and flank_post_target is None and flank_shelf_target is None:
        target = lane_lock_target

    if ball.x() < -28.0 and unum in (2, 3, 4, 5, 6, 7, 8):
        target._x = min(target.x(), base.x() - 2.0)

    return clamp_to_field(target, margin_x=3.0, margin_y=1.5)


def choose_dribble_target(wm: "WorldModel") -> Vector2D:
    profile = get_experiment_profile()
    attack_unlocked = transition_attack_enabled(wm)
    sp = ServerParam.i()
    me = wm.self().pos()
    nearest_dist = float("inf")
    nearest_opp = None

    for opponent in wm.opponents():
        if opponent is None or opponent.unum() <= 0 or opponent.pos_count() > 8 or opponent.is_ghost():
            continue
        dist = opponent.pos().dist(me)
        if dist < nearest_dist:
            nearest_dist = dist
            nearest_opp = opponent

    if nearest_opp is None or nearest_dist > 6.0:
        target_y = clamp(me.y() * (0.35 if attack_unlocked else 0.20), -10.0, 10.0)
        target = Vector2D(sp.pitch_half_length(), target_y)
        return clamp_to_field(target, margin_x=2.0, margin_y=2.0)

    if (profile.setplay_shield or profile.box_clear) and me.x() < -20.0:
        lateral_offset = 14.0 if me.y() <= 0.0 else -14.0
        target = Vector2D(min(sp.pitch_half_length() - 6.0, me.x() + 18.0), me.y() + lateral_offset)
        return clamp_to_field(target, margin_x=2.0, margin_y=2.0)

    lateral_offset = 8.0 if nearest_opp.pos().y() <= me.y() else -8.0
    x_gain = 12.0
    if attack_unlocked:
        x_gain = 18.0 if me.x() > 0.0 else 14.0
        lateral_offset = 5.0 if nearest_opp.pos().y() <= me.y() else -5.0
    target = Vector2D(
        min(sp.pitch_half_length() - 2.0, me.x() + x_gain),
        me.y() + lateral_offset,
    )
    return clamp_to_field(target, margin_x=2.0, margin_y=2.0)


def decide_transition_unlock_action(wm: "WorldModel") -> Action | None:
    profile = get_experiment_profile()
    if not transition_attack_enabled(wm):
        return None

    me = wm.self().pos()

    if in_shooting_range(wm):
        return shoot_action(wm)

    teammate = find_best_pass_target(wm)
    progress_margin = 6.0 if profile.guarded_transition else 4.0
    if teammate is not None and teammate.pos().x() > me.x() + progress_margin:
        return pass_action(wm, teammate, aggressive=True)

    pressure_limit = 4.0 if profile.guarded_transition else 2.5
    transition_line = 20.0 if profile.guarded_transition else 15.0
    if nearest_valid_opponent_distance(wm, me) < pressure_limit and me.x() < transition_line:
        return None

    advance = 5.5 if profile.guarded_transition else 6.0
    return dribble_action(wm, advance=advance)


def in_our_penalty_support_zone(ball: Vector2D, sp: "ServerParam", x_pad: float = 0.0, y_pad: float = 0.0) -> bool:
    return (
        ball.x() < sp.our_penalty_area_line_x() + x_pad
        and abs(ball.y()) < sp.penalty_area_half_width() + y_pad
    )


def choose_defensive_clearance_label(
    profile,
    ball: Vector2D,
    me: Vector2D,
    opp_pressure: bool,
    sp: "ServerParam",
) -> str | None:
    if not (profile.setplay_shield or profile.box_clear):
        return None

    in_our_box = in_our_penalty_support_zone(ball, sp, x_pad=8.0, y_pad=6.0)
    goalie_risk_box = in_our_penalty_support_zone(ball, sp, x_pad=3.5, y_pad=2.5)
    shield_pressure_box = in_our_penalty_support_zone(ball, sp, x_pad=7.0, y_pad=5.5)
    deep_zone = ball.x() < -24.0 or me.x() < -24.0
    wide_trap = abs(ball.y()) > sp.pitch_half_width() - 10.0 and ball.x() < -18.0

    if profile.box_clear and (in_our_box or (deep_zone and opp_pressure)):
        return "box_clear"
    if profile.setplay_shield and (goalie_risk_box or (shield_pressure_box and opp_pressure) or (deep_zone and (opp_pressure or wide_trap))):
        return "shield_clear"
    return None


def should_use_one_step_clear(ball: Vector2D, me: Vector2D, opp_pressure: bool, sp: "ServerParam", profile=None, wm=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if in_our_penalty_support_zone(ball, sp, x_pad=3.5, y_pad=2.5) or (ball.x() < -24.0 and opp_pressure):
        return True
    if profile.cyrus2d_only_central_box_one_step_clear and not cyrus2d_central_clear_opponent(wm):
        return False
    if profile.keyed_central_box_one_step_clear and not keyed_central_clear_opponent(wm):
        return False
    if profile.central_restart_terminal_guard and central_restart_terminal_guard_active(wm, profile=profile):
        return in_central_box_clear_window(ball, me, sp, max_abs_y=13.5)
    if profile.narrow_kickoff_center_entry_clear and narrow_kickoff_center_entry_clear_active(wm, profile=profile):
        return in_central_box_clear_window(ball, me, sp, max_abs_y=9.0)
    if profile.kickoff_terminal_guard and kickoff_terminal_guard_active(wm, profile=profile):
        return in_central_box_clear_window(ball, me, sp, max_abs_y=16.0)
    enabled = (
        profile.central_box_one_step_clear
        or profile.keyed_central_box_one_step_clear
        or profile.narrow_central_box_one_step_clear
        or profile.cyrus2d_only_central_box_one_step_clear
    )
    max_abs_y = 8.0 if profile.narrow_central_box_one_step_clear else 14.0
    return bool(enabled) and in_central_box_clear_window(ball, me, sp, max_abs_y=max_abs_y)


def keyed_central_clear_opponent(wm) -> bool:
    if wm is None:
        return False
    return opponent_key_or_name(wm) in {"cyrus2d", "starter2d"}


def cyrus2d_central_clear_opponent(wm) -> bool:
    if wm is None:
        return False
    return opponent_key_or_name(wm) == "cyrus2d"


def in_central_box_clear_window(ball: Vector2D, me: Vector2D, sp: "ServerParam", max_abs_y: float = 14.0) -> bool:
    return (
        ball.x() < sp.our_penalty_area_line_x() + 6.0
        and abs(ball.y()) < max_abs_y
        and me.x() < sp.our_penalty_area_line_x() + 8.0
    )


_RECENT_TEAMMATE_TOUCH_CYCLE = -1000


def update_recent_teammate_touch(wm: "WorldModel", ball: Vector2D) -> None:
    global _RECENT_TEAMMATE_TOUCH_CYCLE
    for teammate in wm.teammates():
        if teammate.is_ghost() or teammate.pos_count() > 1:
            continue
        if teammate.pos().dist(ball) > 3.0:
            continue
        if teammate.kick() or teammate.is_tackling() or teammate.tackle_count() <= 8:
            _RECENT_TEAMMATE_TOUCH_CYCLE = wm.time().cycle()
            return


def has_recent_teammate_touch(wm: "WorldModel") -> bool:
    return wm.time().cycle() - _RECENT_TEAMMATE_TOUCH_CYCLE <= 12


def safe_to_leave_goalie_backpass_ball(wm: "WorldModel", ball: Vector2D) -> bool:
    if wm.exist_kickable_opponents():
        return False
    if wm.ball().vel().r() > 1.35:
        return False
    if nearest_valid_opponent_distance(wm, ball) < 4.5:
        return False
    return True


def should_avoid_goalie_backpass_catch(wm: "WorldModel") -> bool:
    profile = get_experiment_profile()
    if not (profile.setplay_shield or profile.goalie_backpass_guard) or not wm.self().goalie():
        return False
    if wm.game_mode().type() != GameModeType.PlayOn:
        return False

    sp = ServerParam.i()
    ball = wm.ball().pos()
    update_recent_teammate_touch(wm, ball)
    catchable_area = sp.catchable_area() if sp.catchable_area() > 0.0 else 1.3
    if not (
        wm.time().cycle() > wm.self().catch_time().cycle() + sp.catch_ban_cycle()
        and wm.ball().dist_from_self() < catchable_area + wm.ball().vel().r() + 0.2
        and in_our_penalty_support_zone(ball, sp, x_pad=-1.0, y_pad=-1.0)
    ):
        return False

    if wm.last_kicker_side() == wm.our_side():
        return safe_to_leave_goalie_backpass_ball(wm, ball)
    if not has_recent_teammate_touch(wm):
        return False
    if wm.exist_kickable_opponents():
        return False
    if wm.ball().vel().r() > 2.2:
        return False
    if nearest_valid_opponent_distance(wm, ball) < 3.8:
        return False
    return ball.x() < sp.our_penalty_area_line_x() - 4.0


def try_avoid_goalie_backpass_catch(agent: "PlayerAgent") -> bool:
    wm = agent.world()
    if not should_avoid_goalie_backpass_catch(wm):
        return False

    if wm.self().is_kickable():
        target = choose_clearance_target(wm)
        Body_KickOneStep(target, ServerParam.i().ball_speed_max()).execute(agent)
        agent.set_neck_action(Neck_TurnToBall())
        return True

    Intercept(False).execute(agent)
    agent.set_neck_action(Neck_TurnToBall())
    return True


def goalie_flank_box_intercept_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.goalie_flank_box_intercept or not wm.self().goalie():
        return False
    if profile.non_cyrus2d_goalie_flank_box_intercept and opponent_key_or_name(wm) == "cyrus2d":
        return False
    if wm.game_mode().type() != GameModeType.PlayOn:
        return False
    if not wm.ball().pos_valid():
        return False

    sp = ServerParam.i()
    ball = wm.ball().pos()
    if ball.x() > sp.our_penalty_area_line_x() + 8.0:
        return False
    if abs(ball.y()) > sp.penalty_area_half_width() + 8.0:
        return False
    if abs(ball.y()) < 10.0 and ball.x() > sp.our_penalty_area_line_x() - 1.0:
        return False

    catchable_area = sp.catchable_area() if sp.catchable_area() > 0.0 else 1.3
    can_legally_catch = wm.time().cycle() > wm.self().catch_time().cycle() + sp.catch_ban_cycle()
    if (
        can_legally_catch
        and wm.ball().dist_from_self() < catchable_area - 0.05
        and in_our_penalty_support_zone(ball, sp, x_pad=-1.0, y_pad=-1.0)
    ):
        return False
    if wm.ball().vel().r() > 2.4:
        return False

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    return self_min <= 7 and self_min <= opp_min + 2 and self_min <= mate_min + 2


def try_goalie_flank_box_intercept(agent: "PlayerAgent") -> bool:
    wm = agent.world()
    if not goalie_flank_box_intercept_active(wm):
        return False

    Intercept(False).execute(agent)
    agent.set_neck_action(Neck_TurnToBall())
    return True


def goalie_box_sweeper_intercept_active(wm: "WorldModel", profile=None) -> bool:
    if profile is None:
        profile = get_experiment_profile()
    if not profile.goalie_box_sweeper_intercept or not wm.self().goalie():
        return False
    if profile.non_cyrus2d_goalie_box_sweeper_intercept and opponent_key_or_name(wm) == "cyrus2d":
        return False
    if wm.game_mode().type() != GameModeType.PlayOn:
        return False
    if not wm.ball().pos_valid():
        return False

    sp = ServerParam.i()
    ball = wm.ball().pos()
    if ball.x() > sp.our_penalty_area_line_x() + 8.0:
        return False
    if abs(ball.y()) > sp.penalty_area_half_width() + 6.0:
        return False

    catchable_area = sp.catchable_area() if sp.catchable_area() > 0.0 else 1.3
    can_legally_catch = wm.time().cycle() > wm.self().catch_time().cycle() + sp.catch_ban_cycle()
    if (
        can_legally_catch
        and wm.ball().dist_from_self() < catchable_area - 0.05
        and in_our_penalty_support_zone(ball, sp, x_pad=-1.0, y_pad=-1.0)
    ):
        return False
    if wm.ball().vel().r() > 2.5:
        return False

    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    opponent_pressure = (
        wm.exist_kickable_opponents()
        or opp_min <= min(self_min, mate_min) + 2
        or nearest_valid_opponent_distance(wm, ball) < 8.0
    )
    if not opponent_pressure:
        return False
    if self_min > 7:
        return False
    if self_min > opp_min + 2:
        return False
    if self_min > mate_min + 2:
        return False
    return ball.x() < sp.our_penalty_area_line_x() - 1.0 or opp_min <= mate_min + 1


def try_goalie_box_sweeper_intercept(agent: "PlayerAgent") -> bool:
    wm = agent.world()
    if not goalie_box_sweeper_intercept_active(wm):
        return False

    Intercept(False).execute(agent)
    agent.set_neck_action(Neck_TurnToBall())
    return True


def should_use_safe_goalie_restart(wm: "WorldModel") -> bool:
    profile = get_experiment_profile()
    if not profile.setplay_shield or not wm.self().goalie():
        return False

    gm = wm.game_mode()
    if gm.side() != wm.our_side():
        return False

    gm_type = gm.type()
    return gm_type.is_goal_kick() or gm_type.is_goalie_catch_ball()


def goalie_restart_crowding_score(wm: "WorldModel", target: Vector2D) -> float:
    score = 0.0
    for opponent in wm.opponents():
        if opponent is None or opponent.unum() <= 0 or opponent.pos_count() > 8 or opponent.is_ghost():
            continue
        score += 1.0 / max(opponent.pos().dist2(target), 1.0)
    return score


def choose_goalie_restart_target(wm: "WorldModel") -> Vector2D:
    sp = ServerParam.i()
    wing_y = sp.pitch_half_width() - 4.0
    candidates = [
        Vector2D(18.0, wing_y),
        Vector2D(18.0, -wing_y),
        Vector2D(24.0, 24.0),
        Vector2D(24.0, -24.0),
    ]

    ball = wm.ball().pos()
    preferred_sign = 1.0 if ball.y() >= 0.0 else -1.0

    best_target = candidates[0]
    best_score = float("inf")
    for candidate in candidates:
        score = goalie_restart_crowding_score(wm, candidate)
        if candidate.y() * preferred_sign > 0.0:
            score -= 0.02
        if abs(candidate.y()) > 25.0:
            score -= 0.02
        if score < best_score:
            best_score = score
            best_target = candidate

    return clamp_to_field(best_target, margin_x=2.0, margin_y=2.0)


def try_safe_goalie_restart(agent: "PlayerAgent") -> bool:
    wm = agent.world()
    if not should_use_safe_goalie_restart(wm):
        return False

    gm_type = wm.game_mode().type()
    if gm_type.is_goalie_catch_ball():
        catch_time = agent.effector().catch_time()
        if wm.time().cycle() - catch_time.cycle() <= 2:
            agent.set_neck_action(Neck_SafeTurnToBall())
            return True

    if not wm.self().is_kickable():
        return False

    target = choose_goalie_restart_target(wm)
    Body_KickOneStep(target, ServerParam.i().ball_speed_max()).execute(agent)
    agent.set_neck_action(Neck_SafeTurnToBall())
    return True


def transition_attack_enabled(wm: "WorldModel") -> bool:
    profile = get_experiment_profile()
    if not profile.transition_unlock:
        return False
    if not profile.guarded_transition:
        return True

    me = wm.self().pos()
    ball = wm.ball().pos()
    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    nearest_opp = nearest_valid_opponent_distance(wm, me)
    under_pressure = (
        wm.exist_kickable_opponents()
        or opp_min <= 2
        or nearest_opp < 3.8
    )

    if me.x() < 6.0 or ball.x() < 0.0:
        return False
    if min(self_min, mate_min) > opp_min + 1:
        return False
    if under_pressure and me.x() < 18.0:
        return False
    if abs(ball.y()) > 24.0 and me.x() < 18.0:
        return False

    return True


def finish_attack_enabled(wm: "WorldModel") -> bool:
    profile = get_experiment_profile()
    if not profile.finish_unlock:
        return False

    me = wm.self().pos()
    ball = wm.ball().pos()
    if weak_team_killer_active(wm, profile=profile):
        min_me_x = 10.0
        min_ball_x = 5.0
        max_abs_y = 35.0
        min_opp_dist = 2.0
    else:
        min_me_x = 26.0 if profile.finish_tight else 22.0
        min_ball_x = 19.0 if profile.finish_tight else 15.0
        max_abs_y = 15.0 if profile.finish_tight else 18.0
        min_opp_dist = 6.5 if profile.finish_tight else 5.5

    if me.x() < min_me_x or ball.x() < min_ball_x:
        return False
    if abs(me.y()) > max_abs_y:
        return False
    if wm.exist_kickable_opponents() and not weak_team_killer_active(wm, profile=profile):
        return False
    if nearest_valid_opponent_distance(wm, me) < min_opp_dist:
        return False

    our_min = min(wm.intercept_table().self_reach_cycle(), wm.intercept_table().teammate_reach_cycle())
    opp_min = wm.intercept_table().opponent_reach_cycle()
    control_margin = 2 if weak_team_killer_active(wm, profile=profile) else 0 if profile.finish_tight else 1
    return our_min <= opp_min + control_margin


def defensive_clearance_label(wm: "WorldModel") -> str | None:
    profile = get_experiment_profile()
    sp = ServerParam.i()
    ball = wm.ball().pos()
    me = wm.self().pos()
    opp_pressure = (
        wm.exist_kickable_opponents()
        or wm.intercept_table().opponent_reach_cycle() <= 2
        or nearest_valid_opponent_distance(wm, me) < 4.5
    )
    return choose_defensive_clearance_label(profile, ball, me, opp_pressure, sp)


def clearance_action(wm: "WorldModel", label: str) -> Action:
    sp = ServerParam.i()
    target = choose_clearance_target(wm)
    opp_pressure = (
        wm.exist_kickable_opponents()
        or wm.intercept_table().opponent_reach_cycle() <= 2
        or nearest_valid_opponent_distance(wm, wm.self().pos()) < 4.5
    )
    one_step_clear = should_use_one_step_clear(wm.ball().pos(), wm.self().pos(), opp_pressure, sp, get_experiment_profile(), wm)
    body = (
        Body_KickOneStep(target, sp.ball_speed_max())
        if one_step_clear
        else Body_SmartKick(target, sp.ball_speed_max(), sp.ball_speed_max() - 0.2, 3)
    )
    return Action(
        body=body,
        neck=Neck_TurnToBall(),
        label=label,
        decision_target=target,
    )


def choose_clearance_target(wm: "WorldModel") -> Vector2D:
    sp = ServerParam.i()
    ball = wm.ball().pos()
    sign = 1.0 if ball.y() >= 0.0 else -1.0
    target_y = sign * (sp.pitch_half_width() - 4.0)
    if abs(ball.y()) < 8.0:
        target_y = sign * 20.0

    target_x = sp.pitch_half_length() - 6.0
    if ball.x() < -36.0:
        target_x = max(18.0, sp.pitch_half_length() - 14.0)

    return clamp_to_field(Vector2D(target_x, target_y), margin_x=2.0, margin_y=2.0)


def defensive_retreat(unum: int) -> float:
    if unum in (2, 3, 4, 5):
        return 6.0
    if unum in (6, 7, 8):
        return 4.0
    return 2.0




def clamp_to_field(point: Vector2D, margin_x: float = 1.0, margin_y: float = 1.0) -> Vector2D:
    sp = ServerParam.i()
    return Vector2D(
        clamp(point.x(), -sp.pitch_half_length() + margin_x, sp.pitch_half_length() - margin_x),
        clamp(point.y(), -sp.pitch_half_width() + margin_y, sp.pitch_half_width() - margin_y),
    )


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def distance_to_their_goal(point: Vector2D) -> float:
    sp = ServerParam.i()
    return point.dist(Vector2D(sp.pitch_half_length(), 0.0))


def point_to_segment_distance(point: Vector2D, start: Vector2D, end: Vector2D) -> float:
    px, py = point.x(), point.y()
    sx, sy = start.x(), start.y()
    ex, ey = end.x(), end.y()

    dx = ex - sx
    dy = ey - sy
    if abs(dx) < 1.0e-9 and abs(dy) < 1.0e-9:
        return math.hypot(px - sx, py - sy)

    t = ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)
    t = clamp(t, 0.0, 1.0)

    nearest_x = sx + t * dx
    nearest_y = sy + t * dy
    return math.hypot(px - nearest_x, py - nearest_y)
