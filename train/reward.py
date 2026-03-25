from __future__ import annotations

from typing import Protocol


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


def is_pass_action(action_id: int) -> bool:
    return PASS_ACTION_START <= int(action_id) <= PASS_ACTION_END


def compute_reward(
    prev_wm_state: RewardState | None,
    curr_wm_state: RewardState,
    action_taken: int,
) -> float:
    if prev_wm_state is None:
        return 0.0

    reward = -0.001

    reward += 10.0 * max(0, curr_wm_state.our_score - prev_wm_state.our_score)
    reward -= 10.0 * max(0, curr_wm_state.opponent_score - prev_wm_state.opponent_score)
    reward += 0.01 * (curr_wm_state.ball_x - prev_wm_state.ball_x)

    if (
        is_pass_action(action_taken)
        and prev_wm_state.is_kickable
        and curr_wm_state.teammate_kickable_unum is not None
        and curr_wm_state.teammate_kickable_unum != curr_wm_state.self_unum
    ):
        reward += 0.5

    if prev_wm_state.is_kickable and not curr_wm_state.is_kickable and not is_pass_action(action_taken):
        reward -= 0.5

    if int(action_taken) == SHOOT_ACTION:
        reward += 0.1

    BOUNDARY_THRESHOLD = 28.0
    if abs(curr_wm_state.ball_y) > BOUNDARY_THRESHOLD:
        excess = abs(curr_wm_state.ball_y) - BOUNDARY_THRESHOLD
        reward -= 0.003 * excess

    return float(reward)
