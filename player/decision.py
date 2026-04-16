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


class Body_SmartKick(SmartKick):
    pass


class Body_GoToPoint(GoToPoint):
    pass


class Neck_TurnToBall(NeckTurnToBall):
    pass


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
            agent.set_neck_action(NeckTurnToBallOrScan())
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


def get_decision(agent: "PlayerAgent") -> Action:
    wm = agent.world()
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
        return Action(body=Body_BhvSetPlay(), neck=None, label="set_play")

    if _should_tackle(wm):
        return Action(body=Body_BasicTackle(), neck=None, label="basic_tackle")

    if wm.self().is_kickable():
        return decide_on_ball_action(agent)

    return decide_off_ball_action(wm)


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
    clearance_label = defensive_clearance_label(wm)
    if clearance_label is not None:
        return clearance_action(wm, clearance_label)

    profile = get_experiment_profile()
    if profile.transition_unlock:
        transition_action = decide_transition_unlock_action(wm)
        if transition_action is not None:
            return transition_action

    return None


def decide_off_ball_action(wm: "WorldModel") -> Action:
    profile = get_experiment_profile()
    sp = ServerParam.i()
    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    ball_near_sideline = abs(wm.ball().pos().y()) > sp.pitch_half_width() - 8.0
    flank_lock_alert = profile.flank_lock and wm.ball().pos().x() < 8.0 and abs(wm.ball().pos().y()) > 18.0
    urgent_defense = (
        wm.ball().pos().x() < -12.0
        and self_min <= mate_min + 1
        and self_min <= opp_min + 2
    )

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
        block_target = find_block_target(wm)
        if block_target is None and flank_lock_alert:
            block_target = flank_lock_block_target(wm)
        return Action(
            body=Body_BhvBlock(),
            neck=None,
            label="bhv_block",
            decision_target=block_target.copy() if block_target is not None else None,
            block_target=block_target,
        )

    return Action(
        body=Body_BhvMove(),
        neck=None,
        label="bhv_move",
        decision_target=StrategyFormation.i().get_pos(wm.self().unum()).copy(),
    )


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

    self_goal = False
    if self_reach_point.x() < -sp.pitch_half_length():
        ball_ray = Ray2D(wm.ball().pos(), wm.ball().vel().th())
        goal_line = Line2D(Vector2D(-sp.pitch_half_length(), 10.0), Vector2D(-sp.pitch_half_length(), -10.0))
        intersect = ball_ray.intersection(goal_line)
        if intersect and intersect.is_valid() and intersect.abs_y() < sp.goal_half_width() + 1.0:
            self_goal = True

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
        advance = 6.0 if get_experiment_profile().transition_unlock and wm.self().pos().x() > -5.0 else 4.0
    return Action(
        body=Body_Dribble(goal_target, advance=advance),
        neck=Neck_TurnToBall(),
        label="dribble",
        decision_target=goal_target,
    )


def in_shooting_range(wm: "WorldModel") -> bool:
    profile = get_experiment_profile()
    sp = ServerParam.i()
    goal_center = Vector2D(sp.pitch_half_length(), 0.0)
    goal_vector = goal_center - wm.self().pos()
    goal_distance = goal_vector.r()
    goal_angle = (goal_vector.th() - wm.self().body()).abs()
    max_distance = 24.0 if profile.transition_unlock else 20.0
    max_angle = 38.0 if profile.transition_unlock else 30.0
    return goal_distance < max_distance and goal_angle < max_angle


def find_best_pass_target(wm: "WorldModel"):
    profile = get_experiment_profile()
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
        if profile.transition_unlock and me.pos().x() > -5.0 and teammate.pos().x() < me.pos().x() - 2.0:
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
        if profile.transition_unlock:
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
    if profile.transition_unlock and end.x() > start.x():
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


def shifted_formation_position(wm: "WorldModel") -> Vector2D:
    profile = get_experiment_profile()
    StrategyFormation.i().update(wm)
    base = StrategyFormation.i().get_pos(wm.self().unum()).copy()
    ball = wm.ball().pos()
    unum = wm.self().unum()
    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()

    x_shift = clamp(ball.x() * 0.35, -15.0, 15.0)

    # Shift more aggressively toward the sideline so players follow the ball
    if profile.flank_lock and abs(ball.y()) > 18.0:
        y_coeff = 0.42
    else:
        y_coeff = 0.30 if abs(ball.y()) > 25.0 else 0.15
    y_shift = clamp(ball.y() * y_coeff, -12.0, 12.0)

    target = Vector2D(base.x() + x_shift, base.y() + y_shift)
    if opp_min + 1 < min(self_min, mate_min) or ball.x() < -18.0:
        retreat = defensive_retreat(unum)
        if profile.box_clear and ball.x() < -36.0 and unum in (2, 3, 4, 5, 6, 7, 8):
            retreat += 1.5 if unum in (2, 3, 4, 5) else 1.0
        if profile.flank_lock and ball.x() < 8.0 and abs(ball.y()) > 18.0 and unum in (2, 3, 4, 5, 6, 7, 8):
            retreat += 1.5 if unum in (2, 3, 4, 5) else 1.0
        target._x -= retreat
        cover_bias = 0.45 if unum in (2, 3, 4, 5) else 0.30 if unum in (6, 7, 8) else 0.15
        if profile.flank_lock and abs(ball.y()) > 18.0:
            cover_bias += 0.20 if unum in (2, 3, 4, 5) else 0.15 if unum in (6, 7, 8) else 0.05
        target._y += clamp((ball.y() - target.y()) * cover_bias, -6.0, 6.0)

    if ball.x() < -28.0 and unum in (2, 3, 4, 5, 6, 7, 8):
        target._x = min(target.x(), base.x() - 2.0)

    return clamp_to_field(target, margin_x=3.0, margin_y=1.5)


def choose_dribble_target(wm: "WorldModel") -> Vector2D:
    profile = get_experiment_profile()
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
        target_y = clamp(me.y() * (0.35 if profile.transition_unlock else 0.20), -10.0, 10.0)
        target = Vector2D(sp.pitch_half_length(), target_y)
        return clamp_to_field(target, margin_x=2.0, margin_y=2.0)

    if (profile.setplay_shield or profile.box_clear) and me.x() < -20.0:
        lateral_offset = 14.0 if me.y() <= 0.0 else -14.0
        target = Vector2D(min(sp.pitch_half_length() - 6.0, me.x() + 18.0), me.y() + lateral_offset)
        return clamp_to_field(target, margin_x=2.0, margin_y=2.0)

    lateral_offset = 8.0 if nearest_opp.pos().y() <= me.y() else -8.0
    x_gain = 12.0
    if profile.transition_unlock:
        x_gain = 18.0 if me.x() > 0.0 else 14.0
        lateral_offset = 5.0 if nearest_opp.pos().y() <= me.y() else -5.0
    target = Vector2D(
        min(sp.pitch_half_length() - 2.0, me.x() + x_gain),
        me.y() + lateral_offset,
    )
    return clamp_to_field(target, margin_x=2.0, margin_y=2.0)


def decide_transition_unlock_action(wm: "WorldModel") -> Action | None:
    me = wm.self().pos()
    if me.x() < -8.0:
        return None

    if in_shooting_range(wm):
        return shoot_action(wm)

    teammate = find_best_pass_target(wm)
    if teammate is not None and teammate.pos().x() > me.x() + 4.0:
        return pass_action(wm, teammate, aggressive=True)

    if nearest_valid_opponent_distance(wm, me) < 2.5 and me.x() < 15.0:
        return None

    return dribble_action(wm, advance=6.0)


def defensive_clearance_label(wm: "WorldModel") -> str | None:
    profile = get_experiment_profile()
    if not (profile.setplay_shield or profile.box_clear):
        return None

    sp = ServerParam.i()
    ball = wm.ball().pos()
    me = wm.self().pos()
    opp_pressure = (
        wm.exist_kickable_opponents()
        or wm.intercept_table().opponent_reach_cycle() <= 2
        or nearest_valid_opponent_distance(wm, me) < 4.5
    )
    in_our_box = (
        ball.x() < sp.our_penalty_area_line_x() + 6.0
        and abs(ball.y()) < sp.penalty_area_half_width() + 5.0
    )
    deep_zone = ball.x() < -24.0 or me.x() < -24.0
    wide_trap = abs(ball.y()) > sp.pitch_half_width() - 10.0 and ball.x() < -18.0

    if profile.box_clear and (in_our_box or (deep_zone and opp_pressure)):
        return "box_clear"
    if profile.setplay_shield and deep_zone and (opp_pressure or wide_trap):
        return "shield_clear"
    return None


def clearance_action(wm: "WorldModel", label: str) -> Action:
    sp = ServerParam.i()
    target = choose_clearance_target(wm)
    return Action(
        body=Body_SmartKick(target, sp.ball_speed_max(), sp.ball_speed_max() - 0.2, 3),
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
