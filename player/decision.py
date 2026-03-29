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
from lib.action.neck_turn_to_ball import NeckTurnToBall
from lib.action.smart_kick import SmartKick
from lib.debug.debug import log
from lib.player.soccer_action import BodyAction, NeckAction
from lib.rcsc.types import GameModeType
from lib.rcsc.server_param import ServerParam
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
            return BhvKick().execute(agent)
        except Exception as exc:
            log.os_log().error(f"BhvKick crashed this cycle, fallback to safe kick: {exc}")

        fallback = decide_on_ball_fallback_action(agent.world())
        fallback.body.execute(agent)
        if fallback.neck is not None:
            agent.set_neck_action(fallback.neck)
        return True


class Body_BhvMove(BodyAction):
    def execute(self, agent: "PlayerAgent"):
        try:
            if _get_bhv_move().execute(agent):
                return True
        except Exception as exc:
            log.os_log().error(f"BhvMove crashed, fallback to formation move: {exc}")

        wm = agent.world()
        sp = ServerParam.i()
        target = shifted_formation_position(wm)
        return Body_GoToPoint(target, 1.0, sp.max_dash_power()).execute(agent)


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
        from base.bhv_block import Bhv_Block

        try:
            if Bhv_Block().execute(agent):
                return True
        except Exception as exc:
            log.os_log().error(f"Bhv_Block crashed, fallback to BhvMove: {exc}")

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

    def execute(self, agent: "PlayerAgent"):
        log.debug_client().add_message(self.label)
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


def decide_off_ball_action(wm: "WorldModel") -> Action:
    sp = ServerParam.i()
    self_min = wm.intercept_table().self_reach_cycle()
    mate_min = wm.intercept_table().teammate_reach_cycle()
    opp_min = wm.intercept_table().opponent_reach_cycle()
    ball_near_sideline = abs(wm.ball().pos().y()) > sp.pitch_half_width() - 8.0

    if (
        not wm.exist_kickable_teammates()
        and (
            self_min <= 3
            or (self_min <= mate_min and self_min < opp_min + 3)
            or (ball_near_sideline and self_min <= mate_min + 1)
        )
    ):
        return Action(body=Body_BhvMove(), neck=None, label="bhv_move_intercept")

    if opp_min < mate_min:
        return Action(body=Body_BhvBlock(), neck=None, label="bhv_block")

    return Action(body=Body_BhvMove(), neck=None, label="bhv_move")


def decide_off_ball_formation_only(wm: "WorldModel") -> Action:
    sp = ServerParam.i()
    target = shifted_formation_position(wm)
    return Action(
        body=Body_GoToPoint(target, 1.0, sp.max_dash_power()),
        neck=Neck_TurnToBall(),
        label="move_to_formation",
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
    )


def pass_action(wm: "WorldModel", teammate: "PlayerObject") -> Action:
    start_speed = clamp(wm.self().pos().dist(teammate.pos()) * 0.18 + 1.0, 1.2, 2.7)
    return Action(
        body=Body_KickOneStep(teammate.pos(), start_speed),
        neck=Neck_TurnToBall(),
        label=f"pass_{teammate.unum()}",
    )


def dribble_action(wm: "WorldModel") -> Action:
    sp = ServerParam.i()
    goal_target = Vector2D(sp.pitch_half_length(), 0.0)
    return Action(
        body=Body_Dribble(goal_target),
        neck=Neck_TurnToBall(),
        label="dribble",
    )


def in_shooting_range(wm: "WorldModel") -> bool:
    sp = ServerParam.i()
    goal_center = Vector2D(sp.pitch_half_length(), 0.0)
    goal_vector = goal_center - wm.self().pos()
    goal_distance = goal_vector.r()
    goal_angle = (goal_vector.th() - wm.self().body()).abs()
    return goal_distance < 20.0 and goal_angle < 30.0


def find_best_pass_target(wm: "WorldModel"):
    me = wm.self()
    candidates = []

    for teammate in wm.teammates():
        if teammate is None:
            continue
        if teammate.unum() <= 0 or teammate.pos_count() > 8 or teammate.is_ghost():
            continue
        if teammate.goalie():
            continue
        if distance_to_their_goal(teammate.pos()) >= distance_to_their_goal(me.pos()) - 1.0:
            continue
        if not pass_lane_clear(wm, teammate):
            continue
        if not receiver_goal_lane_clear(wm, teammate):
            continue

        candidates.append(teammate)

    if not candidates:
        return None

    return max(candidates, key=lambda player: (player.pos().x(), -abs(player.pos().y())))


def pass_lane_clear(wm: "WorldModel", teammate: "PlayerObject") -> bool:
    start = wm.self().pos()
    end = teammate.pos()

    for opponent in wm.opponents():
        if opponent is None or opponent.unum() <= 0 or opponent.pos_count() > 8 or opponent.is_ghost():
            continue

        if point_to_segment_distance(opponent.pos(), start, end) < 3.0:
            return False

    return True


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


def shifted_formation_position(wm: "WorldModel") -> Vector2D:
    StrategyFormation.i().update(wm)
    base = StrategyFormation.i().get_pos(wm.self().unum()).copy()
    ball = wm.ball().pos()

    x_shift = clamp(ball.x() * 0.35, -15.0, 15.0)

    # Shift more aggressively toward the sideline so players follow the ball
    y_coeff = 0.30 if abs(ball.y()) > 25.0 else 0.15
    y_shift = clamp(ball.y() * y_coeff, -12.0, 12.0)

    target = Vector2D(base.x() + x_shift, base.y() + y_shift)
    return clamp_to_field(target, margin_x=3.0, margin_y=1.5)


def should_force_formation_only(wm: "WorldModel") -> bool:
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

    if game_mode_type not in opponent_restart_modes:
        return False

    is_opponent_restart = game_mode.side() != wm.our_side()

    if not is_opponent_restart:
        return False

    # During opponent KickIn, allow the nearest player to approach the ball
    # instead of standing passively in formation
    if game_mode_type in (GameModeType.KickIn_Left, GameModeType.KickIn_Right):
        self_min = wm.intercept_table().self_reach_cycle()
        mate_min = wm.intercept_table().teammate_reach_cycle()
        if self_min <= mate_min + 2:
            return False

    return True


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
