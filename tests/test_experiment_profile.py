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

    def test_available_profiles_include_baseline_and_experiments(self) -> None:
        profiles = available_experiment_profiles()
        self.assertIn("baseline", profiles)
        self.assertIn("exp_a_setplay_shield", profiles)
        self.assertIn("exp_b_flank_lock", profiles)
        self.assertIn("exp_c_box_clear", profiles)
        self.assertIn("exp_d_transition_unlock", profiles)


if __name__ == "__main__":
    unittest.main()
