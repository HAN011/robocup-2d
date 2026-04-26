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
    guarded_transition: bool = False
    box_hold: bool = False
    box_hold_light: bool = False
    finish_unlock: bool = False
    finish_tight: bool = False


_PROFILE_TABLE: dict[str, ExperimentProfile] = {
    "baseline": ExperimentProfile("baseline"),
    "exp_a_setplay_shield": ExperimentProfile("exp_a_setplay_shield", setplay_shield=True),
    "exp_b_flank_lock": ExperimentProfile("exp_b_flank_lock", flank_lock=True),
    "exp_c_box_clear": ExperimentProfile("exp_c_box_clear", box_clear=True),
    "exp_d_transition_unlock": ExperimentProfile("exp_d_transition_unlock", transition_unlock=True),
    "exp_e_box_shield": ExperimentProfile(
        "exp_e_box_shield",
        setplay_shield=True,
        box_clear=True,
    ),
    "exp_f_box_shield_transition": ExperimentProfile(
        "exp_f_box_shield_transition",
        setplay_shield=True,
        box_clear=True,
        transition_unlock=True,
        guarded_transition=True,
    ),
    "exp_g_stable_box": ExperimentProfile(
        "exp_g_stable_box",
        box_clear=True,
        box_hold=True,
    ),
    "exp_h_stable_box_finish": ExperimentProfile(
        "exp_h_stable_box_finish",
        box_clear=True,
        box_hold=True,
        finish_unlock=True,
    ),
    "exp_i_box_finish": ExperimentProfile(
        "exp_i_box_finish",
        box_clear=True,
        finish_unlock=True,
    ),
    "exp_j_light_box_finish": ExperimentProfile(
        "exp_j_light_box_finish",
        box_clear=True,
        box_hold_light=True,
        finish_unlock=True,
    ),
    "exp_k_box_finish_tight": ExperimentProfile(
        "exp_k_box_finish_tight",
        box_clear=True,
        finish_unlock=True,
        finish_tight=True,
    ),
    "exp_l_light_box_finish_tight": ExperimentProfile(
        "exp_l_light_box_finish_tight",
        box_clear=True,
        box_hold_light=True,
        finish_unlock=True,
        finish_tight=True,
    ),
    "exp_m_box_shield_flank": ExperimentProfile(
        "exp_m_box_shield_flank",
        setplay_shield=True,
        box_clear=True,
        flank_lock=True,
    ),
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
    "exp_e": "exp_e_box_shield",
    "box_shield": "exp_e_box_shield",
    "candidate_01": "exp_e_box_shield",
    "exp_f": "exp_f_box_shield_transition",
    "box_shield_transition": "exp_f_box_shield_transition",
    "candidate_02": "exp_f_box_shield_transition",
    "exp_g": "exp_g_stable_box",
    "stable_box": "exp_g_stable_box",
    "candidate_03": "exp_g_stable_box",
    "exp_h": "exp_h_stable_box_finish",
    "stable_box_finish": "exp_h_stable_box_finish",
    "candidate_04": "exp_h_stable_box_finish",
    "exp_i": "exp_i_box_finish",
    "box_finish": "exp_i_box_finish",
    "candidate_05": "exp_i_box_finish",
    "exp_j": "exp_j_light_box_finish",
    "light_box_finish": "exp_j_light_box_finish",
    "candidate_06": "exp_j_light_box_finish",
    "exp_k": "exp_k_box_finish_tight",
    "box_finish_tight": "exp_k_box_finish_tight",
    "candidate_07": "exp_k_box_finish_tight",
    "exp_l": "exp_l_light_box_finish_tight",
    "light_box_finish_tight": "exp_l_light_box_finish_tight",
    "candidate_08": "exp_l_light_box_finish_tight",
    "exp_m": "exp_m_box_shield_flank",
    "box_shield_flank": "exp_m_box_shield_flank",
    "candidate_09": "exp_m_box_shield_flank",
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
