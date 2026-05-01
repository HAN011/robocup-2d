# Long Commands

This file stores long-running commands that are intended to be copied and run manually.

## Candidate 74 Weak-Team Natural High Frontline Finish Pair Validation

Purpose: candidate73 damaged Starter2D badly (`0-11`) and likely disrupted the baseline natural #9 scoring chain. Candidate74 returns to the candidate12 base shape and only adds a very narrow PlayOn finish for weak opponents: #9/#11, high natural frontline touch, x>=34, same-side channel, abs(ball.y) 7..24, and low immediate pressure. This preserves the natural buildup instead of changing restart/kickoff behavior.

Result basis:
- candidate72 clean: `starter2d` improved GA to `0-5` but stayed `GF=0`; `foxsy_cyrus` regressed to `0-20`.
- candidate73 clean: `starter2d` regressed to `0-11`; avoid kickoff-window hard second finish.
- latest baseline candidate12 naturally scored once vs Starter2D (`Aurora 1 - 7 STARTER_base`), with the known successful chain involving Aurora #9 around x=38/y=-18 before the goal.

Acceptance:
- Gate clean: no suspect matches and no disconnects.
- Primary: break `GF=0` against `starter2d`.
- Secondary: do not regress starter2d GA versus same-run baseline by more than 3.
- Diagnostic: server records are enabled so `.rcl/.rcg` can be inspected for `weak_team_natural_high_frontline_finish` labels and #9/#11 high touches.
- Success target: at least one weak opponent has `GF > 0`; ideal target is a draw/win against `starter2d`.

```bash
(
  set -euo pipefail
  trap 'pkill -P $$ || true' EXIT INT TERM
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
    RUN_LABEL=exp_p_weak_pair_recheck \
    BASE_PORT=7410 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    PARALLEL_MATCH_DISABLE_INTERNAL_FILE_LOGS=0 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_74 \
    RUN_LABEL=exp_bv_weak_team_natural_high_frontline_finish \
    BASE_PORT=7510 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    PARALLEL_MATCH_DISABLE_INTERNAL_FILE_LOGS=0 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  wait
)
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bv_weak_team_natural_high_frontline_finish_*.txt | head
```

```bash
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt | head -1)"
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_bv_weak_team_natural_high_frontline_finish_*.txt | head -1)"
```

## Candidate 73 Weak-Team Restart Second Finish Pair Validation

Purpose: candidate72 was clean and still `GF=0`, but it improved starter2d GA versus a same-run noisy baseline (`candidate_12` 0-10, candidate72 0-5) and diagnostics showed deeper attack state (`max_ball_x=44.5`, `front_kicks=5`). Candidate73 keeps candidate72's restart grounder and adds only a narrow post-kickoff second-touch finish: within 170 cycles after our kickoff, if a non-goalie kickable touch reaches x>=18 and abs(y)<=24, shoot hard to the far post. This avoids the global PlayOn hooks that damaged candidates70/71.

Result basis: clean candidate72 run on 2026-05-01 16:13:
- baseline `candidate_12`: `starter2d` Aurora 0-10, `foxsy_cyrus` Aurora 0-16
- `candidate_72`: `starter2d` Aurora 0-5, `foxsy_cyrus` Aurora 0-20
- starter2d diagnostics: candidate72 reached `max_ball_x=44.5` and `front_kicks=5`, but no conversion.

Acceptance:
- Gate clean: no suspect matches and no disconnects.
- Primary: break `GF=0` against `starter2d`.
- Secondary: do not regress starter2d GA versus same-run baseline by more than 3.
- Diagnostic: check for `weak_team_restart_second_finish` labels after our kickoff and whether shots are blocked or miss.
- Success target: at least one weak opponent has `GF > GA`; ideal target is both weak opponents win or draw.

```bash
(
  set -euo pipefail
  trap 'pkill -P $$ || true' EXIT INT TERM
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
    RUN_LABEL=exp_p_weak_pair_recheck \
    BASE_PORT=7410 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_73 \
    RUN_LABEL=exp_bu_weak_team_restart_second_finish \
    BASE_PORT=7510 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  wait
)
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bu_weak_team_restart_second_finish_*.txt | head
```

```bash
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt | head -1)"
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_bu_weak_team_restart_second_finish_*.txt | head -1)"
```

## Candidate 72 Weak-Team Restart Grounder Pair Validation

Purpose: candidate71 was clean but still `GF=0` and regressed badly (`starter2d` 0-7 vs baseline 0-4, `foxsy_cyrus` 0-23 vs baseline 0-16). The PlayOn hooks did not produce visible action labels and repeatedly disturbed natural chains. Candidate72 stops touching PlayOn and only changes our weak-team kick_off/corner restarts into a controlled ground pass toward #9/#10/#11, while keeping candidate12's normal buildup and not enabling `weak_team_killer`.

Result basis: clean candidate71 run on 2026-05-01 15:59:
- baseline `candidate_12`: `starter2d` Aurora 0-4, `foxsy_cyrus` Aurora 0-16
- `candidate_71`: `starter2d` Aurora 0-7, `foxsy_cyrus` Aurora 0-23
- no useful `weak_team_deep_cutback`/`weak_team_deep_far_post_finish` labels observed, so direct PlayOn hooks are not solving the GF=0 bottleneck.

Acceptance:
- Gate clean: no suspect matches and no disconnects.
- Primary: break `GF=0` against at least one weak opponent.
- Secondary: do not regress starter2d GA versus same-run baseline by more than 3.
- Diagnostic: check for `weak_team_kickoff_grounder` / `weak_team_corner_grounder` labels and whether post-restart ball reaches x>=20.
- Success target: at least one weak opponent has `GF > GA`; ideal target is both weak opponents win or draw.

```bash
(
  set -euo pipefail
  trap 'pkill -P $$ || true' EXIT INT TERM
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
    RUN_LABEL=exp_p_weak_pair_recheck \
    BASE_PORT=7410 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_72 \
    RUN_LABEL=exp_bt_weak_team_restart_grounder \
    BASE_PORT=7510 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  wait
)
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bt_weak_team_restart_grounder_*.txt | head
```

```bash
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt | head -1)"
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_bt_weak_team_restart_grounder_*.txt | head -1)"
```

## Candidate 71 Weak-Team Deep Cutback Pair Validation

Purpose: candidate70 was clean but still `GF=0` and interfered with starter2d's natural attack chain. Same-run baseline had `starter2d` Aurora 0-5 with natural deep possession, while candidate70 was 0-6 and diagnostics dropped from `opp_half_kicks=37/front_kicks=11/max_ball_x=52.4` to `opp_half_kicks=10/front_kicks=1/max_ball_x=50.5`. Candidate71 keeps candidate12's buildup untouched and only acts after a natural front-third touch at x>=28: cut back to a central #9/#10/#11 if available, otherwise use a far-post finish from x>=32.

Result basis: clean candidate70 run on 2026-05-01 15:43:
- baseline `candidate_12`: `starter2d` Aurora 0-5, `foxsy_cyrus` Aurora 0-17
- `candidate_70`: `starter2d` Aurora 0-6, `foxsy_cyrus` Aurora 0-17
- no `weak_team_natural_channel_feed` label was observed in player logs; RCG/RCL diagnostics show the middle-third hook disturbed natural starter2d progression.

Acceptance:
- Gate clean: no suspect matches and no disconnects.
- Primary: break `GF=0` against `starter2d`, where natural front-third touches exist.
- Secondary: do not reduce starter2d front-third kicks versus same-run baseline.
- Diagnostic: if GF stays zero, inspect `weak_team_deep_cutback`/`weak_team_deep_far_post_finish` labels and the deepest kick cycles.
- Success target: at least one weak opponent has `GF > GA`; ideal target is both weak opponents win or draw.

```bash
(
  set -euo pipefail
  trap 'pkill -P $$ || true' EXIT INT TERM
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
    RUN_LABEL=exp_p_weak_pair_recheck \
    BASE_PORT=7410 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_71 \
    RUN_LABEL=exp_bs_weak_team_deep_cutback \
    BASE_PORT=7510 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  wait
)
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bs_weak_team_deep_cutback_*.txt | head
```

```bash
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt | head -1)"
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_bs_weak_team_deep_cutback_*.txt | head -1)"
```

## Candidate 70 Weak-Team Natural Channel Feed Pair Validation

Purpose: candidate69 kept the candidate12 shape and improved `foxsy_cyrus` GA, but still had `GF=0` and regressed `starter2d` from baseline `0-9` to `0-14`. The next hypothesis is that direct finish hooks are too late and too blocked; candidate70 keeps the candidate12 shape and only adds a narrow weak-team PlayOn feed when #9/#10/#11 has already naturally moved ahead of the ball in the x=6..24 band.

Result basis: clean candidate69 run on 2026-05-01 15:22:
- baseline `candidate_12`: `starter2d` Aurora 0-9, `foxsy_cyrus` Aurora 0-25
- `candidate_69`: `starter2d` Aurora 0-14, `foxsy_cyrus` Aurora 0-18
- diagnostics showed starter2d `front_third=0` for both, with candidate69 reducing max ball x from 36.5 to 33.7.

Acceptance:
- Gate clean: no suspect matches and no disconnects.
- Primary: break `GF=0` against at least one weak opponent.
- Secondary: do not regress starter2d GA versus same-run baseline by more than 3.
- Diagnostic: if GF stays zero, inspect whether `weak_team_natural_channel_feed` appears in RCL/debug and whether the receiver reaches x>=28.
- Success target: at least one weak opponent has `GF > GA`; ideal target is both weak opponents win or draw.

```bash
(
  set -euo pipefail
  trap 'pkill -P $$ || true' EXIT INT TERM
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
    RUN_LABEL=exp_p_weak_pair_recheck \
    BASE_PORT=7410 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_70 \
    RUN_LABEL=exp_br_weak_team_natural_channel_feed \
    BASE_PORT=7510 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  wait
)
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt results/parallel_fixed_baseline_exp_br_weak_team_natural_channel_feed_*.txt | head
```

```bash
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt | head -1)"
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_br_weak_team_natural_channel_feed_*.txt | head -1)"
```

## Candidate 69 Weak-Team Natural Frontline Finish Pair Validation

Purpose: candidate68 was clean but still failed: `starter2d` was `0-7` vs baseline `0-6`, and `foxsy_cyrus` was `0-19` vs baseline `0-16`. RCG inspection showed candidate68 reduced natural starter2d front-third kicks from baseline `4` to `1`, so the high-slot/press/restart-channel stack is disrupting the best existing attack chain. Candidate69 reverts to the candidate12 shape and only adds the weak-team #9/#10/#11 x>=26 post-finish hook for natural front-line touches.

Result basis: clean candidate68 run on 2026-05-01 15:06:
- baseline `candidate_12`: `starter2d` Aurora 0-6, `foxsy_cyrus` Aurora 0-16
- `candidate_68`: `starter2d` Aurora 0-7, `foxsy_cyrus` Aurora 0-19
- baseline naturally produced `front_third=4` starter2d kicks; candidate68 dropped to `front_third=1`.

Acceptance:
- Gate clean: no suspect matches and no disconnects.
- Primary: break `GF=0` against at least one weak opponent without reducing starter2d front-third touches.
- Diagnostic: if natural front-third touches remain but GF is zero, next step should add a cutback/pass option around x=28-36 rather than more formation pressure.
- Success target: at least one weak opponent has `GF > GA`; ideal target is both weak opponents win or draw.

```bash
(
  set -euo pipefail
  trap 'pkill -P $$ || true' EXIT INT TERM
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
    RUN_LABEL=exp_p_weak_pair_recheck \
    BASE_PORT=7410 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_69 \
    RUN_LABEL=exp_bq_weak_team_natural_frontline_finish \
    BASE_PORT=7510 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  wait
)
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bq_weak_team_natural_frontline_finish_*.txt | head
```

```bash
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt | head -1)"
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_bq_weak_team_natural_frontline_finish_*.txt | head -1)"
```

## Candidate 68 Weak-Team Frontline Post-Finish Pair Validation

Purpose: candidate67 was clean but failed: `starter2d` regressed from baseline `0-8` to `0-14`, and `foxsy_cyrus` stayed `GF=0` (`0-24`). RCG/RCL inspection showed the x>=24 shot did trigger, but #11's central goal-bound ball from x≈26/y≈11 was blocked by STARTER #3 around x≈36/y≈1. Candidate68 keeps candidate66's high frontline slots, removes candidate67's generic front-third shooter, and only lets #9/#10/#11 finish from x>=26 toward the same-side post lane.

Result basis: clean candidate67 run on 2026-05-01 14:47:
- baseline `candidate_12`: `starter2d` Aurora 0-8, `foxsy_cyrus` Aurora 0-27
- `candidate_67`: `starter2d` Aurora 0-14, `foxsy_cyrus` Aurora 0-24
- candidate67 had starter2d front-third kicks but no goal; the main high chance was blocked centrally.

Acceptance:
- Gate clean: no suspect matches and no disconnects.
- Primary: break `GF=0` against at least one weak opponent.
- Diagnostic: starter2d should retain front-third kicks without increasing GA versus candidate66; if GF remains zero and shots are blocked, next step should create a cross/cutback or change formation starts rather than more direct shots.
- Success target: at least one weak opponent has `GF > GA`; ideal target is both weak opponents win or draw.

```bash
(
  set -euo pipefail
  trap 'pkill -P $$ || true' EXIT INT TERM
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
    RUN_LABEL=exp_p_weak_pair_recheck \
    BASE_PORT=7410 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_68 \
    RUN_LABEL=exp_bp_weak_team_frontline_post_finish \
    BASE_PORT=7510 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  wait
)
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bp_weak_team_frontline_post_finish_*.txt | head
```

```bash
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt | head -1)"
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_bp_weak_team_frontline_post_finish_*.txt | head -1)"
```

## Candidate 67 Weak-Team Front-Third Finish Pair Validation

Purpose: candidate66 was clean and finally created a starter2d front-third Aurora kick, but still ended `GF=0`. Candidate67 keeps candidate66's high frontline slots and restart channel, then adds a narrow front-third finish trigger: when a weak-team touch reaches x>=24, shoot immediately at goal instead of falling back to default kick/pass behavior.

Result basis: clean candidate66 run on 2026-05-01 14:29:
- baseline `candidate_12`: `starter2d` Aurora 0-7, `foxsy_cyrus` Aurora 0-17
- `candidate_66`: `starter2d` Aurora 0-7, `foxsy_cyrus` Aurora 0-21
- candidate66 produced the first front-third touch signal against starter2d, but no goal.

Acceptance:
- Gate clean: no suspect matches and no disconnects.
- Primary: break `GF=0` against at least one weak opponent.
- Diagnostic: if starter2d front-third kicks still appear but GF remains zero, inspect shot target and keeper position; if front-third kicks disappear, rollback this finish trigger and change actual formation/start positions.
- Success target: at least one weak opponent has `GF > GA`; ideal target is both weak opponents win or draw.

```bash
(
  set -euo pipefail
  trap 'pkill -P $$ || true' EXIT INT TERM
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
    RUN_LABEL=exp_p_weak_pair_recheck \
    BASE_PORT=7410 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_67 \
    RUN_LABEL=exp_bo_weak_team_front_third_finish \
    BASE_PORT=7510 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  wait
)
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bo_weak_team_front_third_finish_*.txt | head
```

```bash
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt | head -1)"
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_bo_weak_team_front_third_finish_*.txt | head -1)"
```

## Candidate 66 Weak-Team Frontline-Slots Pair Validation

Purpose: candidate65 was clean and improved starter2d defense to `0-5`, but still had `GF=0`. Kick analysis showed restart-channel reached only x≈19 and still produced `0` front-third kicks. Candidate66 keeps the restart channel and weak-team finish gate, but moves #9/#10/#11 into explicit high receiving slots (x≈30-35) when they are not the chaser; kickoff channel targets those slots directly.

Result basis: clean candidate65 run on 2026-05-01 14:11:
- baseline `candidate_12`: `starter2d` Aurora 0-10, `foxsy_cyrus` Aurora 0-19
- `candidate_65`: `starter2d` Aurora 0-5, `foxsy_cyrus` Aurora 0-19
- candidate65 failed the scoring target and did not create front-third touches.

Acceptance:
- Gate clean: no suspect matches and no disconnects.
- Primary: produce front-third Aurora kicks and break `GF=0` against at least one weak opponent.
- Success target: at least one weak opponent has `GF > GA`; ideal target is both weak opponents win or draw.
- If front-third kicks appear but GF remains zero, next step should adjust finishing from x=30-40. If they do not appear, change actual formation files/start positions.

```bash
(
  set -euo pipefail
  trap 'pkill -P $$ || true' EXIT INT TERM
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
    RUN_LABEL=exp_p_weak_pair_recheck \
    BASE_PORT=7410 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_66 \
    RUN_LABEL=exp_bn_weak_team_frontline_slots \
    BASE_PORT=7510 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  wait
)
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bn_weak_team_frontline_slots_*.txt | head
```

```bash
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt | head -1)"
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_bn_weak_team_frontline_slots_*.txt | head -1)"
```

## Candidate 65 Weak-Team Restart-Channel Pair Validation

Purpose: candidate64's play-on channel entry was clean but failed: starter2d worsened to `0-9`, foxsy stayed `0-21`, and kick analysis still showed `0` front-third kicks. Candidate65 returns to a restart-specific entry: against weak teams, our kickoff/corner no longer direct-shoots; it sends a controlled channel ball to #10/#11's x=14-26 lane, then uses weak-team-killer's loose finish conditions once play resumes.

Result basis: clean candidate64 run on 2026-05-01 13:56:
- baseline `candidate_12`: `starter2d` Aurora 0-8, `foxsy_cyrus` Aurora 0-21
- `candidate_64`: `starter2d` Aurora 0-9, `foxsy_cyrus` Aurora 0-21
- candidate64 failed the scoring target and did not create front-third touches.

Acceptance:
- Gate clean: no suspect matches and no disconnects.
- Primary: break `GF=0` against at least one weak opponent.
- Diagnostic: kickoff/corner should show channel-entry kicks instead of direct shots; front-third Aurora kicks should appear after restarts.
- Success target: at least one weak opponent has `GF > GA`; ideal target is both weak opponents win or draw.

```bash
(
  set -euo pipefail
  trap 'pkill -P $$ || true' EXIT INT TERM
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
    RUN_LABEL=exp_p_weak_pair_recheck \
    BASE_PORT=7410 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_65 \
    RUN_LABEL=exp_bm_weak_team_restart_channel \
    BASE_PORT=7510 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  wait
)
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bm_weak_team_restart_channel_*.txt | head
```

```bash
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt | head -1)"
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_bm_weak_team_restart_channel_*.txt | head -1)"
```

## Candidate 64 Weak-Team Channel-Entry Pair Validation

Purpose: candidate63 was clean and improved starter2d defense to `0-3`, but still had `GF=0`. Kick-coordinate analysis showed candidate63 raised starter2d opponent-half kicks from `2` to `11`, but still had `0` front-third kicks; foxsy_cyrus had `0` opponent-half kicks. The earlier baseline goal chain reached `x=28-37` through #8 -> #10/#11 touches. Candidate64 adds a weak-team gated channel-entry ball from controlled midfield touches into #10/#11's front-third lane, without forcing direct shots.

Result basis: clean candidate63 run on 2026-05-01 13:42:
- baseline `candidate_12`: `starter2d` Aurora 0-8, `foxsy_cyrus` Aurora 0-14
- `candidate_63`: `starter2d` Aurora 0-3, `foxsy_cyrus` Aurora 0-21
- candidate63 failed the scoring target: `GF=0` against both weak opponents.

Acceptance:
- Gate clean: no suspect matches and no disconnects.
- Primary: generate at least one front-third Aurora kick and break `GF=0` against at least one weak opponent.
- Success target: at least one weak opponent has `GF > GA`; ideal target is both weak opponents win or draw.
- If front-third kicks appear but GF stays zero, next step should change final shot/finish from x=28-38. If front-third kicks stay zero, next step should make restart/kickoff entry explicit.

```bash
(
  set -euo pipefail
  trap 'pkill -P $$ || true' EXIT INT TERM
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
    RUN_LABEL=exp_p_weak_pair_recheck \
    BASE_PORT=7410 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_64 \
    RUN_LABEL=exp_bl_weak_team_channel_entry \
    BASE_PORT=7510 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  wait
)
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bl_weak_team_channel_entry_*.txt | head
```

```bash
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt | head -1)"
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_bl_weak_team_channel_entry_*.txt | head -1)"
```

## Candidate 63 Weak-Team Press-Intercept Pair Validation

Purpose: candidate62 was clean and cut starter2d GA from `12` to `6`, but still scored `GF=0`. Log analysis showed candidate62 reduced Aurora starter2d kicks to `96` and had `0` front-third kicks, while the earlier paired baseline that accidentally scored had `178` kicks and `9` front-third kicks. Candidate63 keeps candidate62's weak-team pressure, but lets #9/#10/#11 chase the ball first when they are fastest or near-fastest, so pressure does not steal reachable touches.

Result basis: clean candidate62 run on 2026-05-01 13:26:
- baseline `candidate_12`: `starter2d` Aurora 0-12, `foxsy_cyrus` Aurora 0-16
- `candidate_62`: `starter2d` Aurora 0-6, `foxsy_cyrus` Aurora 0-17
- candidate62 failed the primary scoring target: `GF=0` against both weak opponents.

Acceptance:
- Gate clean: no suspect matches and no disconnects.
- Primary: increase front-third Aurora kicks and break `GF=0` against at least one weak opponent.
- Success target: at least one weak opponent has `GF > GA`; ideal target is both weak opponents win or draw.
- If GF remains zero but front-third kicks rise, next step should alter final-ball/shot target. If front-third kicks stay zero, next step should change formation/restart entry rather than shots.

```bash
(
  set -euo pipefail
  trap 'pkill -P $$ || true' EXIT INT TERM
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
    RUN_LABEL=exp_p_weak_pair_recheck \
    BASE_PORT=7410 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_63 \
    RUN_LABEL=exp_bk_weak_team_press_intercept \
    BASE_PORT=7510 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  wait
)
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bk_weak_team_press_intercept_*.txt | head
```

```bash
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt | head -1)"
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_bk_weak_team_press_intercept_*.txt | head -1)"
```

## Candidate 62 Weak-Team Press-Only Pair Validation

Purpose: candidate61 scored worse than its paired baseline against `starter2d`; `.rcl` showed the forced one-step overdrive reduced Aurora touches (`45` kicks vs baseline `178` on the starter2d match). Candidate62 removes the on-ball override and keeps default `BhvKick` possession play, while only pushing weak-team off-ball pressure from 6-11 into attacking slots.

Result basis:
- candidate60 clean weak-pair run on 2026-05-01 12:54 improved `foxsy_cyrus` GA but kept `GF=0`.
- candidate61 clean weak-pair run on 2026-05-01 13:11 failed the scoring target and reduced starter2d GF versus paired baseline.
- Baseline's one starter2d goal came from front-field pressure/mixed default touches around cycles 3686-3721, not from a direct overdrive shot.

Acceptance:
- Gate clean: no suspect matches and no disconnects.
- Primary: `candidate_62` must break `GF=0` against at least one weak opponent.
- Success target: at least one weak opponent has `GF > GA`; ideal target is both weak opponents win or draw.
- If GF remains zero, inspect front-three kickoff and default `BhvKick` target choices rather than returning to forced direct shots.

```bash
(
  set -euo pipefail
  trap 'pkill -P $$ || true' EXIT INT TERM
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
    RUN_LABEL=exp_p_weak_pair_recheck \
    BASE_PORT=7410 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_62 \
    RUN_LABEL=exp_bj_weak_team_press_only \
    BASE_PORT=7510 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  wait
)
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bj_weak_team_press_only_*.txt | head
```

```bash
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt | head -1)"
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_bj_weak_team_press_only_*.txt | head -1)"
```

## Candidate 61 Weak-Team Overdrive Pair Validation

Purpose: candidate60 produced a clean weak-pair run but still scored `GF=0` against both weak opponents. Candidate61 keeps the same weak-team gate and adds a stronger on-ball overdrive: non-goalie weak-team possessions in playable attacking zones are forced into one-step direct attacks, and 6-11 push higher off-ball.

Result basis: clean candidate60 run on 2026-05-01 12:54:
- baseline `candidate_12`: `starter2d` Aurora 0-3, `foxsy_cyrus` Aurora 0-20
- `candidate_60`: `starter2d` Aurora 0-3, `foxsy_cyrus` Aurora 0-13

Acceptance:
- Gate clean: no suspect matches and no disconnects.
- Primary: break `GF=0` against at least one weak opponent.
- Success target: at least one weak opponent has `GF > GA`; ideal target is both weak opponents win or draw.
- If GF remains zero, inspect `.rcl` Aurora kick directions and add a kickoff/formation-specific front-three start package.

```bash
(
  set -euo pipefail
  trap 'pkill -P $$ || true' EXIT INT TERM
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
    RUN_LABEL=exp_p_weak_pair_recheck \
    BASE_PORT=7410 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_61 \
    RUN_LABEL=exp_bi_weak_team_overdrive \
    BASE_PORT=7510 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  wait
)
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bi_weak_team_overdrive_*.txt | head
```

```bash
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt | head -1)"
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_bi_weak_team_overdrive_*.txt | head -1)"
```

## Candidate 60 Weak-Team Killer Pair Validation

Purpose: switch from the prior 6-opponent GA gate to the aggressive weak-team scoring target from `一天激进赢球策略_稳定打败弱队.md`. Compare `candidate_12` against `candidate_60` only on `starter2d` and `foxsy_cyrus`, using low concurrency and explicit cleanup.

Acceptance:
- Gate clean: no suspect matches and no disconnects.
- Primary: `candidate_60` should improve GF against `starter2d` and/or `foxsy_cyrus`.
- Success target: at least one weak opponent has `GF > GA`; ideal target is both weak opponents win or draw.
- If GF remains zero, inspect whether the weak-team shoot/restart branches are being reached before adding the next attack tactic.

```bash
(
  set -euo pipefail
  trap 'pkill -P $$ || true' EXIT INT TERM
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
    RUN_LABEL=exp_p_weak_pair_recheck \
    BASE_PORT=7410 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  (
    BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus" \
    ROBOCUP_EXPERIMENT_PROFILE=candidate_60 \
    RUN_LABEL=exp_bh_weak_team_killer \
    BASE_PORT=7510 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  wait
)
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bh_weak_team_killer_*.txt | head
```

```bash
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt | head -1)"
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_bh_weak_team_killer_*.txt | head -1)"
```

## Candidate 52 Paired Fixed-Pool Validation

Purpose: compare current best `candidate_12` against `candidate_52` with lower gate-risk total parallelism 2.

Result basis: `candidate_51` had a clean paired run on 2026-05-01 11:45:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260501_114506_1855404.txt`
- `results/parallel_fixed_baseline_exp_bd_kickoff_central_entry_stopper_20260501_114506_1855405.txt`

That run failed the 20% gate: valid paired GA was `candidate_12=109`, `candidate_51=100`, only `8.26%`. Goal-chain showed the global stopper preserved kickoff gains (`kick_off -14`, `flank_kickoff_entry -13`, `center_kickoff_midfield_gap -10`) but migrated into `center_kickoff_entry +9` and `flank_setplay_entry +5`. Opponent-level raw GA showed the stopper helped `foxsy_cyrus -4` and `starter2d -5`, while hurting `cyrus_team +2`. `candidate_52` returns to the candidate47 base and enables the central entry stopper only for `foxsy_cyrus` and `starter2d`.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_52` total GA must be at least 20% lower than the paired `candidate_12` run.
- Preserve candidate47 gains on Cyrus-like kickoff: `cyrus2d` and `cyrus_team` should not lose GA versus paired `candidate_12`.
- Keep candidate51 selective gains: `foxsy_cyrus` and `starter2d` should improve without raising `flank_setplay_entry`.
- Avoid global-stopper failure: no large rise in `center_kickoff_entry` or `flank_setplay_entry` versus paired `candidate_12`.

```bash
(
  set -euo pipefail
  trap 'pkill -P $$ || true' EXIT INT TERM
  (
    ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
    RUN_LABEL=exp_p_current_pair_recheck \
    BASE_PORT=7410 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  (
    ROBOCUP_EXPERIMENT_PROFILE=candidate_52 \
    RUN_LABEL=exp_be_selective_kickoff_entry_stopper \
    BASE_PORT=7510 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  wait
)
pgrep -af 'rcssserver|run_parallel_fixed_baseline|run_match.sh|player/main.py|coach/main.py|sample_player|sample_coach|HELIOS|helios|cyrus|wrighteagle|starter' || true
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_be_selective_kickoff_entry_stopper_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_be_selective_kickoff_entry_stopper_*.txt
```

## Candidate 51 Paired Fixed-Pool Validation

Result: failed on clean run 2026-05-01 11:45. Valid paired GA was `candidate_12=109`, `candidate_51=100`, an `8.26%` reduction. It reduced total kickoff GA but migrated into `center_kickoff_entry +9` and `flank_setplay_entry +5`; use `candidate_52` selective gate.

Purpose: compare current best `candidate_12` against `candidate_51` with lower gate-risk total parallelism 2.

Result basis: `candidate_50` had a clean paired run on 2026-05-01 10:59:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260501_105901_1720997.txt`
- `results/parallel_fixed_baseline_exp_bc_strict_kickoff_context_20260501_105901_1720998.txt`

That run failed the 20% gate: valid paired GA was `candidate_12=99`, `candidate_50=94`, a `5.05%` reduction. Goal-chain showed strict context helped `flank_setplay_entry -5` and `flank_kickoff_entry -4`, but migrated into the same main residual: `center_kickoff_entry +11` and `nearest_our_band goalie +21`. `candidate_51` returns to the candidate47 base and adds only `kickoff_central_entry_stopper`: after our kickoff, when the ball is in the narrow central penalty-arc entry lane, one center back blocks the arc-entry seam ahead of the box. It avoids broad terminal clear, second-line 6/7/8 pulls, goalpost guard, and strict context.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_51` total GA must be at least 20% lower than the paired `candidate_12` run.
- Preserve candidate47 kickoff gains: total `kick_off`, `flank_kickoff_entry`, and `center_kickoff_midfield_gap` below paired `candidate_12`.
- Reduce candidate47/50 residual: `center_kickoff_entry` should drop materially without increasing `nearest_our_band=goalie`.
- Avoid candidate48/49 failure modes: no increase in `flank_kickoff_entry`, `flank_setplay_entry`, or `center_setplay_entry` versus paired `candidate_12`.

```bash
(
  set -euo pipefail
  trap 'pkill -P $$ || true' EXIT INT TERM
  (
    ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
    RUN_LABEL=exp_p_current_pair_recheck \
    BASE_PORT=7410 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  (
    ROBOCUP_EXPERIMENT_PROFILE=candidate_51 \
    RUN_LABEL=exp_bd_kickoff_central_entry_stopper \
    BASE_PORT=7510 \
    PARALLEL_JOBS=1 \
    SAFE_PARALLEL_JOBS=1 \
    FAIL_ON_SUSPECT=1 \
    ./scripts/run_parallel_fixed_baseline.sh 1
  ) &
  wait
)
pgrep -af 'rcssserver|run_parallel_fixed_baseline|run_match.sh|player/main.py|coach/main.py|sample_player|sample_coach|HELIOS|helios|cyrus|wrighteagle|starter' || true
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bd_kickoff_central_entry_stopper_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bd_kickoff_central_entry_stopper_*.txt
```

## Candidate 50 Paired Fixed-Pool Validation

Purpose: compare current best `candidate_12` against `candidate_50` with lower gate-risk total parallelism 2.

Result basis: `candidate_49` had a clean paired run on 2026-05-01 10:14:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260501_101402_1598635.txt`
- `results/parallel_fixed_baseline_exp_bb_kickoff_central_second_line_screen_20260501_101402_1598636.txt`

That run failed: valid paired GA was `candidate_12=89`, `candidate_49=93`, a `4.49%` regression. Goal-chain showed the added second-line screen removed the small `center_kickoff_midfield_gap` bucket (`-4`) but migrated failures into `center_kickoff_entry +7`, `flank_kickoff_entry +4`, and `flank_setplay_entry +4`. `candidate_50` therefore discards the second-line screen and returns to the candidate47 base, adding only `strict_kickoff_context`: if any non-kickoff restart occurs after our kickoff, subsequent PlayOn cycles no longer activate kickoff counterpress/lane/anchor/terminal behaviors from the stale kickoff window.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_50` total GA must be at least 20% lower than the paired `candidate_12` run.
- Preserve candidate47 kickoff gains: `flank_kickoff_entry`, `center_kickoff_midfield_gap`, and total `kick_off` below paired `candidate_12`.
- Reduce migration risk: `setplay` and `other` restart-context GA should not rise above paired `candidate_12`.
- Do not reproduce candidate49: no increase in `center_kickoff_entry`, `flank_kickoff_entry`, or `flank_setplay_entry` versus paired `candidate_12`.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_50 \
  RUN_LABEL=exp_bc_strict_kickoff_context \
  BASE_PORT=7510 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bc_strict_kickoff_context_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bc_strict_kickoff_context_*.txt
```

## Candidate 49 Paired Fixed-Pool Validation

Result: failed on clean run 2026-05-01 10:14. Valid paired GA was `candidate_12=89`, `candidate_49=93`, a `4.49%` regression. It reduced `center_kickoff_midfield_gap` but regressed `center_kickoff_entry`, `flank_kickoff_entry`, and `flank_setplay_entry`; use `candidate_50`.

Purpose: compare current best `candidate_12` against `candidate_49` with lower gate-risk total parallelism 2.

Result basis: `candidate_48` had a clean paired run on 2026-05-01 09:21:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260501_092159_1459168.txt`
- `results/parallel_fixed_baseline_exp_ba_narrow_kickoff_center_entry_clear_20260501_092159_1459169.txt`

That run failed the 20% gate: valid paired GA was `candidate_12=101`, `candidate_48=94`, only `6.93%`. Goal-chain showed the narrow terminal clear reduced `center_kickoff_entry` versus candidate47 (`21 -> 17`) but introduced a bad terminal shape: `flank_kickoff_entry +5`, `center_setplay_entry +6`, and `nearest_our_band=goalie +21`. `candidate_49` therefore returns to the candidate47 base and adds only `kickoff_central_second_line_screen`: after our kickoff, central/deep central ball, no teammate kickable, non-fastest 6/7/8 form a narrow arc-top second line. It does not enable `narrow_kickoff_center_entry_clear`, `kickoff_flank_goalpost_guard`, backline shelf, or any goalmouth lock.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_49` total GA must be at least 20% lower than the paired `candidate_12` run.
- Preserve candidate47 gains: `center_kickoff_midfield_gap`, `flank_kickoff_entry`, and total `kick_off` below paired `candidate_12`.
- Reduce candidate47 residual without terminal regression: `center_kickoff_entry` should drop materially from candidate47's 21, while `nearest_our_band=goalie` must not rise above paired `candidate_12`.
- Avoid candidate48 failure mode: no increase in `flank_kickoff_entry` or `center_setplay_entry` versus paired `candidate_12`.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_49 \
  RUN_LABEL=exp_bb_kickoff_central_second_line_screen \
  BASE_PORT=7510 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bb_kickoff_central_second_line_screen_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bb_kickoff_central_second_line_screen_*.txt
```

## Candidate 48 Paired Fixed-Pool Validation

Result: failed 20% gate on clean run 2026-05-01 09:21. Valid paired GA was `candidate_12=101`, `candidate_48=94`, a `6.93%` reduction. It reduced some center kickoff entry but regressed flank kickoff, center setplay, and goalie-nearest terminal shape; use `candidate_49`.

Purpose: compare current best `candidate_12` against `candidate_48` with lower gate-risk total parallelism 2.

Result basis: `candidate_47` had a clean paired run on 2026-05-01 08:38:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260501_083817_1335994.txt`
- `results/parallel_fixed_baseline_exp_az_central_setplay_no_goalpost_20260501_083817_1335995.txt`

That run improved GA from `109 -> 93` (`14.68%`) but missed the 20% gate by about 6 GA. It confirmed that removing the goalpost/backline terminal line was right: `flank_kickoff_entry -18`, `center_kickoff_midfield_gap -13`, `kick_off -19`, with gains on `cyrus_team -8`, `cyrus2d -5`, `starter2d -3`, `helios -2`. The largest remaining regression is `center_kickoff_entry +12` (`21` total). `candidate_48` keeps candidate47 and adds only `narrow_kickoff_center_entry_clear`: a short-window, central-only one-step clear/lane block after our kickoff, limited to the penalty-area entry lane (`abs(y)<=9`) to avoid candidate42's broad terminal-guard regression.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_48` total GA must be at least 20% lower than the paired `candidate_12` run.
- Preserve candidate47 flank kickoff win: `flank_kickoff_entry` and total `kick_off` below paired `candidate_12`.
- Reduce candidate47 residual: `center_kickoff_entry` should drop by at least 6 versus candidate47's 21.
- Do not revive terminal-goalmouth failure: `nearest_our_band=goalie` should not jump above paired `candidate_12`.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_48 \
  RUN_LABEL=exp_ba_narrow_kickoff_center_entry_clear \
  BASE_PORT=7510 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ba_narrow_kickoff_center_entry_clear_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ba_narrow_kickoff_center_entry_clear_*.txt
```

## Candidate 47 Paired Fixed-Pool Validation

Result: failed 20% gate on clean run 2026-05-01 08:38. Valid paired GA was `candidate_12=109`, `candidate_47=93`, a `14.68%` reduction. It was strong but left `center_kickoff_entry=21`; use `candidate_48`.

Purpose: compare current best `candidate_12` against `candidate_47` with lower gate-risk total parallelism 2.

Result basis: `candidate_46` had a clean paired run on 2026-05-01 07:56:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260501_075656_1210708.txt`
- `results/parallel_fixed_baseline_exp_ay_kickoff_flank_backline_shelf_20260501_075656_1210709.txt`

That run improved GA from `101 -> 93` (`7.92%`) but missed the gate. Goal-chain showed it kept central structural gains (`center_kickoff_midfield_gap -23`, `center_midfield_gap -7`) and setplay gain (`flank_setplay_entry -8`), but worsened terminal kickoff/flank shape (`flank_kickoff_entry +10`, `center_kickoff_entry +12`, `nearest_our_band goalie +56`). This matches the earlier candidate41/44/45 pattern: terminal goalpost/goalmouth lines tend to leave the goalie as the nearest defender. `candidate_47` therefore removes the goalpost/backline/lock terminal line and tests the cleaner combination: `candidate_39` + `opponent_central_setplay_wall`.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_47` total GA must be at least 20% lower than the paired `candidate_12` run.
- Preserve candidate39/candidate43 central gains: `center_kickoff_midfield_gap` and `center_midfield_gap` below paired `candidate_12`.
- Recover candidate39's defender-nearest shape: `nearest_our_band=goalie` must not jump like candidate46.
- Avoid candidate41/43 setplay regression: `center_setplay_entry` should not exceed paired `candidate_12`.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_47 \
  RUN_LABEL=exp_az_central_setplay_no_goalpost \
  BASE_PORT=7510 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_az_central_setplay_no_goalpost_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_az_central_setplay_no_goalpost_*.txt
```

## Candidate 46 Paired Fixed-Pool Validation

Result: failed 20% gate on clean run 2026-05-01 07:56. Valid paired GA was `candidate_12=101`, `candidate_46=93`, a `7.92%` reduction. It regressed terminal kickoff/flank shape (`flank_kickoff_entry +10`, `center_kickoff_entry +12`, `nearest_our_band goalie +56`); use `candidate_47`.

Purpose: compare current best `candidate_12` against `candidate_46` with lower gate-risk total parallelism 2.

Result basis: `candidate_45` had a clean paired run on 2026-05-01 07:13:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260501_071346_1092458.txt`
- `results/parallel_fixed_baseline_exp_ax_opponent_flank_restart_lock_20260501_071346_1092459.txt`

That run failed: `candidate_12=96`, `candidate_45=102`, a `6.25%` GA increase. It reduced setplay (`setplay -14`, `flank_setplay_entry -6`) but again damaged kickoff/late flank structure (`kick_off +11`, `flank_kickoff_entry +9`, `flank_box_entry +8`, `nearest_our_band goalie +22`), concentrated in `cyrus_team +7` and `foxsy_cyrus +5`. `candidate_46` abandons the PlayOn goalmouth-lock line and returns to the clean `candidate_43` package. It adds only `kickoff_flank_backline_shelf`: after our kickoff and deep-wide reentry, far-side defenders/mids form a backline shelf behind the existing goalpost guard, before generic lane lockdown. The intent is to reduce the remaining `flank_kickoff_entry` bucket without repeating candidate44/45's terminal-lock regression.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_46` total GA must be at least 20% lower than the paired `candidate_12` run.
- Preserve candidate43's central structure: `center_kickoff_midfield_gap` and `center_midfield_gap` below paired `candidate_12`.
- Improve candidate43's largest remaining bucket: `flank_kickoff_entry` should drop by at least 8 versus paired `candidate_12`, without increasing total `kick_off`.
- Do not reproduce candidate45: `cyrus_team`, `foxsy_cyrus`, `flank_box_entry`, and `nearest_our_band=goalie` must not move materially above paired `candidate_12`.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_46 \
  RUN_LABEL=exp_ay_kickoff_flank_backline_shelf \
  BASE_PORT=7510 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ay_kickoff_flank_backline_shelf_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ay_kickoff_flank_backline_shelf_*.txt
```

## Candidate 45 Paired Fixed-Pool Validation

Result: failed on clean run 2026-05-01 07:13. Valid paired GA was `candidate_12=96`, `candidate_45=102`, a `6.25%` increase. It reduced setplay but regressed kickoff/late flank structure; use `candidate_46`.

Purpose: compare current best `candidate_12` against `candidate_45` with lower gate-risk total parallelism 2.

Result basis: `candidate_44` had a clean paired run on 2026-05-01 06:32:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260501_063226_971197.txt`
- `results/parallel_fixed_baseline_exp_aw_flank_restart_goalmouth_lock_20260501_063226_971198.txt`

That run failed badly: `candidate_12=93`, `candidate_44=102`, a `9.68%` GA increase. It reduced setplay (`flank_setplay_entry -8`, total `setplay -7`) but exploded kickoff (`kick_off +19`, `flank_kickoff_entry +15`, `center_kickoff_entry +7`) across `cyrus2d +4`, `cyrus_team +4`, `helios +3`, and `foxsy_cyrus +2`. `candidate_45` keeps `candidate_43` and changes the candidate44 idea into `opponent_flank_restart_goalmouth_lock`: a narrow post-opponent-flank-restart PlayOn lock only. It does not activate after our kickoff.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_45` total GA must be at least 20% lower than the paired `candidate_12` run.
- Retain the candidate43 structural gain: `center_kickoff_midfield_gap` and `center_midfield_gap` below paired `candidate_12`.
- Fix the candidate43 residual without repeating candidate44: `flank_setplay_entry` should drop, while `kick_off`, `flank_kickoff_entry`, and `center_kickoff_entry` must not exceed paired `candidate_12`.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_45 \
  RUN_LABEL=exp_ax_opponent_flank_restart_lock \
  BASE_PORT=7510 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ax_opponent_flank_restart_lock_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ax_opponent_flank_restart_lock_*.txt
```

## Candidate 44 Paired Fixed-Pool Validation

Result: failed on clean run 2026-05-01 06:32. Valid paired GA was `candidate_12=93`, `candidate_44=102`, a `9.68%` increase. It reduced setplay but regressed kickoff badly; use `candidate_45`.

Purpose: compare current best `candidate_12` against `candidate_44` with lower gate-risk total parallelism 2.

Result basis: `candidate_43` had a clean paired run on 2026-05-01 05:47:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260501_054734_849010.txt`
- `results/parallel_fixed_baseline_exp_av_opponent_central_setplay_wall_20260501_054734_849011.txt`

That run improved GA from `103 -> 90`, a `12.62%` reduction, but missed the 20% gate. It preserved the useful central structure gains (`center_kickoff_midfield_gap -18`, `center_midfield_gap -9`) and improved most opponents (`cyrus2d -4`, `wrighteagle -4`, `helios -3`, `foxsy_cyrus -3`, `starter2d -3`), but shifted failures into the final box: `flank_kickoff_entry=24`, `flank_setplay_entry=19`, `center_kickoff_entry=14`, `flank_box_entry=10`; 89/90 conceded goals had goalie as nearest Aurora player. `candidate_44` keeps `candidate_43` and adds `flank_restart_goalmouth_lock`, a narrow off-ball near-post/cutback blocker for post-our-kickoff or opponent-driven flank restart leaks after the ball reaches our box edge. It avoids `candidate_42`'s broad PlayOn central terminal guard.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_44` total GA must be at least 20% lower than the paired `candidate_12` run.
- Preserve `candidate_43` central gains: `center_kickoff_midfield_gap` and `center_midfield_gap` stay below paired `candidate_12`.
- Attack the largest remaining buckets: `flank_kickoff_entry + flank_setplay_entry + flank_box_entry` should drop by at least 12 versus candidate43's 53 combined count.
- Do not reproduce candidate42: `center_kickoff_entry` and total `kick_off` must not exceed paired `candidate_12`.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_44 \
  RUN_LABEL=exp_aw_flank_restart_goalmouth_lock \
  BASE_PORT=7510 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_aw_flank_restart_goalmouth_lock_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_aw_flank_restart_goalmouth_lock_*.txt
```

## Candidate 43 Paired Fixed-Pool Validation

Result: failed 20% gate on clean run 2026-05-01 05:47. Valid paired GA was `candidate_12=103`, `candidate_43=90`, a `12.62%` reduction. It reduced `center_kickoff_midfield_gap -18` and `center_midfield_gap -9`, but left final-box buckets (`flank_kickoff_entry=24`, `flank_setplay_entry=19`, `center_kickoff_entry=14`, `flank_box_entry=10`) and regressed `cyrus_team +4`. Use `candidate_44`.

Purpose: compare current best `candidate_12` against `candidate_43` with lower gate-risk total parallelism 2.

Result basis: `candidate_42` had a clean paired run on 2026-05-01 05:05:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260501_050506_723250.txt`
- `results/parallel_fixed_baseline_exp_au_central_restart_terminal_guard_20260501_050506_723251.txt`

That run failed badly: `candidate_12=107`, `candidate_42=115`, a `7.48%` GA increase. Goal-chain showed the PlayOn terminal guard preserved structural gains (`center_kickoff_midfield_gap -12`, `center_midfield_gap -9`) but exploded kickoff entries: `center_kickoff_entry +17`, `flank_kickoff_entry +13`, and `kick_off +18`, with regressions concentrated at `cyrus2d +5` and `helios +6`. `candidate_43` therefore drops the PlayOn terminal guard and returns to the `candidate_41` package, adding only `opponent_central_setplay_wall`: a non-PlayOn central free-kick/indirect-free-kick wall that should target `candidate_41`'s `center_setplay_entry +11` without touching kickoff windows.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_43` total GA must be at least 20% lower than the paired `candidate_12` run.
- Preserve `candidate_41` structural gains: `center_kickoff_midfield_gap` and `center_midfield_gap` should both stay below paired `candidate_12`.
- Fix the setplay regression: `center_setplay_entry` should not exceed paired `candidate_12`.
- Do not reproduce `candidate_42`: `kick_off`, `flank_kickoff_entry`, and `center_kickoff_entry` must not exceed paired `candidate_12`.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_43 \
  RUN_LABEL=exp_av_opponent_central_setplay_wall \
  BASE_PORT=7510 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_av_opponent_central_setplay_wall_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_av_opponent_central_setplay_wall_*.txt
```

## Candidate 42 Paired Fixed-Pool Validation

Result: failed on clean rerun 2026-05-01 05:05. Valid paired GA was `candidate_12=107`, `candidate_42=115`, a `7.48%` GA increase. It regressed `center_kickoff_entry +17` and `flank_kickoff_entry +13`; do not rerun unchanged.

Purpose: compare current best `candidate_12` against `candidate_42` with lower gate-risk total parallelism 2.

Result basis: `candidate_41` had a clean paired run on 2026-05-01 04:15:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260501_041509_587701.txt`
- `results/parallel_fixed_baseline_exp_at_kickoff_flank_goalpost_guard_20260501_041509_587702.txt`

That run failed the 20% gate: `candidate_12=107`, `candidate_41=100`, a `6.54%` GA reduction. It kept the useful structure gains from the central-anchor line (`center_kickoff_midfield_gap -14`, `center_midfield_gap -9`) and improved the broad opponent mix (`foxsy_cyrus -5`, `cyrus2d -3`, `helios -3`, `wrighteagle -1`), but shifted failures into central terminal buckets: `center_setplay_entry +11` and `center_kickoff_entry +8`; `cyrus_team` also regressed by `+4`. `candidate_42` keeps the `candidate_41` package and adds `central_restart_terminal_guard`, a narrow central setplay/kickoff terminal guard that reuses one-step clear and goalmouth lane blocking only after recent opponent central restart or our kickoff, inside the box-entry zone.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_42` total GA must be at least 20% lower than the paired `candidate_12` run.
- Preserve `candidate_41` strengths: `center_kickoff_midfield_gap` and `center_midfield_gap` should both stay below paired `candidate_12`.
- Cut the `candidate_41` regression: `center_setplay_entry + center_kickoff_entry` should not exceed paired `candidate_12` and should drop by at least 12 versus candidate_41's 41 combined count.
- Do not give back the opponent gains: `foxsy_cyrus + cyrus2d + helios` should remain below paired `candidate_12`; `cyrus_team` should not exceed paired `candidate_12`.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_42 \
  RUN_LABEL=exp_au_central_restart_terminal_guard \
  BASE_PORT=7510 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_au_central_restart_terminal_guard_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_au_central_restart_terminal_guard_*.txt
```

## Candidate 41 Paired Fixed-Pool Validation

Result: failed on clean rerun 2026-05-01 04:15. Valid paired GA was `candidate_12=107`, `candidate_41=100`, a `6.54%` reduction. It reduced `center_kickoff_midfield_gap -14` and `center_midfield_gap -9`, but regressed `center_setplay_entry +11` and `center_kickoff_entry +8`; use `candidate_42`.

Purpose: compare current best `candidate_12` against `candidate_41` with lower gate-risk total parallelism 2.

Result basis: `candidate_40` had a clean paired run on 2026-05-01 03:30:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260501_033055_467280.txt`
- `results/parallel_fixed_baseline_exp_as_cyrus_kickoff_central_anchor_20260501_033055_467281.txt`

That run failed badly: `candidate_12=83`, `candidate_40=112`, a `34.94%` GA increase. Goal-chain showed the simple Cyrus-only gate broke the useful lane-lockdown behavior: `flank_kickoff_entry +20`, `center_kickoff_entry +7`, `center_kickoff_midfield_gap +5`. The previous `candidate_39` remains the better base (`90 -> 85`) because it reduced `flank_setplay_entry -11` and `center_kickoff_midfield_gap -8`; its largest remaining buckets were `flank_kickoff_entry=24` and `center_kickoff_entry=19`. `candidate_41` therefore returns to the `candidate_39` global central-anchor package and adds `kickoff_flank_goalpost_guard`, a narrow post-our-kickoff deep-wide guard for near fullback/CB/#7 before the lane-lockdown template can leave the near-post half-space open.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_41` total GA must be at least 20% lower than the paired `candidate_12` run.
- Improve on `candidate_39`: total GA should be at least 8 lower than the paired `candidate_39`-style expectation, with `flank_kickoff_entry` down by at least 10 versus paired `candidate_12`.
- Preserve `candidate_39` strengths: `flank_setplay_entry` and `center_kickoff_midfield_gap` should stay below paired `candidate_12`.
- Do not reproduce `candidate_40`: `kick_off` GA and `flank_kickoff_entry` must not exceed paired `candidate_12`.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_41 \
  RUN_LABEL=exp_at_kickoff_flank_goalpost_guard \
  BASE_PORT=7510 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_at_kickoff_flank_goalpost_guard_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_at_kickoff_flank_goalpost_guard_*.txt
```

## Candidate 40 Paired Fixed-Pool Validation

Result: failed on clean rerun 2026-05-01 03:30. Valid paired GA was `candidate_12=83`, `candidate_40=112`, a `34.94%` GA increase. It regressed `flank_kickoff_entry +20`; do not rerun unchanged.

Purpose: compare current best `candidate_12` against `candidate_40` with lower gate-risk total parallelism 2.

Result basis: `candidate_39` had a clean paired run on 2026-05-01 02:32:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260501_023200_305543.txt`
- `results/parallel_fixed_baseline_exp_ar_kickoff_central_channel_anchor_20260501_023200_305544.txt`

That run failed the 20% gate: `candidate_12=90`, `candidate_39=85`, a `5.56%` GA reduction. The useful signal was concentrated and large on Cyrus-like opponents: `cyrus2d -7`, `cyrus_team -6`, plus `helios -1`. The regressions were concentrated elsewhere: `foxsy_cyrus +4`, `wrighteagle +3`, `starter2d +2`. Goal-chain showed the candidate kept big structural gains (`flank_setplay_entry -11`, `center_kickoff_midfield_gap -8`) but paid for it with `center_kickoff_entry +6`, `center_midfield_gap +4`, and `flank_box_entry +3`. `candidate_40` therefore keeps `kickoff_lane_lockdown` globally but gates the new `kickoff_central_channel_anchor` to Cyrus-like opponents only, avoiding the non-Cyrus regressions from `candidate_39`.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_40` total GA must be at least 20% lower than the paired `candidate_12` run.
- Keep the `candidate_39` Cyrus-like gains: `cyrus2d + cyrus_team` GA should drop by at least 10 versus paired `candidate_12`.
- Avoid the `candidate_39` non-Cyrus regressions: `wrighteagle + foxsy_cyrus + starter2d` GA should not exceed paired `candidate_12`.
- Preserve the structural gains: `flank_setplay_entry` and `center_kickoff_midfield_gap` should both stay below paired `candidate_12`.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_40 \
  RUN_LABEL=exp_as_cyrus_kickoff_central_anchor \
  BASE_PORT=7510 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_as_cyrus_kickoff_central_anchor_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_as_cyrus_kickoff_central_anchor_*.txt
```

## Candidate 39 Paired Fixed-Pool Validation

Result: failed on clean rerun 2026-05-01 02:32. Valid paired GA was `candidate_12=90`, `candidate_39=85`, a `5.56%` reduction. It improved `cyrus2d` and `cyrus_team` strongly but regressed `foxsy_cyrus`, `wrighteagle`, and `starter2d`. Do not rerun unchanged; use `candidate_40`.

Purpose: compare current best `candidate_12` against `candidate_39` with lower gate-risk total parallelism 2.

Result basis: `candidate_38` had a clean paired run on 2026-05-01 01:30:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260501_013054_144478.txt`
- `results/parallel_fixed_baseline_exp_aq_kickoff_lane_terminal_guard_20260501_013054_144479.txt`

That run failed the 20% gate: `candidate_12=100`, `candidate_38=98`, only a `2.00%` GA reduction. Goal-chain showed the lane-lockdown family still helped the intended structure buckets (`center_kickoff_midfield_gap -13`, `flank_kickoff_entry -8`, `flank_setplay_entry -6`, `center_midfield_gap -7`), but it moved too many kickoff possessions into central terminal goals: `center_kickoff_entry +23` and `center_setplay_entry +5`. The regression was broad across `cyrus2d`, `cyrus_team`, and `helios`, not a single-opponent anomaly. `candidate_39` keeps the lane-lockdown package for wide kickoff reentries but adds `kickoff_central_channel_anchor`, which anchors #3/#4/#7 in the central channel during post-our-kickoff center reentry before the wide-lane template can pull them out.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_39` total GA must be at least 20% lower than the paired `candidate_12` run.
- Preserve the lane-lockdown structural gain: `flank_kickoff_entry + center_kickoff_midfield_gap` should stay at least 15 below paired `candidate_12`.
- Fix the main regression: `center_kickoff_entry` should not exceed paired `candidate_12` and should drop by at least 15 versus `candidate_38`.
- Setplay should not regress: `center_setplay_entry + flank_setplay_entry` should not exceed paired `candidate_12`.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_39 \
  RUN_LABEL=exp_ar_kickoff_central_channel_anchor \
  BASE_PORT=7510 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ar_kickoff_central_channel_anchor_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ar_kickoff_central_channel_anchor_*.txt
```

## Candidate 38 Paired Fixed-Pool Validation

Result: failed on clean rerun 2026-05-01 01:30. Valid paired GA was `candidate_12=100`, `candidate_38=98`, a `2.00%` reduction only. It retained some lane-lockdown gains (`center_kickoff_midfield_gap -13`, `flank_kickoff_entry -8`), but regressed badly in `center_kickoff_entry +23`. Do not rerun unchanged; use `candidate_39`.

Purpose: compare current best `candidate_12` against `candidate_38` with lower gate-risk total parallelism 2.

Result basis: `candidate_37` had a clean paired run on 2026-04-30 22:28:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260430_222807_287356.txt`
- `results/parallel_fixed_baseline_exp_ap_kickoff_lane_lockdown_20260430_222807_287357.txt`

That run improved GA from `105 -> 95`, a `9.52%` reduction, but still failed the 20% gate. The useful signal was exactly in the intended kickoff structure buckets: `flank_kickoff_entry -16`, `center_kickoff_midfield_gap -10`, `flank_setplay_entry -4`, and `center_midfield_gap -3`. The regression was terminal: `center_kickoff_entry +12`, `center_box_entry +8`, and `flank_box_entry +4`. `candidate_38` keeps the `candidate_37` lane lockdown and adds `kickoff_terminal_guard`, which reuses central one-step clear and goalmouth lane blocking only during the post-our-kickoff terminal window, instead of bringing back `candidate_36`'s global terminal behavior.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_38` total GA must be at least 20% lower than the paired `candidate_12` run.
- Keep the `candidate_37` kickoff structural gain: `flank_kickoff_entry + center_kickoff_midfield_gap` should stay at least 20 below paired `candidate_12`.
- Cut the `candidate_37` terminal regression: `center_kickoff_entry + center_box_entry + flank_box_entry` should drop by at least 12 versus `candidate_37`.
- `setplay` GA should not regress versus `candidate_37`.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_38 \
  RUN_LABEL=exp_aq_kickoff_lane_terminal_guard \
  BASE_PORT=7510 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_aq_kickoff_lane_terminal_guard_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_aq_kickoff_lane_terminal_guard_*.txt
```

## Candidate 37 Paired Fixed-Pool Validation

Result: failed on clean rerun 2026-04-30 22:28. Valid paired GA was `candidate_12=105`, `candidate_37=95`, a `9.52%` reduction. It hit the intended structure buckets (`flank_kickoff_entry -16`, `center_kickoff_midfield_gap -10`) but shifted failures into terminal entries (`center_kickoff_entry +12`, `center_box_entry +8`, `flank_box_entry +4`). Do not rerun unchanged; use `candidate_38`.

Purpose: compare current best `candidate_12` against `candidate_37` with lower gate-risk total parallelism 2.

Result basis: `candidate_36` had a clean paired run on 2026-04-30 21:12:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260430_211244_37622.txt`
- `results/parallel_fixed_baseline_exp_ao_central_clear_lane_lockdown_20260430_211244_37623.txt`

That run failed the gate: `candidate_12=105`, `candidate_36=104`, only `0.95%` GA reduction. Goal-chain showed the central terminal target did not improve (`center_box_entry + center_kickoff_entry + center_setplay_entry` went `17 -> 20`), while the largest remaining buckets were `flank_kickoff_entry=36` and `center_midfield_gap=21`. `candidate_37` therefore drops the `candidate_36` terminal additions and extends the valid `candidate_34` package with `kickoff_lane_lockdown`: after our kickoff it locks #6/#7/#8 and ball-side fullback/CB into wide-lane plus central second-line positions for 220 PlayOn cycles, aiming at Cyrus-like and HELIOS flank kickoff entries without changing the kickoff first touch.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_37` total GA must be at least 20% lower than the paired `candidate_12` run.
- `flank_kickoff_entry` must drop by at least 16 versus paired `candidate_12`.
- `center_midfield_gap` must not increase; target is at least 6 fewer than paired `candidate_12`.
- The `candidate_34` setplay benefit must mostly remain: `flank_setplay_entry` should stay below paired `candidate_12`.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_37 \
  RUN_LABEL=exp_ap_kickoff_lane_lockdown \
  BASE_PORT=7510 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ap_kickoff_lane_lockdown_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ap_kickoff_lane_lockdown_*.txt
```

## Candidate 36 Paired Fixed-Pool Validation

Result: failed on clean rerun 2026-04-30 21:12. Valid paired GA was `candidate_12=105`, `candidate_36=104`, a `0.95%` reduction only. It reduced `center_kickoff_midfield_gap` by 5 and `flank_setplay_entry` by 5, but gave back `center_setplay_entry +5`, `center_midfield_gap +4`, and `flank_box_entry +2`; `flank_kickoff_entry` remained unchanged at 36. Do not rerun this candidate unless specifically debugging `central_box_one_step_clear + goalmouth_lane_block` trigger behavior.

Purpose: compare current best `candidate_12` against `candidate_36` with lower gate-risk total parallelism 2.

Hypothesis: this is a 20% gate candidate. The clean 2026-04-30 14:50 paired run showed `candidate_34` cut GA from 114 to 98, a 14.0% reduction. It already removed 35 kickoff-chain goals (`flank_kickoff_entry -21`, `center_kickoff_midfield_gap -14`), but left a new central terminal cluster: `center_box_entry + center_kickoff_entry + center_setplay_entry = 33` GA. `candidate_36` keeps the valid `candidate_34` kickoff/setplay package and adds `central_box_one_step_clear + goalmouth_lane_block`, so the required extra gain is only 7 GA versus `candidate_34`; target is at least 9 fewer central terminal goals, giving projected GA near 89 and a 21.9% reduction versus the paired 114 baseline.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_36` total GA must be at least 20% lower than the paired `candidate_12` run.
- `center_box_entry + center_kickoff_entry + center_setplay_entry` should drop by at least 9 versus `candidate_34`.
- The `candidate_34` kickoff gain must mostly remain: `flank_kickoff_entry + center_kickoff_midfield_gap` should not give back more than 4.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_36 \
  RUN_LABEL=exp_ao_central_clear_lane_lockdown \
  BASE_PORT=7510 \
  PARALLEL_JOBS=1 \
  SAFE_PARALLEL_JOBS=1 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ao_central_clear_lane_lockdown_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ao_central_clear_lane_lockdown_*.txt
```

## Candidate 35 Paired Fixed-Pool Validation

Result: invalid on 2026-04-30 16:14. Do not count:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260430_161458_651231.txt`
- `results/parallel_fixed_baseline_exp_an_counterpress_goalie_sweeper_20260430_161458_651232.txt`

Reason: both paired runs exited with `gate_status: suspect_results_detected`. Baseline had suspect `cyrus2d` and `helios`; candidate had suspect `cyrus2d` and `helios`. Even as non-gated signal it was weak: raw GA was `candidate_12=113`, `candidate_35=110`, only 2.7%. Goal-chain analysis showed `flank_setplay_entry -8`, but `kick_off` restart-context GA increased from 44 to 56 and `center_kickoff_entry` increased from 7 to 18. Do not rerun this candidate unless the goal is debugging suspect run stability.

Purpose: compare current best `candidate_12` against `candidate_35` with safer total parallelism 4.

Hypothesis: this is a 20% gate candidate. The clean 2026-04-30 14:50 paired run showed `candidate_34` cut GA from 114 to 98: it strongly reduced `flank_kickoff_entry` by 21 and `center_kickoff_midfield_gap` by 14, but the remaining failures shifted into terminal central box handling (`center_box_entry +8`, `center_kickoff_entry +6`, `center_setplay_entry +4`). `candidate_35` keeps the `candidate_34` counterpress/setplay-wall package and adds the non-`cyrus2d` goalie box sweeper to attack those terminal central entries. The needed extra gain is only about 7 GA versus `candidate_34` on this pairing.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_35` total GA must be at least 20% lower than the paired `candidate_12` run.
- `center_box_entry + center_kickoff_entry + center_setplay_entry` should drop by at least 8 versus `candidate_34` without giving back more than 3 in `center_midfield_gap`.
- `flank_kickoff_entry` should remain far below paired `candidate_12`.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=2 \
  SAFE_PARALLEL_JOBS=2 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_35 \
  RUN_LABEL=exp_an_counterpress_goalie_sweeper \
  BASE_PORT=7510 \
  PARALLEL_JOBS=2 \
  SAFE_PARALLEL_JOBS=2 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_an_counterpress_goalie_sweeper_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_an_counterpress_goalie_sweeper_*.txt
```

## Candidate 34 Paired Fixed-Pool Validation

Result: failed on clean rerun 2026-04-30 14:50. Valid paired GA was `candidate_12=114`, `candidate_34=98`, a 14.0% reduction only. It reduced `flank_kickoff_entry` by 21 and `center_kickoff_midfield_gap` by 14, but increased `center_box_entry` by 8, `center_kickoff_entry` by 6, `center_setplay_entry` by 4, and `flank_setplay_entry` by 4.

Result: invalid on 2026-04-30 13:48. Do not count:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260430_134821_129450.txt`
- `results/parallel_fixed_baseline_exp_am_opponent_flank_setplay_wall_20260430_134821_129451.txt`

Reason: both paired runs exited with `gate_status: suspect_results_detected`. Baseline had suspect disconnects on `cyrus2d`, `cyrus_team`, `foxsy_cyrus`, and `starter2d`; candidate had the same pattern. Rerun with lower per-run parallelism before judging the strategy.

Purpose: compare current best `candidate_12` against `candidate_34` with safer total parallelism 4 after a suspect total-parallelism-6 run.

Hypothesis: this is a 20% gate candidate. The 2026-04-30 09:05 paired run showed `candidate_33` cut GA only from 97 to 88: it reduced `center_midfield_gap` by 11, `center_kickoff_midfield_gap` by 5, `flank_kickoff_entry` by 5, and `flank_box_entry` by 5, but gave back most of that through `flank_setplay_entry +9` and `center_kickoff_entry +7`. `candidate_34` keeps the useful counterpress/frontline package, then adds a narrow low wall only for opponent wide setplays, keeping #2-#8 at legal distance while covering near-side, cutback, and central lanes.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_34` total GA must be at least 20% lower than the paired `candidate_12` run.
- `flank_setplay_entry` must not increase versus paired `candidate_12`; target is at least 8-10 fewer than `candidate_33`.
- The `candidate_33` gains in `center_midfield_gap` and `flank_kickoff_entry` should mostly remain.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=2 \
  SAFE_PARALLEL_JOBS=2 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_34 \
  RUN_LABEL=exp_am_opponent_flank_setplay_wall \
  BASE_PORT=7510 \
  PARALLEL_JOBS=2 \
  SAFE_PARALLEL_JOBS=2 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_am_opponent_flank_setplay_wall_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_am_opponent_flank_setplay_wall_*.txt
```

## Candidate 33 Paired Fixed-Pool Validation

Result: failed on 2026-04-30. Valid paired GA was `candidate_12=97`, `candidate_33=88`, a 9.3% reduction only. It reduced `center_midfield_gap` by 11, `center_kickoff_midfield_gap` by 5, `flank_kickoff_entry` by 5, and `flank_box_entry` by 5, but increased `flank_setplay_entry` by 9 and `center_kickoff_entry` by 7. Per opponent, `helios -5` and `starter2d -9` improved, but `cyrus2d +1`, `cyrus_team +3`, and `wrighteagle +1` regressed.

Purpose: compare current best `candidate_12` against `candidate_33` with total parallelism 6.

Hypothesis: this is a 20% gate candidate. The 2026-04-30 08:18 paired run showed `candidate_32` cut total GA only from 103 to 93, but the remaining largest bucket is now `flank_kickoff_entry=35`. Offline restart-policy analysis shows that after Aurora kickoffs the ball often advances into wide/half-space lanes while Aurora has almost no player within 12m of the ball after 120 cycles. `candidate_33` keeps the useful frontline recovery screen from `candidate_32`, but adds a narrow #9/#10/#11 counterpress only during the first 160 PlayOn cycles after our own kickoff, without changing the kickoff first touch.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_33` total GA must be at least 20% lower than the paired `candidate_12` run.
- `flank_kickoff_entry` should drop by at least 18-20 GA versus paired `candidate_12`.
- `cyrus_team` and `foxsy_cyrus` must not regress; they were the `candidate_32` regression points.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_33 \
  RUN_LABEL=exp_al_kickoff_counterpress \
  BASE_PORT=7510 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_al_kickoff_counterpress_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_al_kickoff_counterpress_*.txt
```

## Candidate 32 Paired Fixed-Pool Validation

Result: failed on 2026-04-30. Valid paired GA was `candidate_12=103`, `candidate_32=93`, a 9.7% reduction only. It improved `flank_setplay_entry` by 8 and reduced `starter2d` by 6 / `wrighteagle` by 4, but `flank_kickoff_entry` increased by 6 and `cyrus_team` / `foxsy_cyrus` regressed.

Codex self-run at `2026-04-30 01:02:42` was invalid, not a strategy failure: every opponent result reported `ERROR missing result path` / `ERROR timeout or server crash`, with `rcssserver` and player logs showing local socket permission failures (`Operation not permitted`). Do not count these summaries:
- `results/parallel_fixed_baseline_exp_p_current_pair_recheck_20260430_010242_4.txt`
- `results/parallel_fixed_baseline_exp_ak_frontline_recovery_screen_20260430_010242_5.txt`

Purpose: compare current best `candidate_12` against `candidate_32` with total parallelism 6.

Hypothesis: this is a 20% gate candidate. The latest paired runs show all conceded goals are box-entry goals, while goalie-only and single field-player guard changes merely move failures between flank and center buckets. `candidate_32` removes those single-point interventions and instead drops #9/#10/#11 into a three-lane recovery screen once we lose PlayOn initiative in our half. Since Aurora has almost no scoring output in this pool, sacrificing forward rest-defense should reduce both `flank_*` and `center_*` box-entry chains.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_32` total GA must be at least 20% lower than the paired `candidate_12` run.
- Combined center and flank box-entry chains must drop without a compensating increase in `kick_off` restart-context GA.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_32 \
  RUN_LABEL=exp_ak_frontline_recovery_screen \
  BASE_PORT=7510 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ak_frontline_recovery_screen_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ak_frontline_recovery_screen_*.txt
```

## Candidate 31 Paired Fixed-Pool Validation

Result: failed on 2026-04-30. Paired GA was `candidate_12=92`, `candidate_31=93`; it reduced `center_kickoff_entry` by 9 and `flank_box_entry` by 9, but increased `center_midfield_gap` by 15 and `center_kickoff_midfield_gap` by 8.

Purpose: compare current best `candidate_12` against `candidate_31` with total parallelism 6.

Hypothesis: this is a 20% gate candidate. The latest paired baseline conceded 100 GA; 44 goals ended with the goalie as the nearest Aurora player, and 38 of those were outside `cyrus2d`.
`candidate_26` used the same execution lever narrowly on flank box balls and reduced the goalie-nearest bucket by 17 while cutting total GA by 9. `candidate_31` removes the failed field-player cutback guard and expands the goalie intercept to non-`cyrus2d` central/wide box races, while still deferring to legal catches and quiet balls.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_31` total GA must be at least 20% lower than the paired `candidate_12` run.
- Non-`cyrus2d` goalie-nearest conceded goals should drop by about 20 or more.
- `cyrus2d` must not regress versus paired `candidate_12` because this candidate is gated off there.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_31 \
  RUN_LABEL=exp_aj_non_cyrus2d_goalie_box_sweeper \
  BASE_PORT=7510 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_aj_non_cyrus2d_goalie_box_sweeper_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_aj_non_cyrus2d_goalie_box_sweeper_*.txt
```

## Candidate 30 Paired Fixed-Pool Validation

Result: failed on 2026-04-29. Paired GA was `candidate_12=100`, `candidate_30=107`; `flank_kickoff_entry` and `flank_setplay_entry` each dropped by only 2, while `center_kickoff_entry` increased by 7 and `flank_box_entry` increased by 5.

Purpose: compare current best `candidate_12` against `candidate_30` with total parallelism 6.

Hypothesis: this is a 20% gate candidate. The latest four paired `candidate_12` rechecks average 100.75 GA/run; flank entry chains account for about 56 GA/run (`flank_kickoff_entry=29.75`, `flank_setplay_entry=17.25`, `flank_box_entry=9.0`).
`candidate_28` and `candidate_29` proved that changing kickoff first touch is the wrong lever. `candidate_30` leaves kickoff possession alone and instead assigns one non-owner defensive field player to the deep-wide cutback lane during PlayOn, plus keeps the small `candidate_26` goalie flank-intercept signal only outside `cyrus2d`.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_30` total GA must be at least 20% lower than the paired `candidate_12` run.
- Combined `flank_kickoff_entry + flank_setplay_entry + flank_box_entry` should drop by about 22 GA/run or more.
- `kick_off` restart-context GA must not increase versus paired `candidate_12`.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_30 \
  RUN_LABEL=exp_ai_flank_cutback_guard \
  BASE_PORT=7510 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ai_flank_cutback_guard_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ai_flank_cutback_guard_*.txt
```

## Candidate 29 Paired Fixed-Pool Validation

Result: failed on 2026-04-29. Paired GA was `candidate_12=98`, `candidate_29=111`; `kick_off` GA increased from 37 to 65 and `flank_kickoff_entry` increased from 19 to 40.

Purpose: compare current best `candidate_12` against `candidate_29` with total parallelism 6.

Hypothesis: this is a 20% gate candidate. The latest paired baseline conceded 53/102 goals from `kick_off` restart chains.
`candidate_28` proved that sending the kickoff ball deep to the opponent is wrong; it increased `kick_off` GA from 53 to 69.
`candidate_29` keeps the same 20% target bucket but changes the first kickoff touch to a controlled short wide outlet to our own #9/#11 side, avoiding both the 30-cycle set-play wait and the deep punt turnover.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_29` total GA must be at least 20% lower than the paired `candidate_12` run.
- `kick_off` restart-context GA should drop by about 40% or more.
- `flank_kickoff_entry` must not increase versus paired `candidate_12`.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_29 \
  RUN_LABEL=exp_ah_kickoff_wide_outlet \
  BASE_PORT=7510 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ah_kickoff_wide_outlet_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ah_kickoff_wide_outlet_*.txt
```

## Candidate 28 Paired Fixed-Pool Validation

Result: failed on 2026-04-29. Paired GA was `candidate_12=102`, `candidate_28=119`; `kick_off` GA increased from 53 to 69.

Purpose: compare current best `candidate_12` against `candidate_28` with total parallelism 6.

Hypothesis: this is a 20% gate candidate. The latest paired baseline conceded 49/103 goals from `kick_off` restart chains.
`candidate_28` changes only our kickoff first touch: instead of waiting and building through midfield, the kickable non-goalie immediately punts to the opponent deep wide corner. If this cuts about half of kickoff-chain concessions, expected improvement is about 24-25 GA/run, above the 20% gate.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_28` total GA must be at least 20% lower than the paired `candidate_12` run.
- `kick_off` restart-context GA should drop by about 45% or more.
- Setplay/other GA must not increase enough to erase the kickoff gain.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_28 \
  RUN_LABEL=exp_ag_kickoff_safety_punt \
  BASE_PORT=7510 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ag_kickoff_safety_punt_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ag_kickoff_safety_punt_*.txt
```

## Candidate 27 Paired Fixed-Pool Validation

Result: superseded before run by the 20% gate request. Expected gain was about 10-11%, so do not use this as the next validation command.

Purpose: compare current best `candidate_12` against `candidate_27` with total parallelism 6.

Hypothesis: `candidate_26` reduced GA from 103 to 94 but missed the 10% gate because it worsened only `cyrus2d` by 2 goals.
`candidate_27` keeps the same goalie flank-box intercept for `helios`, `wrighteagle`, `cyrus_team`, `foxsy_cyrus`, and `starter2d`, but disables it for `ROBOCUP_OPPONENT_KEY=cyrus2d`.
Using the last paired run as a segment estimate, expected total GA is about 92 against paired baseline 103, which clears the 10% gate.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_27` total GA must be at least 10% lower than the paired `candidate_12` run.
- `cyrus2d` must not regress versus paired `candidate_12`.
- `helios + foxsy_cyrus + starter2d` should retain most of the `candidate_26` gain.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_27 \
  RUN_LABEL=exp_af_non_cyrus2d_goalie_flank_box_intercept \
  BASE_PORT=7510 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_af_non_cyrus2d_goalie_flank_box_intercept_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_af_non_cyrus2d_goalie_flank_box_intercept_*.txt
```

## Candidate 26 Paired Fixed-Pool Validation

Result: near miss on 2026-04-29. Paired GA was `candidate_12=103`, `candidate_26=94`; improvement was 8.7%, below the 10% hard gate.

Purpose: compare current best `candidate_12` against `candidate_26` with total parallelism 6.

Hypothesis: `candidate_26` targets the current largest bucket, `flank_kickoff_entry + flank_setplay_entry`.
The paired baseline has 58 GA/run in that bucket, and older low/high groups still show about 42-45 GA/run, so a 20-25% hit rate is enough to clear a 10% total-GA improvement gate.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_26` total GA must be at least 10% lower than the paired `candidate_12` run.
- `flank_kickoff_entry + flank_setplay_entry` should drop by about 20% or more without increasing center GA.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_26 \
  RUN_LABEL=exp_ae_goalie_flank_box_intercept \
  BASE_PORT=7510 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ae_goalie_flank_box_intercept_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ae_goalie_flank_box_intercept_*.txt
```

## Candidate 25 Paired Fixed-Pool Validation

Result: failed on 2026-04-29. Paired GA was `candidate_12=100`, `candidate_25=105`; keep this section for audit only.

Purpose: compare current best `candidate_12` against `candidate_25` with total parallelism 6.

Acceptance:
- Gate clean: no suspect matches, no disconnects.
- `candidate_25` total GA must be at least 10% lower than the paired `candidate_12` run.
- `center_midfield_gap + center_kickoff_midfield_gap` should drop by about 25% or more.

```bash
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_12 \
  RUN_LABEL=exp_p_current_pair_recheck \
  BASE_PORT=7410 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
(
  ROBOCUP_EXPERIMENT_PROFILE=candidate_25 \
  RUN_LABEL=exp_ad_central_midfield_gap_plug \
  BASE_PORT=7510 \
  PARALLEL_JOBS=3 \
  SAFE_PARALLEL_JOBS=3 \
  FAIL_ON_SUSPECT=1 \
  ./scripts/run_parallel_fixed_baseline.sh 1
) &
wait
```

Quick result lookup:

```bash
ls -t results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ad_central_midfield_gap_plug_*.txt | head
```

```bash
rg -n "GF=|GA=|gate|suspect|disconnect|summary" results/parallel_fixed_baseline_exp_p_current_pair_recheck_*.txt results/parallel_fixed_baseline_exp_ad_central_midfield_gap_plug_*.txt
```
