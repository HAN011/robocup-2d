# 下一轮接力 Prompt

你是 Codex，在 `/home/ccczorange/robocup` 继续 RoboCup 2D 策略迭代。请用中文回复，直接、工程化、以结果为导向。

## 当前用户目标

用户已将策略目标从“强队少失球”切到“一天激进赢球策略_稳定打败弱队.md”：

- 主要目标：稳定打败弱队 `starter2d` / `foxsy_cyrus`
- 当前核心瓶颈：大多数候选仍是 `GF=0`
- 当前最重要任务：破 `GF=0`，再谈净胜
- 用户允许自动执行长命令，但要求低并发、不要留下残留进程、不要跑爆内存

固定测试弱队命令要低并发：

- baseline 一边：`candidate_12`
- candidate 一边：待测候选
- `BASELINE_OPPONENT_KEYS="starter2d foxsy_cyrus"`
- 每边 `PARALLEL_JOBS=1 SAFE_PARALLEL_JOBS=1 FAIL_ON_SUSPECT=1`
- 两边并行，总体约 2 个比赛实例

测试 Python 固定优先使用：

```bash
/home/ccczorange/anaconda3/envs/robocup2d/bin/python
```

## 提交前状态

已完成一次整合提交，提交包含当前所有 worktree 改动：

- 实验 profiles / decision hooks
- 弱队候选 60-74 相关代码
- 分析脚本和测试
- runner 的 opponent key 传递和 profile alias 支持
- Pyrus2D server silence timeout 修正
- docs / submission 相关文件

提交后如果继续工作，先运行：

```bash
git status --short
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

## 当前最好结论

稳定默认基线仍是：

- `candidate_12` / `exp_p_cyrus_arc_second_ball`

弱队方向里已验证最有信号的是：

- `candidate_72` / `exp_bt_weak_team_restart_grounder`

candidate72 clean 结果：

- baseline `candidate_12`: `starter2d` 0-10, `foxsy_cyrus` 0-16
- `candidate_72`: `starter2d` 0-5, `foxsy_cyrus` 0-20
- 结论：Starter2D GA 改善，攻击到达更深区域，但仍 `GF=0`

失败/不建议继续的最近候选：

- `candidate_70`: `starter2d` 0-6, `foxsy_cyrus` 0-17，仍 `GF=0`，并干扰自然推进
- `candidate_71`: `starter2d` 0-7, `foxsy_cyrus` 0-23，明显退化
- `candidate_73`: `starter2d` 0-11, `foxsy_cyrus` 0-18，破坏 baseline 自然进球路径

重要发现：

- 最近一轮 baseline `candidate_12` 曾自然打进 Starter2D 1 球
- summary: `results/parallel_fixed_baseline_exp_p_weak_pair_recheck_20260501_162940_2638030.txt`
- baseline 比分：`starter2d` Aurora 1-7 STARTER_base
- RCL/RCG 在本地该目录未保留，后续长局最好显式设置 `PARALLEL_MATCH_DISABLE_INTERNAL_FILE_LOGS=0`
- 已知关键链条来自之前提取：Aurora #9 在 x≈38、y≈-18 一带高位触球，4042/4043 连续 kick 后 4049 进球
- 结论：不要继续 broad PlayOn hook 或 kickoff-window hard finish；应该保护 baseline 自然链条，只在 #9/#11 高位自然链条非常窄地补终结

## 最新已实现候选

`candidate_74` / `exp_bv_weak_team_natural_high_frontline_finish`

实现文件：

- `player/experiment_profile.py`
- `player/decision.py`
- `tests/test_experiment_profile.py`
- `tests/test_decision_clearance.py`

profile 形状：

- 基于 candidate12：
  - `box_clear=True`
  - `box_hold_light=True`
  - `finish_unlock=True`
  - `finish_tight=True`
  - `goalie_backpass_guard=True`
  - `cyrus_arc_second_ball=True`
- 只新增：
  - `weak_team_natural_high_frontline_finish=True`
- 不启用：
  - `weak_team_restart_grounder`
  - `weak_team_restart_second_finish`
  - `weak_team_deep_cutback`
  - `weak_team_natural_channel_feed`
  - weak-team press/overdrive/killer 系列

decision 触发条件：

- weak opponent only (`starter` or `foxsy`)
- PlayOn only
- non-goalie, kickable
- self unum only `9` or `11`
- `max(me.x, ball.x) >= 34`
- `7 <= abs(ball.y) <= 24`
- me/ball 同侧或横向差不过大
- 压力门控：kickable opponent 太近或 ball 附近 opponent 太近则不触发
- 动作 label：`weak_team_natural_high_frontline_finish`

单元测试已通过：

```bash
/home/ccczorange/anaconda3/envs/robocup2d/bin/python -m unittest discover tests
```

结果：`Ran 220 tests ... OK`

## 下一步必须做

1. 先确认无残留：

```bash
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

2. 将 candidate74 验证命令写到 `long_commands.md` 顶部，如果还没写的话。

3. 运行 candidate74 低并发 paired validation。推荐保留 server records：

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

4. 验证后读取最新 summary：

```bash
ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt results/parallel_fixed_baseline_exp_bv_weak_team_natural_high_frontline_finish_*.txt | head
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_p_weak_pair_recheck_*.txt | head -1)"
sed -n '1,220p' "$(ls -t results/parallel_fixed_baseline_exp_bv_weak_team_natural_high_frontline_finish_*.txt | head -1)"
```

5. 验收顺序：

- 首先 gate clean，无 suspect/disconnect
- 首先看是否破 `GF=0`
- 其次看 starter2d 是否不明显回退
- 如果 candidate74 仍 `GF=0`，直接用保留的 `.rcl/.rcg` 抽 `weak_team_natural_high_frontline_finish` 是否触发，及 #9/#11 高位触球是否出现

## 残留进程规则

每次长命令结束都必须跑：

```bash
pgrep -af '[r]cssserver|[r]un_parallel_fixed_baseline|[r]un_match.sh|[p]layer/main.py|[c]oach/main.py|[s]ample_player|[s]ample_coach|HELIOS|[h]elios|[c]yrus|[w]righteagle|[s]tarter' || true
```

如果有真实残留，再用温和 `kill -TERM`，必要时才处理；不要粗暴杀无关进程。
