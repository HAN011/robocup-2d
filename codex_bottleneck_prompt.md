# Codex Prompt: RoboCup Aurora GA Bottleneck Analysis

你在 `/home/ccczorange/robocup` 这个 RoboCup 2D 项目里做独立分析。先不要直接改代码，先阅读代码、结果和观测输出，给出下一步最有希望把 GA 从当前 89 降到 50 附近的实验方案。

## 背景和约束

- 目标：优化 Aurora 自身策略，固定 6 队对手池总 GA 尽量降到 50 以下。
- 禁止 RL/training 改动，不要改 `train/`。
- 不要改变 `./start.sh` 语义。
- 固定对手池：`cyrus2d`、`helios`、`wrighteagle`、`cyrus_team`、`foxsy_cyrus`、`starter2d`。
- 验证必须 gate clean：无 suspect matches、无 disconnects。
- 当前 fresh best：
  - profile: `exp_p_cyrus_arc_second_ball` / `candidate_12`
  - result: `results/parallel_fixed_baseline_exp_p_current_recheck_20260428_212248_1721604.txt`
  - GA=89, GF=0, gate clean
  - per opponent GA: cyrus2d 24, helios 17, wrighteagle 7, cyrus_team 20, foxsy_cyrus 17, starter2d 4
- 当前 fresh observability：
  - `results/parallel_fixed_baseline_exp_p_current_recheck_20260428_212248_1721604_observability.json`
  - 总失球 89
  - restart contexts: kick_off=42, setplay=33, other=14
  - channels: center=46, left_flank=24, right_flank=19
  - 最大组合：setplay/center=21, kick_off/center=19
  - 所有失球都有 box entry

## 当前保留的大致改动

- vendor 稳定性修复：
  - `.vendor/Pyrus2D/lib/action/neck_scan_field.py`
  - `.vendor/Pyrus2D/lib/coach/gloabl_world_model.py`
  - `.vendor/Pyrus2D/lib/player/world_model.py`
- `player/experiment_profile.py` 中已有 profiles 到 `candidate_12` / `exp_p_cyrus_arc_second_ball`。
- `player/decision.py` 中已有 goalie back-pass guard、`candidate_12` 的 `cyrus_arc_second_ball`、guarded possession 等逻辑。
- `tests/test_decision_clearance.py`、`tests/test_experiment_profile.py` 有对应单测。
- `scripts/run_parallel_fixed_baseline.sh` 和 `scripts/run_fixed_baseline.sh` 会注入 `ROBOCUP_OPPONENT_KEY`。

## 已验证失败并回退的方向，不要重复

1. `candidate_13` kickoff/after-goal 深站位：
   - `exp_q_kickoff_reset_guard`
   - GA=103, gate clean
   - 已回退
2. `candidate_13` set-play immediate wide outlet：
   - `exp_q_setplay_outlet_guard`
   - GA=115, gate clean
   - 已回退
3. `candidate_13` restart center screen：
   - `exp_q_restart_center_screen`
   - GA=116, gate clean
   - 已回退
4. 更早失败方向：
   - broad center compact / midblock
   - wrighteagle-only midblock
   - pressure outlet / possession relief broad variants
   - restart screen
   - near-teammate backpass guard
   - adding setplay shield to light_box_finish_tight
   - broader goalie catch avoidance
   - global visual kick touch

这些多数会降低局部问题但整体 GA 恶化。

## 请你做的事

1. 独立阅读以下文件/结果：
   - `player/decision.py`
   - `player/experiment_profile.py`
   - `tests/test_decision_clearance.py`
   - `tests/test_experiment_profile.py`
   - `results/parallel_fixed_baseline_exp_p_current_recheck_20260428_212248_1721604.txt`
   - `results/parallel_fixed_baseline_exp_p_current_recheck_20260428_212248_1721604_observability.json`
   - 如需要，也看 `scripts/analyze_match_observability.py` 和 `scripts/analyze_opponent_policy.py`
2. 不要重复上面失败过的“更深站位 / 立即清边 / 中路 screen / broad midblock / broad possession outlet”。
3. 重点思考：为什么 kickoff/setplay/center 失球多，但直接改 kickoff/setplay 反而变差？有没有更底层的原因，比如：
   - off-ball intercept/block 选择错误
   - 防线和中场的 player assignment 错位
   - goalie/defender 对 box entry 的处理顺序问题
   - clear/pass/hold 的触发条件过晚或目标错误
   - formation update 与 game mode/restart 状态耦合问题
   - 对手 key gating 或 side handling 的盲点
4. 输出 2-3 个“最小、可 profile-gated、可回退”的实验建议。
   每个建议请包含：
   - 假设是什么
   - 为什么它避开了已失败方向
   - 预计改哪些函数/文件
   - 应加哪些单测
   - 固定池验证命令
   - 如果失败，应如何判断和回退
5. 请优先找能同时降低 cyrus2d/cyrus_team/foxsy_cyrus 的方案，因为它们占当前 GA 的大头；但不要用明显会伤害 helios/wrighteagle/starter2d 的特化。
6. 暂时只给分析和实验计划，不要直接实现。
