#!/usr/bin/env python3
from __future__ import annotations

import unittest

from player.experiment_profile import (
    available_experiment_profiles,
    normalize_experiment_profile_name,
    resolve_experiment_profile,
)


class ExperimentProfileTest(unittest.TestCase):
    def test_unknown_profile_falls_back_to_baseline(self) -> None:
        self.assertEqual(normalize_experiment_profile_name("mystery"), "baseline")

    def test_aliases_resolve_to_expected_profiles(self) -> None:
        self.assertEqual(normalize_experiment_profile_name("exp_a"), "exp_a_setplay_shield")
        self.assertEqual(normalize_experiment_profile_name("flank"), "exp_b_flank_lock")
        self.assertEqual(normalize_experiment_profile_name("transition"), "exp_d_transition_unlock")

    def test_combo_profile_enables_both_axes(self) -> None:
        profile = resolve_experiment_profile("exp_ab")
        self.assertTrue(profile.setplay_shield)
        self.assertTrue(profile.flank_lock)
        self.assertFalse(profile.box_clear)
        self.assertFalse(profile.transition_unlock)

    def test_new_candidate_profile_combines_box_and_shield(self) -> None:
        profile = resolve_experiment_profile("candidate_01")
        self.assertTrue(profile.setplay_shield)
        self.assertTrue(profile.box_clear)
        self.assertFalse(profile.flank_lock)
        self.assertFalse(profile.transition_unlock)

    def test_guarded_transition_candidate_is_resolved(self) -> None:
        profile = resolve_experiment_profile("candidate_02")
        self.assertTrue(profile.setplay_shield)
        self.assertTrue(profile.box_clear)
        self.assertTrue(profile.transition_unlock)
        self.assertTrue(profile.guarded_transition)

    def test_stable_box_candidate_keeps_shield_off(self) -> None:
        profile = resolve_experiment_profile("candidate_03")
        self.assertFalse(profile.setplay_shield)
        self.assertTrue(profile.box_clear)
        self.assertTrue(profile.box_hold)
        self.assertFalse(profile.finish_unlock)

    def test_finish_candidate_only_unlocks_safe_finishing(self) -> None:
        profile = resolve_experiment_profile("candidate_04")
        self.assertFalse(profile.setplay_shield)
        self.assertTrue(profile.box_clear)
        self.assertTrue(profile.box_hold)
        self.assertTrue(profile.finish_unlock)
        self.assertFalse(profile.transition_unlock)

    def test_box_finish_candidate_keeps_hold_off(self) -> None:
        profile = resolve_experiment_profile("candidate_05")
        self.assertTrue(profile.box_clear)
        self.assertFalse(profile.box_hold)
        self.assertFalse(profile.box_hold_light)
        self.assertTrue(profile.finish_unlock)
        self.assertFalse(profile.transition_unlock)

    def test_light_box_finish_candidate_uses_light_hold(self) -> None:
        profile = resolve_experiment_profile("candidate_06")
        self.assertTrue(profile.box_clear)
        self.assertFalse(profile.box_hold)
        self.assertTrue(profile.box_hold_light)
        self.assertTrue(profile.finish_unlock)
        self.assertFalse(profile.transition_unlock)

    def test_box_finish_tight_candidate_stays_finish_only(self) -> None:
        profile = resolve_experiment_profile("candidate_07")
        self.assertTrue(profile.box_clear)
        self.assertFalse(profile.box_hold)
        self.assertFalse(profile.box_hold_light)
        self.assertTrue(profile.finish_unlock)
        self.assertTrue(profile.finish_tight)

    def test_light_box_finish_tight_candidate_combines_light_hold(self) -> None:
        profile = resolve_experiment_profile("candidate_08")
        self.assertTrue(profile.box_clear)
        self.assertFalse(profile.box_hold)
        self.assertTrue(profile.box_hold_light)
        self.assertTrue(profile.finish_unlock)
        self.assertTrue(profile.finish_tight)

    def test_box_shield_flank_candidate_combines_three_defensive_axes(self) -> None:
        profile = resolve_experiment_profile("candidate_09")
        self.assertTrue(profile.setplay_shield)
        self.assertTrue(profile.box_clear)
        self.assertTrue(profile.flank_lock)
        self.assertFalse(profile.transition_unlock)

    def test_available_profiles_include_baseline_and_experiments(self) -> None:
        profiles = available_experiment_profiles()
        self.assertIn("baseline", profiles)
        self.assertIn("exp_a_setplay_shield", profiles)
        self.assertIn("exp_b_flank_lock", profiles)
        self.assertIn("exp_c_box_clear", profiles)
        self.assertIn("exp_d_transition_unlock", profiles)
        self.assertIn("exp_e_box_shield", profiles)
        self.assertIn("exp_f_box_shield_transition", profiles)
        self.assertIn("exp_g_stable_box", profiles)
        self.assertIn("exp_h_stable_box_finish", profiles)
        self.assertIn("exp_i_box_finish", profiles)
        self.assertIn("exp_j_light_box_finish", profiles)
        self.assertIn("exp_k_box_finish_tight", profiles)
        self.assertIn("exp_l_light_box_finish_tight", profiles)
        self.assertIn("exp_m_box_shield_flank", profiles)


if __name__ == "__main__":
    unittest.main()
