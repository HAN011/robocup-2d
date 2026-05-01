#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUBMISSION_DIR="${PROJECT_ROOT}/submission"
PROFILE_FILE="${SUBMISSION_DIR}/team_profile.env"
RUN_TS="${RUN_TS:-$(date +%Y%m%d_%H%M%S)}"
INCLUDE_TECH_SLIDES="${INCLUDE_TECH_SLIDES:-0}"

TEAM_NAME="$(PYTHONPATH="${PROJECT_ROOT}" python3 - <<'PY'
import team_config
print(team_config.TEAM_NAME)
PY
)"

SCHOOL_NAME="待补充学校名称"
ADVISOR_NAME="待补充指导老师"
LEADER_NAME="待补充领队"
TEAM_MEMBERS="待补充队员名单"
CONTACT_PERSON="待补充联系人"
CONTACT_EMAIL="待补充邮箱"
SUBMISSION_DATE="2026-04-25"

if [[ -f "${PROFILE_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${PROFILE_FILE}"
fi

OUTPUT_DIR="${SUBMISSION_DIR}/dist/${TEAM_NAME}_submission_${RUN_TS}"
SRC_DIR="${OUTPUT_DIR}/src"
ASSET_DIR="${OUTPUT_DIR}/assets"
CODE_STAGE_DIR="${OUTPUT_DIR}/code_stage/${TEAM_NAME}"

DESCRIPTION_PDF="${OUTPUT_DIR}/${TEAM_NAME}_team_description.pdf"
REGISTRATION_INFO_FILE="${OUTPUT_DIR}/${TEAM_NAME}_registration_info.txt"
RUN_INSTRUCTIONS_FILE="${OUTPUT_DIR}/${TEAM_NAME}_run_instructions.md"
EMAIL_TEMPLATE_FILE="${OUTPUT_DIR}/${TEAM_NAME}_email_template.txt"
CODE_ZIP_FILE="${OUTPUT_DIR}/${TEAM_NAME}_code_bundle.zip"
SUBMISSION_ZIP_FILE="${OUTPUT_DIR}/${TEAM_NAME}_submission_bundle.zip"

log() {
  printf '[build_submission_bundle] %s\n' "$*"
}

die() {
  printf '[build_submission_bundle] ERROR: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  local cmd="$1"
  command -v "${cmd}" >/dev/null 2>&1 || die "required command not found: ${cmd}"
}

resolve_runtime_python() {
  local candidate
  local candidates=(
    "${HOME}/anaconda3/envs/robocup2d/bin/python"
    "${HOME}/miniconda3/envs/robocup2d/bin/python"
  )

  for candidate in "${candidates[@]}"; do
    if [[ -x "${candidate}" ]] && "${candidate}" -c 'import pyrusgeom' >/dev/null 2>&1; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  die "could not find a Python runtime with pyrusgeom installed"
}

require_runtime_python_distributions() {
  local runtime_python="$1"
  shift

  "${runtime_python}" - "$@" <<'PY'
from __future__ import annotations

import sys
from importlib import metadata

missing = []
for name in sys.argv[1:]:
    try:
        metadata.distribution(name)
    except metadata.PackageNotFoundError:
        missing.append(name)

if missing:
    raise SystemExit(
        "missing Python distributions: {missing}. "
        "Install CPU RL dependencies first, for example: "
        "python -m pip install --index-url https://download.pytorch.org/whl/cpu torch "
        "&& python -m pip install gymnasium"
        .format(missing=", ".join(missing))
    )
PY
}

resolve_latest_match_report() {
  local pattern="$1"
  local file

  [[ -d "${PROJECT_ROOT}/results" ]] || return 1

  while IFS= read -r file; do
    if [[ -f "${file}" ]] && grep -qE '^Match 1:' "${file}"; then
      printf '%s\n' "${file}"
      return 0
    fi
  done < <(
    find "${PROJECT_ROOT}/results" -maxdepth 1 -type f -name "${pattern}" -printf '%T@ %p\n' \
      | sort -nr \
      | cut -d' ' -f2-
  )

  return 1
}

extract_first_match_line() {
  local file="$1"
  [[ -f "${file}" ]] || return 1
  grep -E '^Match 1:' "${file}" | head -n1
}

escape_html() {
  python3 -c 'import html, sys; print(html.escape(sys.stdin.read()), end="")'
}

write_validation_card_html() {
  local helios_line="$1"
  local cyrus_line="$2"
  local validation_log="$3"
  local html_file="${SRC_DIR}/validation_card.html"
  local helios_html
  local cyrus_html
  local log_html

  helios_html="$(printf '%s' "${helios_line}" | escape_html)"
  cyrus_html="$(printf '%s' "${cyrus_line}" | escape_html)"
  log_html="$(printf '%s' "${validation_log}" | escape_html)"

  cat >"${html_file}" <<EOF
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>${TEAM_NAME} Validation Card</title>
  <style>
    :root {
      --bg: #f4efe6;
      --card: #fffaf3;
      --ink: #162126;
      --muted: #5a6770;
      --accent: #b5532f;
      --line: #d8c8ae;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(181, 83, 47, 0.15), transparent 32%),
        linear-gradient(135deg, #efe5d4, var(--bg));
      font-family: "Noto Sans CJK SC", sans-serif;
      color: var(--ink);
    }
    .wrap {
      width: 1600px;
      height: 900px;
      padding: 64px;
    }
    .card {
      height: 100%;
      border: 2px solid var(--line);
      border-radius: 28px;
      background: var(--card);
      box-shadow: 0 18px 48px rgba(22, 33, 38, 0.12);
      padding: 48px 56px;
      display: flex;
      flex-direction: column;
      gap: 28px;
    }
    .eyebrow {
      font-size: 24px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--accent);
      font-weight: 700;
    }
    h1 {
      margin: 0;
      font-size: 54px;
      line-height: 1.1;
    }
    .sub {
      margin: 0;
      font-size: 24px;
      color: var(--muted);
    }
    .results {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }
    .result-box {
      border: 1px solid var(--line);
      border-radius: 20px;
      background: #fff;
      padding: 24px 28px;
    }
    .label {
      font-size: 20px;
      font-weight: 700;
      color: var(--accent);
      margin-bottom: 12px;
    }
    .value {
      font-size: 28px;
      font-weight: 700;
      line-height: 1.4;
      white-space: pre-wrap;
    }
    .note {
      flex: 1;
      border-radius: 20px;
      background: #182228;
      color: #eff6f8;
      padding: 24px 28px;
      font-family: "Noto Sans Mono CJK SC", "Noto Sans Mono", monospace;
      font-size: 18px;
      line-height: 1.5;
      white-space: pre-wrap;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="eyebrow">Submission Evidence</div>
      <h1>${TEAM_NAME} 可执行码短赛验证</h1>
      <p class="sub">重点证明：队伍可启动、身份信息输出合规、短赛结果可回收。</p>
      <div class="results">
        <div class="result-box">
          <div class="label">HELIOS 短赛</div>
          <div class="value">${helios_html}</div>
        </div>
        <div class="result-box">
          <div class="label">Cyrus2D 短赛</div>
          <div class="value">${cyrus_html}</div>
        </div>
      </div>
      <div class="note">${log_html}</div>
    </div>
  </div>
</body>
</html>
EOF
}

render_validation_card_png() {
  local html_file="${SRC_DIR}/validation_card.html"
  local png_file="${ASSET_DIR}/validation_card.png"
  google-chrome \
    --headless \
    --disable-gpu \
    --hide-scrollbars \
    --allow-file-access-from-files \
    --no-first-run \
    --window-size=1600,900 \
    "--screenshot=${png_file}" \
    "file://${html_file}" >/dev/null 2>&1
}

write_print_css() {
  cat >"${SRC_DIR}/print.css" <<'EOF'
@page {
  size: A4;
  margin: 16mm 16mm 18mm 16mm;
}

:root {
  --bg: #f8f5ef;
  --ink: #182228;
  --muted: #4c5d65;
  --accent: #b5532f;
  --panel: #fffdf8;
  --line: #d9ccb7;
}

body {
  font-family: "Noto Sans CJK SC", sans-serif;
  color: var(--ink);
  background: var(--bg);
  line-height: 1.65;
  font-size: 11pt;
}

h1, h2, h3 {
  color: var(--ink);
  margin-top: 0;
}

h1 {
  font-size: 24pt;
  border-bottom: 3px solid var(--accent);
  padding-bottom: 6px;
  margin-bottom: 16px;
}

h2 {
  font-size: 16pt;
  margin-top: 20px;
  margin-bottom: 10px;
}

h3 {
  font-size: 13pt;
  margin-top: 14px;
  margin-bottom: 6px;
}

p, li {
  color: var(--ink);
}

blockquote, pre {
  background: #f2ebe1;
  border-left: 4px solid var(--accent);
  padding: 10px 12px;
}

code {
  font-family: "Noto Sans Mono CJK SC", "Noto Sans Mono", monospace;
}

img {
  max-width: 100%;
  border: 1px solid var(--line);
  border-radius: 10px;
}

table {
  border-collapse: collapse;
  width: 100%;
  background: var(--panel);
}

th, td {
  border: 1px solid var(--line);
  padding: 8px 10px;
  text-align: left;
}

th {
  background: #f2ebe1;
}

.meta-table td:first-child {
  width: 28%;
  font-weight: 700;
}
EOF
}

write_slides_markdown() {
  local helios_line="$1"
  local cyrus_line="$2"
  cat >"${SRC_DIR}/slides.md" <<EOF
# 1. 封面

## ${TEAM_NAME} 技术资格审查汇报

RoboCup 足球机器人比赛·仿真 2D 组

提交日期：${SUBMISSION_DATE}

- 学校：${SCHOOL_NAME}
- 指导老师：${ADVISOR_NAME}
- 领队：${LEADER_NAME}
- 队员：${TEAM_MEMBERS}
- 联系邮箱：${CONTACT_EMAIL}

---

# 2. 比赛目标与运行环境

- 本次提交目标：优先通过技术资格审查，保证可执行码可启动、可验证、可解释。
- 目标环境：Ubuntu 24.04 64-bit + rcssserver-19.0.x。
- 队伍运行入口：./start.sh。
- 默认比赛口径：规则策略为主，RL 完整训练环境随包提供但默认关闭。
- 合规要求：主程序启动时输出 2026RoboCup机器人世界杯中国赛【${TEAM_NAME}】。

---

# 3. 队伍系统结构

- start.sh：统一拉起 11 个球员进程和 1 个 coach 进程。
- player/：球员主程序、决策调度和执行链路。
- coach/：教练端进程和队伍级信息同步。
- base/：基于 Pyrus2D 的规则策略、阵型和 set-play 逻辑。
- train/：强化学习训练、桥接、状态编码和 PPO 模块，随包提供但默认不启用。
- .vendor/Pyrus2D：底层框架与行为库。

---

# 4. 当前主策略

- 比赛版本采用规则决策主导，覆盖 set-play、无球跑位、带球推进、基本抢断与守门员逻辑。
- player/decision.py 提供“规则策略 + 可选 RL 接管”的统一入口。
- 默认提交口径下不启用 ROBOCUP_RL_MODE=1，避免 RL 训练链路影响比赛运行稳定性。
- 当前重点不是激进进攻，而是先保证球队完整上线、稳定跑完短赛验证。

---

# 5. 本年度技术突破

- 合规突破：身份验证机制已经植入主程序代码，满足 2026 规则新增防作弊要求。
- 稳定性突破：scripts/run_match.sh 在短赛结束判定滞后时会回收最终比分，避免把已完成比赛误判为 crash。
- 当前短赛结果：
  - HELIOS_base：${helios_line}
  - Cyrus2D_base：${cyrus_line}
- 当前判断：对 Cyrus2D_base 仍明显落后，后续将继续聚焦防守与稳定性。

---

# 6. 实验与验证

![](assets/validation_card.png){ width=88% }

---

# 7. 未来技术发展方向

- 对 Cyrus2D_base 做更有针对性的防守站位和失球模式分析。
- 继续消除 benchmark 中的 timeout / 结束判定问题，保证回归测试稳定。
- 在保持默认比赛版本稳定的前提下，逐步把 train/ 中的 RL 能力做成可控增强。
- 技术挑战赛展示口径以球队主要技术描述、本年度技术突破、未来发展方向为主。
EOF
}

write_description_markdown() {
  local helios_line="$1"
  local cyrus_line="$2"
  cat >"${SRC_DIR}/description.md" <<EOF
# ${TEAM_NAME} 球队描述文档

提交日期：${SUBMISSION_DATE}

## 1. 队伍信息

- 球队名称：${TEAM_NAME}
- 学校名称：${SCHOOL_NAME}
- 队伍成员（请注明指导老师和领队）：
  指导老师：${ADVISOR_NAME}
  领队：${LEADER_NAME}
  队员：${TEAM_MEMBERS}
- 联系邮箱：${CONTACT_EMAIL}

为避免报名信息与文档信息不一致，以上字段与报名系统和提交邮件保持完全一致。

## 2. 项目目标与提交口径

本次提交版本以技术资格审查通过为第一目标，重点保证以下三件事：

1. 球队可执行码可以在 Ubuntu 24.04 与 rcssserver-19.0.x 环境中正常启动。
2. 球队主程序在运行时输出标准赛事身份信息，满足 2026 年新增的防作弊要求。
3. 材料能够清楚说明系统结构、当前技术路线与近期验证结果，不夸大能力边界。

当前比赛版本以规则策略为主，代码包内同时提供 CPU 版 RL 完整训练环境，但默认不启用。这一选择的原因是当前提交更强调稳定性与可运行性，而不是高风险的策略试验。

## 3. 系统架构

本队伍基于 Pyrus2D 框架组织比赛逻辑，核心模块如下：

- start.sh：统一解析 Python 运行环境，按顺序拉起 11 个球员进程和 1 个 coach 进程。
- player/main.py：球员主入口，负责参数处理、身份验证输出和 RoboCupPlayerAgent 启动。
- player/decision.py：决策主控入口，组织规则策略、可选 RL 接管与异常回退。
- coach/main.py：教练进程入口，负责队伍级连接与通信。
- base/：规则队伍能力集合，包括阵型管理、无球移动、基本防守、set-play 和守门员逻辑。
- train/：训练环境、状态编码、奖励函数与 PPO 训练循环，随代码包提供，正式比赛默认不进入该链路。
- scripts/run_match.sh：比赛验证脚本，用于启动 rcssserver、对手队伍和本队伍，并汇总比分。

## 4. 关键策略说明

### 4.1 规则策略主导

当前比赛版本由规则策略主导，主要覆盖以下行为：

- 阵型更新与基础站位；
- 非 PlayOn 状态下的 set-play 处理；
- 持球后的推进、踢球和安全回退；
- 无球状态下的移动、防守与基本抢断；
- 守门员专用决策逻辑。

这一设计的优势是解释性强、依赖清晰、部署风险低，适合作为资格审查与正式比赛前的稳定基线。

### 4.2 可选 RL 增强

player/decision.py 保留了 RL 接管入口，但默认比赛版本不启用 ROBOCUP_RL_MODE=1。这意味着：

- 普通比赛启动不会导入 torch/gymnasium，不会加载模型；
- 需要继续训练时，可手动运行 ./train/run_train.sh；
- 若后续要让模型参与正式比赛，需显式设置 ROBOCUP_RL_MODE=1 与 ROBOCUP_RL_MODEL_PATH。

## 5. 本年度技术突破

### 5.1 身份验证合规

根据 2026 规则，球队核心代码必须在运行时直接输出标准赛事信息。本队已在球员主程序中实现如下输出：

> 2026RoboCup机器人世界杯中国赛【${TEAM_NAME}】

该逻辑位于主程序内部，而不是外部脚本，符合规则要求。

### 5.2 验证链路稳定性补强

短赛验证时，rcssserver 在部分情况下不会自动结束进程，导致脚本误判为 timeout。为保证资格审查阶段能稳定回收验证结果，本次提交对比赛验证脚本做了保守修正：

- 先尝试从 rcssserver.log 中解析比分；
- 若比赛结束信号滞后，则回收 .rcg 记录中的最终比分；
- 必要时由脚本主动结束 rcssserver，并在结束后再次读取结果。

这项修改不影响球队比赛逻辑，只用于减少“比赛已完成但验证脚本报错”的误判。

## 6. 当前验证结果

### 6.1 近期短赛验证

- HELIOS_base：${helios_line}
- Cyrus2D_base：${cyrus_line}

![](assets/validation_card.png)

### 6.2 当前判断

- 现有版本已经具备“可启动、可输出身份信息、可完成短赛验证”的基本交付能力；
- 对 HELIOS_base 的短赛结果表明当前规则基线具备一定可运行性；
- 对 Cyrus2D_base 仍处于明显劣势，后续重点应放在失球模式分析、站位与防守协同上；
- 本次提交不对外宣称性能突破，主要强调稳定提交和可执行码完整性。

## 7. 后续计划

后续工作按照以下顺序推进：

1. 继续做 HELIOS 和 Cyrus2D 的稳定回归测试，积累可对比日志。
2. 分析对 Cyrus2D_base 的失球场景，优先修正防线位置与补位问题。
3. 在不破坏现有基线的前提下，逐步将 train/ 中的 RL 能力接入更严格的对照试验流程。
4. 保持比赛版本与资格审查版本底层一致，避免后续合规风险。

## 8. 环境与验证流程

建议的资格审查验证流程如下。以下命令均以代码包解压后的球队根目录为当前目录。

### 8.1 环境确认

先确认比赛环境满足规则要求：

~~~bash
uname -m
rcssserver --version
~~~

预期为：

- 操作系统：Ubuntu 24.04 64-bit
- CPU 架构：x86_64
- 仿真器版本：rcssserver-19.0.x

### 8.2 启动球队并确认身份验证输出

直接使用代码包内置的 Python 运行时启动球队，无需额外执行 pip install：

~~~bash
env -i HOME=/tmp PATH=/usr/local/bin:/usr/bin:/bin timeout 12s ./start.sh
~~~

预期终端输出包含：

~~~text
2026RoboCup机器人世界杯中国赛【${TEAM_NAME}】
~~~

### 8.3 启动本地仿真器并检查联机

先启动本地 rcssserver：

~~~bash
env -i HOME=/tmp PATH=/usr/local/bin:/usr/bin:/bin HALF_TIME_SECONDS=300 NR_NORMAL_HALFS=1 ./scripts/start_local_server.sh 6000
~~~

再在另一个终端启动球队：

~~~bash
env -i HOME=/tmp PATH=/usr/local/bin:/usr/bin:/bin timeout 12s ./start.sh
~~~

预期 rcssserver 日志中出现 11 个球员和 1 个 online coach 连接记录。

### 8.4 短赛验证

如需在本地做一场短赛验证，可使用：

~~~bash
PORT=6110 HALF_TIME_SECONDS=10 MATCH_TIMEOUT=120 ./scripts/run_match.sh helios 1
~~~

如需补充 Cyrus2D 短赛验证，可使用：

~~~bash
PORT=6120 HALF_TIME_SECONDS=10 MATCH_TIMEOUT=120 ./scripts/run_match.sh cyrus2d 1
~~~

如比赛结束信号存在延迟，则依赖脚本从日志与 .rcg 中回收最终比分。

### 8.5 可选 RL 训练

代码包内提供 CPU 版 PyTorch 与 Gymnasium 训练环境，但默认比赛启动不会启用 RL。现场若需要继续训练，机器上仍需已有 rcssserver-19.0.x，可执行：

~~~bash
./train/run_train.sh --episodes 1 --num-workers 1 --device cpu
~~~

训练产物默认写入 log/train/，不属于提交材料清单；若要将模型用于正式比赛，需要另行加入 checkpoint，并显式设置 ROBOCUP_RL_MODE=1 和 ROBOCUP_RL_MODEL_PATH。

本次提交保留了短赛验证结果，便于技术委员会快速确认球队程序具备运行能力。

## 9. 提交材料清单

本次技术资格审查对应的提交材料包括：

- 球队名称；
- 学校名称；
- 队伍成员信息（注明指导老师和领队）；
- 联系邮箱；
- 球队描述文档 PDF；
- 球队可执行代码 zip；

其中，比赛代码包包含默认比赛运行集合与可选 RL 训练环境，不包含 logs、results、opponents 与训练检查点，避免无关文件影响审查。
EOF
}

write_run_instructions() {
  cat >"${RUN_INSTRUCTIONS_FILE}" <<EOF
# ${TEAM_NAME} 运行说明

## 1. 环境要求

- 操作系统：Ubuntu 24.04 64-bit
- 仿真器：rcssserver-19.0.x
- Python：代码包内已自带运行时，默认使用 ./python/bin/python

说明：

- 不需要额外执行 pip install；
- 代码包内包含 CPU 版 RL 训练环境；
- RL 能力默认关闭，不影响可执行码启动。

## 2. 启动入口

~~~bash
./start.sh
~~~

兼容调试参数：

~~~bash
./start.sh ${TEAM_NAME} localhost 6000
~~~

启动脚本会按以下顺序寻找运行时：

1. 环境变量 PYTHON_BIN 指定的 Python
2. 代码包内置 ./python/bin/python
3. 机器上已有的 robocup2d Python 环境
4. 系统 python3（仅作为兜底）

## 3. 身份验证输出

球队主程序启动时会输出：

~~~text
2026RoboCup机器人世界杯中国赛【${TEAM_NAME}】
~~~

## 4. 验证脚本

如需在本地做一场短赛验证，可使用：

~~~bash
PORT=6110 HALF_TIME_SECONDS=10 MATCH_TIMEOUT=120 ./scripts/run_match.sh helios 1
~~~

如果只想手动启动一个本地服务器再连接球队，可使用：

~~~bash
./scripts/start_local_server.sh 6000
./start.sh
~~~

如果把服务器改到非默认端口，必须保持端口组一致：

- player port: PORT
- trainer port: PORT + 1
- online coach port: PORT + 2

脚本位置：

- scripts/run_match.sh
- scripts/parse_result.py
- scripts/start_local_server.sh

## 5. 可选 RL 训练

默认比赛启动不会设置 ROBOCUP_RL_MODE=1，因此不会启用 RL，也不会加载模型。

如需继续训练，机器上需要已有 rcssserver-19.0.x：

~~~bash
./train/run_train.sh --episodes 1 --num-workers 1 --device cpu
~~~

训练产物默认写入 log/train/，不属于提交材料。若要让训练模型进入正式比赛，需要显式设置 ROBOCUP_RL_MODE=1 和 ROBOCUP_RL_MODEL_PATH。

## 6. 代码包内容

代码包包含：

- start.sh
- python/
- player/
- coach/
- base/
- train/
- formations/
- team_config.py
- pyrus2d_bootstrap.py
- .vendor/Pyrus2D
- 必要脚本和本说明文件
EOF
}

write_registration_info() {
  cat >"${REGISTRATION_INFO_FILE}" <<EOF
球队名称：${TEAM_NAME}
学校名称：${SCHOOL_NAME}
队伍成员（请注明指导老师和领队）：
- 指导老师：${ADVISOR_NAME}
- 领队：${LEADER_NAME}
- 队员：${TEAM_MEMBERS}
联系邮箱：${CONTACT_EMAIL}
EOF
}

write_email_template() {
  cat >"${EMAIL_TEMPLATE_FILE}" <<EOF
邮件主题建议：
${TEAM_NAME} - RoboCup 2D 技术资格审查材料提交

邮件正文模板：

老师您好，

现提交 ${TEAM_NAME} 队的 RoboCup 足球机器人比赛仿真 2D 组技术资格审查材料，请查收。

球队名称：${TEAM_NAME}
学校名称：${SCHOOL_NAME}
指导老师：${ADVISOR_NAME}
领队：${LEADER_NAME}
队员：${TEAM_MEMBERS}
联系邮箱：${CONTACT_EMAIL}

附件包括：
1. 球队描述文档 PDF
2. 球队可执行代码 zip

说明：球队名称、学校名称、队伍成员信息与联系邮箱已在正文中列明。

此致
敬礼
EOF
}

render_description_pdf() {
  local html_file="${SRC_DIR}/description.html"
  pandoc "${SRC_DIR}/description.md" \
    --resource-path="${OUTPUT_DIR}:${PROJECT_ROOT}" \
    -s \
    -t html5 \
    --css "${SRC_DIR}/print.css" \
    --metadata title="${TEAM_NAME} 球队描述文档" \
    -o "${html_file}"

  google-chrome \
    --headless \
    --disable-gpu \
    --allow-file-access-from-files \
    --no-first-run \
    --no-pdf-header-footer \
    "--print-to-pdf=${DESCRIPTION_PDF}" \
    "file://${html_file}" >/dev/null 2>&1
}

copy_package_item() {
  local src="$1"
  local dest="$2"

  mkdir -p "$(dirname "${dest}")"
  cp -a "${src}" "${dest}"
}

copy_train_sources() {
  mkdir -p "${CODE_STAGE_DIR}/train"
  rsync -a \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='*.pt' \
    --exclude='*.pth' \
    --exclude='*.ckpt' \
    --exclude='checkpoints*' \
    "${PROJECT_ROOT}/train/" "${CODE_STAGE_DIR}/train/"
  chmod +x "${CODE_STAGE_DIR}/train/run_train.sh"
}

copy_python_distribution_closure() {
  local runtime_python="$1"
  local dest_site_packages="$2"
  shift 2

  "${runtime_python}" - "${dest_site_packages}" "$@" <<'PY'
from __future__ import annotations

import re
import shutil
import sys
from collections import deque
from importlib import metadata
from pathlib import Path

try:
    from packaging.markers import default_environment
    from packaging.requirements import Requirement
except Exception:  # pragma: no cover - build environment fallback
    Requirement = None
    default_environment = None


dest_root = Path(sys.argv[1]).resolve()
roots = list(sys.argv[2:])
dest_root.mkdir(parents=True, exist_ok=True)


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_requirement(raw: str) -> str | None:
    if Requirement is not None:
        req = Requirement(raw)
        if req.marker is not None and default_environment is not None:
            if not req.marker.evaluate(default_environment()):
                return None
        return req.name

    name = raw.split(";", 1)[0].strip()
    name = re.split(r"[\s<>=!~\[]", name, maxsplit=1)[0]
    return name or None


def copy_recorded_file(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst = dst.resolve()
    if not dst.is_relative_to(dest_root):
        return
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
        return
    if src.name.endswith((".pyc", ".pyo")) or "__pycache__" in src.parts:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


queue: deque[str] = deque(roots)
seen: set[str] = set()
copied: list[str] = []

while queue:
    requested = queue.popleft()
    key = canonical(requested)
    if key in seen:
        continue
    seen.add(key)

    try:
        dist = metadata.distribution(requested)
    except metadata.PackageNotFoundError as exc:
        missing = ", ".join(roots)
        raise SystemExit(
            f"missing Python distribution {requested!r}. "
            f"Install CPU RL dependencies before building, for example: "
            f"python -m pip install --index-url https://download.pytorch.org/whl/cpu torch "
            f"&& python -m pip install gymnasium. Required roots: {missing}"
        ) from exc

    dist_name = dist.metadata.get("Name", requested)
    copied.append(f"{dist_name}=={dist.version}")

    for file in dist.files or ():
        parts = file.parts
        if "__pycache__" in parts or str(file).endswith((".pyc", ".pyo")):
            continue
        copy_recorded_file(Path(dist.locate_file(file)), dest_root / file)

    for raw_req in dist.requires or ():
        dep_name = parse_requirement(raw_req)
        if dep_name:
            queue.append(dep_name)

print("copied Python distributions:")
for item in copied:
    print(f"  - {item}")
PY
}

build_embedded_python_runtime() {
  local runtime_python source_env python_version runtime_root stdlib_root

  runtime_python="$(resolve_runtime_python)"
  source_env="$(cd "$(dirname "${runtime_python}")/.." && pwd)"
  python_version="$("${runtime_python}" - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"

  runtime_root="${CODE_STAGE_DIR}/python"
  stdlib_root="${source_env}/lib/python${python_version}"

  mkdir -p "${runtime_root}/bin" "${runtime_root}/lib/python${python_version}/site-packages"

  cp -a "${source_env}/bin/python${python_version}" "${runtime_root}/bin/python${python_version}"
  find "${source_env}/lib" -maxdepth 1 \( -type f -o -type l \) \( -name '*.so' -o -name '*.so.*' \) -exec cp -a {} "${runtime_root}/lib/" \;

  cat >"${runtime_root}/bin/python" <<EOF
#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_ROOT="\$(cd "\${SCRIPT_DIR}/.." && pwd)"

export PYTHONHOME="\${RUNTIME_ROOT}"
export LD_LIBRARY_PATH="\${RUNTIME_ROOT}/lib\${LD_LIBRARY_PATH:+:\${LD_LIBRARY_PATH}}"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
unset PYTHONPATH

exec "\${SCRIPT_DIR}/python${python_version}" "\$@"
EOF
  chmod +x "${runtime_root}/bin/python"
  ln -sf python "${runtime_root}/bin/python3"

  rsync -a \
    --exclude='site-packages' \
    --exclude='__pycache__' \
    --exclude='test' \
    --exclude='tests' \
    --exclude='tkinter' \
    --exclude='turtledemo' \
    --exclude='idlelib' \
    --exclude='ensurepip' \
    --exclude='distutils' \
    --exclude='lib2to3' \
    "${stdlib_root}/" "${runtime_root}/lib/python${python_version}/"

  mkdir -p "${runtime_root}/lib/python${python_version}/site-packages"
  copy_python_distribution_closure \
    "${runtime_python}" \
    "${runtime_root}/lib/python${python_version}/site-packages" \
    pyrusgeom \
    coloredlogs \
    humanfriendly \
    numpy \
    scipy \
    torch \
    gymnasium

  find "${runtime_root}" -type d -name '__pycache__' -prune -exec rm -rf {} +
  find "${runtime_root}" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
}

build_code_bundle() {
  rm -rf "${OUTPUT_DIR}/code_stage"
  mkdir -p "${CODE_STAGE_DIR}" "${CODE_STAGE_DIR}/scripts"

  copy_package_item "${PROJECT_ROOT}/start.sh" "${CODE_STAGE_DIR}/start.sh"
  copy_package_item "${PROJECT_ROOT}/player" "${CODE_STAGE_DIR}/player"
  copy_package_item "${PROJECT_ROOT}/coach" "${CODE_STAGE_DIR}/coach"
  copy_package_item "${PROJECT_ROOT}/base" "${CODE_STAGE_DIR}/base"
  copy_train_sources
  copy_package_item "${PROJECT_ROOT}/formations" "${CODE_STAGE_DIR}/formations"
  copy_package_item "${PROJECT_ROOT}/team_config.py" "${CODE_STAGE_DIR}/team_config.py"
  copy_package_item "${PROJECT_ROOT}/pyrus2d_bootstrap.py" "${CODE_STAGE_DIR}/pyrus2d_bootstrap.py"
  copy_package_item "${PROJECT_ROOT}/scripts/run_match.sh" "${CODE_STAGE_DIR}/scripts/run_match.sh"
  copy_package_item "${PROJECT_ROOT}/scripts/parse_result.py" "${CODE_STAGE_DIR}/scripts/parse_result.py"
  copy_package_item "${PROJECT_ROOT}/scripts/start_local_server.sh" "${CODE_STAGE_DIR}/scripts/start_local_server.sh"
  copy_package_item "${PROJECT_ROOT}/.vendor/Pyrus2D" "${CODE_STAGE_DIR}/.vendor/Pyrus2D"
  copy_package_item "${RUN_INSTRUCTIONS_FILE}" "${CODE_STAGE_DIR}/RUN_INSTRUCTIONS.md"
  copy_package_item "${RUN_INSTRUCTIONS_FILE}" "${CODE_STAGE_DIR}/README.md"
  build_embedded_python_runtime

  find "${CODE_STAGE_DIR}" -type d -name '__pycache__' -prune -exec rm -rf {} +
  find "${CODE_STAGE_DIR}" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

  (
    cd "${OUTPUT_DIR}/code_stage"
    zip -qr "${CODE_ZIP_FILE}" "${TEAM_NAME}"
  )
}

build_submission_bundle_zip() {
  (
    cd "${OUTPUT_DIR}"
    zip -q "${SUBMISSION_ZIP_FILE}" \
      "$(basename "${REGISTRATION_INFO_FILE}")" \
      "$(basename "${DESCRIPTION_PDF}")" \
      "$(basename "${CODE_ZIP_FILE}")"
  )
}

main() {
  require_cmd python3
  require_cmd pandoc
  require_cmd google-chrome
  require_cmd zip
  require_cmd rsync

  local runtime_python
  runtime_python="$(resolve_runtime_python)"
  require_runtime_python_distributions "${runtime_python}" torch gymnasium

  mkdir -p "${SRC_DIR}" "${ASSET_DIR}"

  local helios_report cyrus_report helios_line cyrus_line validation_log
  helios_report="$(resolve_latest_match_report 'helios_*.txt')"
  cyrus_report="$(resolve_latest_match_report 'cyrus2d_*.txt')"

  helios_line="$(extract_first_match_line "${helios_report}" || true)"
  cyrus_line="$(extract_first_match_line "${cyrus_report}" || true)"

  if [[ -z "${helios_line}" ]]; then
    helios_line='暂无 HELIOS 短赛结果，请在生成提交物前补跑验证。'
  fi
  if [[ -z "${cyrus_line}" ]]; then
    cyrus_line='暂无 Cyrus2D 短赛结果，请在赛前调试阶段补跑。'
  fi

  validation_log=$'Evidence:\n- 身份验证输出位于 player/main.py\n- 短赛验证入口：scripts/run_match.sh\n- 若结束判定滞后，则由脚本回收 rcssserver.log / .rcg 最终比分'

  write_validation_card_html "${helios_line}" "${cyrus_line}" "${validation_log}"
  render_validation_card_png
  write_print_css
  write_description_markdown "${helios_line}" "${cyrus_line}"
  write_registration_info
  write_run_instructions
  write_email_template
  if [[ "${INCLUDE_TECH_SLIDES}" == "1" ]]; then
    write_slides_markdown "${helios_line}" "${cyrus_line}"
    pandoc "${SRC_DIR}/slides.md" \
      --resource-path="${OUTPUT_DIR}:${PROJECT_ROOT}" \
      -t pptx \
      -o "${OUTPUT_DIR}/${TEAM_NAME}_slides.pptx"
  fi
  render_description_pdf
  build_code_bundle
  build_submission_bundle_zip

  log "generated: ${OUTPUT_DIR}"
  log "registration info: ${REGISTRATION_INFO_FILE}"
  log "description: ${DESCRIPTION_PDF}"
  log "code zip: ${CODE_ZIP_FILE}"
  log "bundle zip: ${SUBMISSION_ZIP_FILE}"
}

main "$@"
