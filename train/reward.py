from __future__ import annotations

import math
from typing import Protocol

# Keep these in sync with train/action.py constants.
SHOOT_ACTION = 0
PASS_ACTION_START = 4
PASS_ACTION_END = 14

class RewardState(Protocol):
    self_unum: int
    ball_x: float
    ball_y: float
    our_score: int
    opponent_score: int
    is_kickable: bool
    teammate_kickable_unum: int | None
    opponent_kickable_unum: int | None


def _is_pass_action(action_id: int) -> bool:
    return PASS_ACTION_START <= int(action_id) <= PASS_ACTION_END


def _is_shoot_action(action_id: int) -> bool:
    return int(action_id) == SHOOT_ACTION


def _opponent_has_ball(curr: RewardState) -> bool:
    return curr.opponent_kickable_unum is not None


def _teammate_received_ball(prev: RewardState, curr: RewardState) -> bool:
    if not prev.is_kickable:
        return False

    teammate_unum = curr.teammate_kickable_unum
    return teammate_unum is not None and int(teammate_unum) != int(curr.self_unum)


def _log_reward_components(message: str) -> None:
    try:
        from lib.debug.debug import log

        log.os_log().info(message)
    except Exception:
        # Training utilities may run in stripped-down environments without Pyrus2D logger deps.
        return


def compute_reward(
    prev_wm_state: RewardState | None,
    curr_wm_state: RewardState,
    action_taken: int,
) -> float:
    if prev_wm_state is None:
        return 0.0

    goal_component = 0.0
    dist_component = 0.0
    possession_component = 0.0
    pass_component = 0.0
    ball_loss_component = 0.0
    shot_component = 0.0
    step_component = -0.0002
    boundary_component = 0.0

    our_goal_delta = curr_wm_state.our_score - prev_wm_state.our_score
    opp_goal_delta = curr_wm_state.opponent_score - prev_wm_state.opponent_score
    goal_component += 10.0 * our_goal_delta
    goal_component -= 10.0 * opp_goal_delta

    prev_goal_dist = math.hypot(52.5 - prev_wm_state.ball_x, prev_wm_state.ball_y)
    curr_goal_dist = math.hypot(52.5 - curr_wm_state.ball_x, curr_wm_state.ball_y)
    dist_component += 0.05 * (prev_goal_dist - curr_goal_dist)

    if curr_wm_state.is_kickable:
        possession_component += 0.005
    elif _opponent_has_ball(curr_wm_state):
        possession_component -= 0.003

    if _is_pass_action(action_taken) and prev_wm_state.is_kickable:
        if _teammate_received_ball(prev_wm_state, curr_wm_state):
            forward_gain = max(0.0, curr_wm_state.ball_x - prev_wm_state.ball_x)
            pass_component += 0.3 + 0.015 * forward_gain

    if not _is_pass_action(action_taken) and prev_wm_state.is_kickable and not curr_wm_state.is_kickable:
        if not _teammate_received_ball(prev_wm_state, curr_wm_state):
            ball_loss_component -= 0.4

    if _is_shoot_action(action_taken) and prev_wm_state.is_kickable:
        shot_dist = math.hypot(52.5 - prev_wm_state.ball_x, prev_wm_state.ball_y)
        if shot_dist < 25.0:
            shot_component += 0.2 * (1.0 - shot_dist / 25.0)

    if abs(curr_wm_state.ball_y) > 28.0:
        boundary_component -= 0.015 * (abs(curr_wm_state.ball_y) - 28.0)

    reward = (
        goal_component
        + dist_component
        + possession_component
        + pass_component
        + ball_loss_component
        + shot_component
        + step_component
        + boundary_component
    )

    _log_reward_components(
        "reward components: "
        f"goal={goal_component:.3f} "
        f"dist={dist_component:.3f} "
        f"poss={possession_component:.3f} "
        f"pass={pass_component:.3f} "
        f"loss={ball_loss_component:.3f} "
        f"shot={shot_component:.3f} "
        f"step={step_component:.3f} "
        f"boundary={boundary_component:.3f} "
        f"total={reward:.3f}"
    )

    return float(reward)
