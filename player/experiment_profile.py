from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentProfile:
    key: str
    setplay_shield: bool = False
    flank_lock: bool = False
    box_clear: bool = False
    transition_unlock: bool = False


_PROFILE_TABLE: dict[str, ExperimentProfile] = {
    "baseline": ExperimentProfile("baseline"),
    "exp_a_setplay_shield": ExperimentProfile("exp_a_setplay_shield", setplay_shield=True),
    "exp_b_flank_lock": ExperimentProfile("exp_b_flank_lock", flank_lock=True),
    "exp_c_box_clear": ExperimentProfile("exp_c_box_clear", box_clear=True),
    "exp_d_transition_unlock": ExperimentProfile("exp_d_transition_unlock", transition_unlock=True),
    "exp_ab_setplay_flank": ExperimentProfile(
        "exp_ab_setplay_flank",
        setplay_shield=True,
        flank_lock=True,
    ),
}

_PROFILE_ALIASES = {
    "": "baseline",
    "0": "baseline",
    "default": "baseline",
    "none": "baseline",
    "base": "baseline",
    "exp_a": "exp_a_setplay_shield",
    "setplay_shield": "exp_a_setplay_shield",
    "shield": "exp_a_setplay_shield",
    "exp_b": "exp_b_flank_lock",
    "flank_lock": "exp_b_flank_lock",
    "flank": "exp_b_flank_lock",
    "exp_c": "exp_c_box_clear",
    "box_clear": "exp_c_box_clear",
    "clear": "exp_c_box_clear",
    "exp_d": "exp_d_transition_unlock",
    "transition_unlock": "exp_d_transition_unlock",
    "transition": "exp_d_transition_unlock",
    "exp_ab": "exp_ab_setplay_flank",
    "shield_flank": "exp_ab_setplay_flank",
}


def normalize_experiment_profile_name(raw_name: str | None) -> str:
    key = (raw_name or "").strip().lower()
    canonical = _PROFILE_ALIASES.get(key, key)
    return canonical if canonical in _PROFILE_TABLE else "baseline"


def resolve_experiment_profile(raw_name: str | None) -> ExperimentProfile:
    return _PROFILE_TABLE[normalize_experiment_profile_name(raw_name)]


def get_experiment_profile() -> ExperimentProfile:
    return resolve_experiment_profile(os.environ.get("ROBOCUP_EXPERIMENT_PROFILE"))


def available_experiment_profiles() -> tuple[str, ...]:
    return tuple(_PROFILE_TABLE.keys())
