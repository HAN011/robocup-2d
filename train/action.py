from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pyrus2d_bootstrap import bootstrap_pyrus2d


bootstrap_pyrus2d(PROJECT_ROOT)

from lib.rcsc.server_param import ServerParam
from pyrusgeom.vector_2d import Vector2D


SHOOT_ACTION = 0
DRIBBLE_FORWARD_ACTION = 1
DRIBBLE_LEFT_ACTION = 2
DRIBBLE_RIGHT_ACTION = 3
PASS_ACTION_START = 4
PASS_ACTION_END = 14
CHASE_BALL_ACTION = 15
FORMATION_ACTION = 16
CLEAR_TO_CENTER_ACTION = 17

ACTION_LABELS = {
    SHOOT_ACTION: "shoot",
    DRIBBLE_FORWARD_ACTION: "dribble_forward",
    DRIBBLE_LEFT_ACTION: "dribble_left",
    DRIBBLE_RIGHT_ACTION: "dribble_right",
    CHASE_BALL_ACTION: "chase_ball",
    FORMATION_ACTION: "formation",
    CLEAR_TO_CENTER_ACTION: "clear_to_center",
}


def is_pass_action(action_id: int) -> bool:
    return PASS_ACTION_START <= int(action_id) <= PASS_ACTION_END


def get_pass_target_unum(action_id: int) -> int | None:
    action_id = int(action_id)
    if not is_pass_action(action_id):
        return None
    return action_id - PASS_ACTION_START + 1


def action_label(action_id: int) -> str:
    action_id = int(action_id)
    if is_pass_action(action_id):
        return f"pass_{get_pass_target_unum(action_id)}"
    return ACTION_LABELS.get(action_id, f"unknown_{action_id}")


def _goal_target() -> Vector2D:
    return Vector2D(ServerParam.i().pitch_half_length(), 0.0)


def _dribble_lane_target(wm, lateral_offset: float) -> Vector2D:
    sp = ServerParam.i()
    return Vector2D(
        sp.pitch_half_length(),
        max(-sp.pitch_half_width() + 1.5, min(sp.pitch_half_width() - 1.5, wm.self().pos().y() + lateral_offset)),
    )


def action_to_decision(action_id: int, wm):
    from player import decision as decision_module

    action_id = int(action_id)

    if action_id == SHOOT_ACTION:
        if wm.self().is_kickable():
            return decision_module.shoot_action(wm)
        return decision_module.decide_off_ball_action(wm)

    if action_id == DRIBBLE_FORWARD_ACTION:
        if wm.self().is_kickable():
            return decision_module.Action(
                body=decision_module.Body_Dribble(_goal_target()),
                neck=decision_module.Neck_TurnToBall(),
                label="rl_dribble_forward",
            )
        return decision_module.decide_off_ball_action(wm)

    if action_id == DRIBBLE_LEFT_ACTION:
        if wm.self().is_kickable():
            return decision_module.Action(
                body=decision_module.Body_Dribble(_dribble_lane_target(wm, 12.0)),
                neck=decision_module.Neck_TurnToBall(),
                label="rl_dribble_left",
            )
        return decision_module.decide_off_ball_action(wm)

    if action_id == DRIBBLE_RIGHT_ACTION:
        if wm.self().is_kickable():
            return decision_module.Action(
                body=decision_module.Body_Dribble(_dribble_lane_target(wm, -12.0)),
                neck=decision_module.Neck_TurnToBall(),
                label="rl_dribble_right",
            )
        return decision_module.decide_off_ball_action(wm)

    if is_pass_action(action_id):
        target_unum = get_pass_target_unum(action_id)
        teammate = wm.our_player(target_unum) if target_unum is not None else None
        if not wm.self().is_kickable():
            return decision_module.decide_off_ball_action(wm)
        if teammate is None or teammate.unum() == wm.self().unum() or teammate.is_ghost() or teammate.pos_count() > 8:
            return decision_module.dribble_action(wm)
        return decision_module.pass_action(wm, teammate)

    if action_id == CHASE_BALL_ACTION:
        sp = ServerParam.i()
        intercept_cycle = max(1, min(wm.intercept_table().self_reach_cycle(), 6))
        chase_target = decision_module.clamp_to_field(wm.ball().inertia_point(intercept_cycle))
        return decision_module.Action(
            body=decision_module.Body_GoToPoint(chase_target, 0.7, sp.max_dash_power()),
            neck=decision_module.Neck_TurnToBall(),
            label="rl_chase_ball",
        )

    if action_id == FORMATION_ACTION:
        sp = ServerParam.i()
        return decision_module.Action(
            body=decision_module.Body_GoToPoint(
                decision_module.shifted_formation_position(wm),
                1.0,
                sp.max_dash_power(),
            ),
            neck=decision_module.Neck_TurnToBall(),
            label="rl_move_to_formation",
        )

    if action_id == CLEAR_TO_CENTER_ACTION:
        sp = ServerParam.i()
        from player import decision as dm

        if wm.self().is_kickable():
            center_target = Vector2D(
                min(wm.self().pos().x() + 5.0, sp.pitch_half_length() - 2.0),
                0.0,
            )
            return dm.Action(
                body=dm.Body_SmartKick(center_target, 2.0, 1.5, 3),
                neck=dm.Neck_TurnToBall(),
                label="rl_clear_to_center",
            )

        intercept_cycle = max(1, min(wm.intercept_table().self_reach_cycle(), 6))
        chase_target = dm.clamp_to_field(wm.ball().inertia_point(intercept_cycle))
        return dm.Action(
            body=dm.Body_GoToPoint(chase_target, 0.7, sp.max_dash_power()),
            neck=dm.Neck_TurnToBall(),
            label="rl_chase_for_clear",
        )

    return decision_module.decide_off_ball_action(wm)
