# RoboCup 2D 项目交付说明

## 1. 项目概览

本仓库是我们用于 2026 RoboCup 中国赛的 2D 仿真足球队伍代码。

当前整体结构：

- 规则队伍主逻辑在 `base/` 和 `player/decision.py`
- 单个球员的 RL 增强逻辑在 `train/`
- 比赛评测脚本在 `scripts/`
- 内置的 Pyrus2D 框架在 `.vendor/Pyrus2D`

当前队名：

- `Pyrus433`

当前短期目标：

- 降低对 `Cyrus2D_base` 的失球数
- 提升系统稳定性，保证连续回归测试时不出现 crash/timeout

## 2. Windows 队员必须使用的环境

如果你使用的是 Windows，不要在原生 Windows Python 环境里直接跑这个项目。

统一使用：

- `WSL2`
- `Ubuntu 24.04`
- Ubuntu 内的 `Miniconda` 或 `Anaconda`

Windows 侧推荐安装命令：

```powershell
wsl --install -d Ubuntu-24.04
```

Ubuntu 装好之后，后续所有命令都在 Ubuntu 终端里执行。

为什么必须用 Ubuntu：

- `install_robocup_sim.sh` 依赖 `apt`、`sudo`、`ldconfig`
- `scripts/run_match.sh` 和 `run_all.sh` 依赖 Linux 进程控制能力，比如 `kill`、`pkill`、`LD_LIBRARY_PATH`
- `scripts/setup_opponents.sh` 需要在 Linux 下编译对手和相关 C/C++ 依赖

## 3. 一次性环境安装

### 3.1 克隆仓库

```bash
git clone <your-repo-url> robocup
cd robocup
```

### 3.2 在 Ubuntu 里安装 Miniconda

如果 WSL 里还没有 conda，先装 Miniconda。

装好后确认：

```bash
conda --version
```

### 3.3 安装 RoboCup 仿真器和 Python 依赖

执行：

```bash
bash install_robocup_sim.sh
```

这个脚本会自动完成：

- 安装 Linux 构建依赖
- 安装 `rcssserver` 19.0.x
- 安装 `rcssmonitor` 19.0.x
- 创建 conda 环境 `robocup2d`
- 安装 `pyrus2d`、`torch`、`numpy`、`pyrusgeom` 等依赖

注意：

- 脚本中会调用 `sudo ldconfig`
- 第一次执行时，通常需要在终端里输入一次 sudo 密码
- 如果脚本中途被打断，`robocup2d` 环境里的 Python 包可能不会装全，需要重新执行

安装完成后激活环境：

```bash
conda activate robocup2d
```

### 3.4 编译对手队伍

执行：

```bash
bash scripts/setup_opponents.sh
```

这个脚本会准备：

- `Cyrus2D_base`
- `HELIOS_base`
- 本地 `librcsc` 编译结果，位于 `opponents/local_cyrus` 和 `opponents/local_helios`

## 4. 安装后快速验证

环境装完后，至少跑完下面这些检查。

### 4.1 验证仿真器二进制

```bash
command -v rcssserver
command -v rcssmonitor
rcssserver --version || true
rcssmonitor --version
```

说明：

- `rcssserver --version` 在当前 19.0.0 版本下会打印版本信息，但退出码不一定是 0，这不代表安装失败

### 4.2 验证 Python 环境

```bash
conda activate robocup2d
python -c "import pyrusgeom, torch, numpy"
```

### 4.3 跑一场集成验证

```bash
PORT=6100 HALF_TIME_SECONDS=10 MATCH_TIMEOUT=90 ./scripts/run_match.sh helios 1
```

预期结果：

- `logs/matches/` 下生成详细日志
- `results/` 下尝试生成结果报告

结果文件示例：

- `results/helios_<timestamp>.txt`

说明：

- 默认 `PORT=6000`，如果本机已有其他训练或比赛实例在跑，可能会报 `Address already in use`
- 冒烟测试建议先用空闲端口，比如 `6100`
- 上面这条命令是缩短版集成验证，更适合先确认启动链路
- `HALF_TIME_SECONDS` 的单位是秒，不是 cycle
- 正常的完整 benchmark 再使用默认比赛长度；当前默认是每半场 `300` 秒
- 截至 `2026-03-29` 的沙盒验证中，环境安装和对手编译已通过，但缩短版比赛仍可能因为比赛结束时序而触发 timeout
- 如果命令返回 timeout，请优先检查对应 `rcssserver.log` 里是否已经出现 `Game Results`

## 5. 日常常用命令

### 5.1 跑 HELIOS 对局

```bash
conda activate robocup2d
./scripts/run_match.sh helios 3
```

### 5.2 跑 Cyrus 对局

```bash
conda activate robocup2d
./scripts/run_match.sh cyrus2d 3
```

如果 `6000` 端口被占用，可以改端口：

```bash
conda activate robocup2d
PORT=6100 ./scripts/run_match.sh helios 3
```

### 5.3 打开可视化监视器

```bash
conda activate robocup2d
VISUAL=1 ./scripts/run_match.sh helios 1
```

### 5.4 启动 RL 训练

注意：

- `install_robocup_sim.sh` 默认创建 `robocup2d`
- `train/run_train.sh` 默认查找 `ROBOCUP_TRAIN_CONDA_ENV=rl_robot`

为了避免环境名不一致，训练时统一用下面这条：

```bash
conda activate robocup2d
ROBOCUP_TRAIN_CONDA_ENV=robocup2d ./train/run_train.sh --episodes 100
```

如果训练时需要显式指定球员进程用哪个 Python，可以用：

```bash
conda activate robocup2d
ROBOCUP_TRAIN_CONDA_ENV=robocup2d \
ROBOCUP_PLAYER_PYTHON="$HOME/miniconda3/envs/robocup2d/bin/python" \
./train/run_train.sh --episodes 100
```

## 6. 重要路径

- 队伍配置：`team_config.py`
- 球员决策主逻辑：`player/decision.py`
- 规则队伍主逻辑：`base/`
- RL 训练主循环：`train/train_loop.py`
- RL 动作空间：`train/action.py`
- RL 奖励定义：`train/reward.py`
- 队伍启动脚本：`start.sh`
- 比赛运行脚本：`scripts/run_match.sh`
- 对手安装脚本：`scripts/setup_opponents.sh`
- 比分解析脚本：`scripts/parse_result.py`
- 比赛结果报告：`results/`
- 比赛日志：`logs/matches/`
- 训练日志：`logs/train/`

## 7. 输出文件位置

### 7.1 比赛结果报告

每次 benchmark 都会在 `results/` 下生成一个文本结果文件。

示例：

```text
results/cyrus2d_20260328_220517.txt
```

结果文件会汇总：

- 对手是谁
- 打了几场
- 每场比分
- 总 W-D-L

### 7.2 比赛详细日志

每次 benchmark 的详细日志在：

```text
logs/matches/<opponent>_<timestamp>/match_001/
```

常见文件：

- `rcssserver.log`
- `home_launcher.log`
- `opponent_launcher.log`
- `server_records/*.rcg`

### 7.3 训练日志

RL 训练日志在：

```text
logs/train/
```

每个 episode 或 worker 都会写自己的子目录和日志。

## 8. 当前项目状态

状态统计日期：

- `2026-03-29`

根据 `results/` 中已有比赛记录汇总：

- 对 `Cyrus2D_base`：32 场有效比赛里 `0-5-27`，另有 5 场异常结束，场均进球 `0.09`，场均失球 `2.31`
- 对 `HELIOS_base`：2 场有效比赛里 `1-1-0`，另有 1 场异常结束，场均进球 `0.50`，场均失球 `0.00`

当前判断：

- 对 `HELIOS_base` 已经有一定竞争力
- 对 `Cyrus2D_base` 仍明显落后
- 稳定性还不够，因为历史上已经出现过多次 timeout/crash 异常

## 9. 当前已知问题

- 部分 benchmark 会出现 `ERROR timeout or server crash`
- 部分比赛会出现 `ERROR failed to parse score from .../rcssserver.log`
- 训练环境名默认不一致，建议显式设置 `ROBOCUP_TRAIN_CONDA_ENV=robocup2d`
- 当前 RL 默认只控制一个球员：`10 号`
- 如果本机已有其他实例占用 `6000/6001/6002`，比赛脚本会启动失败，需要改 `PORT`
- 缩短版集成验证在当前代码库里不保证稳定产出结果文件，必要时应查看 `logs/matches/.../rcssserver.log` 中是否已有 `Game Results`

## 10. 建议队内分工

### 主开发 / 最终合版负责人

- 修改 `player/decision.py`
- 修改 `base/`
- 决定 RL 改动是否并入比赛版本
- 负责最终比赛版本

### 测试与评测负责人

- 执行 `./scripts/run_match.sh helios 3`
- 执行 `./scripts/run_match.sh cyrus2d 3`
- 记录比分、异常、回归结果
- 总结失球模式

### 交付与环境负责人

- 在干净的 `WSL2 + Ubuntu 24.04` 环境里复现安装
- 记录所有环境问题
- 维护这份交付文档

## 11. 最低交付检查清单

在说“可以交付”之前，至少确认下面这些都通过：

- Ubuntu 环境确认为 `WSL2 + Ubuntu 24.04`
- `conda activate robocup2d` 可用
- `python -c "import pyrusgeom, torch"` 可用
- `rcssserver --version` 可用
- `bash scripts/setup_opponents.sh` 能完整执行
- `./scripts/run_match.sh helios 1` 能产出结果文件
- `./scripts/run_match.sh cyrus2d 1` 能产出结果文件
- 接手人能正常查看 `results/` 和 `logs/matches/`

## 12. 接手后的第一批动作

接手仓库后，先做下面几件事：

1. 完成环境安装和冒烟测试。
2. 重新跑 `HELIOS` 3 场。
3. 重新跑 `Cyrus` 3 场。
4. 确认没有新增 timeout/crash。
5. 确认环境稳定后，再开始改队伍逻辑或训练。
