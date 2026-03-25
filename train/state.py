from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pyrus2d_bootstrap import bootstrap_pyrus2d


bootstrap_pyrus2d(PROJECT_ROOT)

if TYPE_CHECKING:
    from lib.player.object_player import PlayerObject
    from lib.player.world_model import WorldModel


PITCH_HALF_LENGTH = 52.5
PITCH_HALF_WIDTH = 34.0


@dataclass(frozen=True)
class StateSnapshot:
    observation: np.ndarray
    cycle: int
    stopped_cycle: int
    request_id: int
    episode_id: str
    self_unum: int
    ball_x: float
    ball_y: float
    our_score: int
    opponent_score: int
    is_kickable: bool
    teammate_kickable_unum: int | None
    opponent_kickable_unum: int | None
    game_mode: str
    last_kicker_side: str
    prev_action_source: str


def _clip_unit(value: float) -> float:
    return float(max(-1.0, min(1.0, value)))


def _normalize_x(value: float) -> float:
    return _clip_unit(value / PITCH_HALF_LENGTH)


def _normalize_y(value: float) -> float:
    return _clip_unit(value / PITCH_HALF_WIDTH)


def _normalize_stamina(value: float) -> float:
    from lib.rcsc.server_param import ServerParam

    stamina_max = max(ServerParam.i().stamina_max(), 1.0)
    return _clip_unit((value / stamina_max) * 2.0 - 1.0)


def _normalize_bool(flag: bool) -> float:
    return 1.0 if flag else -1.0


def _player_xy(player: "PlayerObject | None") -> tuple[float, float]:
    if player is None:
        return 0.0, 0.0
    if hasattr(player, "is_ghost") and player.is_ghost():
        return 0.0, 0.0
    if hasattr(player, "pos_valid") and not player.pos_valid():
        return 0.0, 0.0
    pos = player.pos()
    return _normalize_x(pos.x()), _normalize_y(pos.y())


def extract_state_vector(wm: "WorldModel") -> np.ndarray:
    ball = wm.ball()
    me = wm.self()

    features: list[float] = []

    ball_pos = ball.pos() if ball.pos_valid() else None
    ball_vel = ball.vel() if ball.vel_valid() else None
    features.extend(
        [
            _normalize_x(ball_pos.x()) if ball_pos is not None else 0.0,
            _normalize_y(ball_pos.y()) if ball_pos is not None else 0.0,
            _normalize_x(ball_vel.x()) if ball_vel is not None else 0.0,
            _normalize_y(ball_vel.y()) if ball_vel is not None else 0.0,
        ]
    )

    me_pos = me.pos() if me.pos_valid() else None
    me_vel = me.vel() if me.vel_valid() else None
    features.extend(
        [
            _normalize_x(me_pos.x()) if me_pos is not None else 0.0,
            _normalize_y(me_pos.y()) if me_pos is not None else 0.0,
            _normalize_x(me_vel.x()) if me_vel is not None else 0.0,
            _normalize_y(me_vel.y()) if me_vel is not None else 0.0,
            _normalize_stamina(me.stamina()),
            _normalize_bool(me.is_kickable()),
        ]
    )

    for unum in range(1, 12):
        if unum == me.unum():
            continue
        features.extend(_player_xy(wm.our_player(unum)))

    for unum in range(1, 12):
        features.extend(_player_xy(wm.their_player(unum)))

    if len(features) != 52:
        raise ValueError(f"unexpected observation size: {len(features)}")

    return np.asarray(features, dtype=np.float32)


def _score_pair(wm: "WorldModel") -> tuple[int, int]:
    from lib.rcsc.types import SideID

    game_mode = wm.game_mode()
    left_score = int(getattr(game_mode, "_left_score", 0))
    right_score = int(getattr(game_mode, "_right_score", 0))

    if wm.our_side() == SideID.RIGHT:
        return right_score, left_score
    return left_score, right_score


def _unum_or_none(player: "PlayerObject | None") -> int | None:
    if player is None:
        return None
    unum = player.unum()
    return int(unum) if unum and unum > 0 else None


def build_state_snapshot(
    wm: "WorldModel",
    episode_id: str = "",
    request_id: int = 0,
    prev_action_source: str = "reset",
) -> StateSnapshot:
    our_score, opponent_score = _score_pair(wm)
    ball_x = wm.ball().pos().x() if wm.ball().pos_valid() else 0.0
    ball_y = wm.ball().pos().y() if wm.ball().pos_valid() else 0.0
    game_mode = wm.game_mode().type().value
    last_kicker_side = getattr(wm.last_kicker_side(), "value", str(wm.last_kicker_side()))

    return StateSnapshot(
        observation=extract_state_vector(wm),
        cycle=wm.time().cycle(),
        stopped_cycle=wm.time().stopped_cycle(),
        request_id=request_id,
        episode_id=episode_id,
        self_unum=wm.self().unum(),
        ball_x=ball_x,
        ball_y=ball_y,
        our_score=our_score,
        opponent_score=opponent_score,
        is_kickable=wm.self().is_kickable(),
        teammate_kickable_unum=_unum_or_none(wm.kickable_teammate()),
        opponent_kickable_unum=_unum_or_none(wm.kickable_opponent()),
        game_mode=game_mode,
        last_kicker_side=last_kicker_side,
        prev_action_source=prev_action_source,
    )


def build_bridge_state_message(
    wm: "WorldModel",
    episode_id: str,
    request_id: int,
    prev_action_source: str,
) -> dict:
    snapshot = build_state_snapshot(
        wm,
        episode_id=episode_id,
        request_id=request_id,
        prev_action_source=prev_action_source,
    )
    return {
        "observation": snapshot.observation.tolist(),
        "cycle": snapshot.cycle,
        "stopped_cycle": snapshot.stopped_cycle,
        "request_id": snapshot.request_id,
        "episode_id": snapshot.episode_id,
        "self_unum": snapshot.self_unum,
        "ball_x": snapshot.ball_x,
        "ball_y": snapshot.ball_y,
        "our_score": snapshot.our_score,
        "opponent_score": snapshot.opponent_score,
        "is_kickable": snapshot.is_kickable,
        "teammate_kickable_unum": snapshot.teammate_kickable_unum,
        "opponent_kickable_unum": snapshot.opponent_kickable_unum,
        "game_mode": snapshot.game_mode,
        "last_kicker_side": snapshot.last_kicker_side,
        "prev_action_source": snapshot.prev_action_source,
    }


def snapshot_from_message(message: dict) -> StateSnapshot:
    return StateSnapshot(
        observation=np.asarray(message["observation"], dtype=np.float32),
        cycle=int(message.get("cycle", 0)),
        stopped_cycle=int(message.get("stopped_cycle", 0)),
        request_id=int(message.get("request_id", 0)),
        episode_id=str(message.get("episode_id", "")),
        self_unum=int(message.get("self_unum", 0)),
        ball_x=float(message.get("ball_x", 0.0)),
        ball_y=float(message.get("ball_y", 0.0)),
        our_score=int(message.get("our_score", 0)),
        opponent_score=int(message.get("opponent_score", 0)),
        is_kickable=bool(message.get("is_kickable", False)),
        teammate_kickable_unum=message.get("teammate_kickable_unum"),
        opponent_kickable_unum=message.get("opponent_kickable_unum"),
        game_mode=str(message.get("game_mode", "")),
        last_kicker_side=str(message.get("last_kicker_side", "")),
        prev_action_source=str(message.get("prev_action_source", "unknown")),
    )
