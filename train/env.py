from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from train import bridge, config
from train.reward import compute_reward
from train.state import StateSnapshot, snapshot_from_message


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _supports_pyrus2d(candidate: str) -> bool:
    try:
        result = subprocess.run(
            [candidate, "-c", "import pyrusgeom"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def resolve_player_python() -> str:
    candidate = os.environ.get("ROBOCUP_PLAYER_PYTHON", "").strip()
    candidates = [
        candidate,
        str(Path.home() / "anaconda3/envs/robocup2d/bin/python"),
        str(Path.home() / "miniconda3/envs/robocup2d/bin/python"),
        sys.executable,
        shutil.which("python3") or "",
    ]
    for item in candidates:
        if item and Path(item).exists() and _supports_pyrus2d(item):
            return item
    return sys.executable


class RoboCupEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        train_team_name: str = config.TRAIN_TEAM_NAME,
        opponent_team_name: str = config.OPPONENT_TEAM_NAME,
        control_unum: int = config.CONTROL_UNUM,
        server_host: str = config.SERVER_HOST,
        server_port: int = config.SERVER_PORT,
        env_id: str = "env0",
    ):
        super().__init__()
        self.observation_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(config.OBSERVATION_SIZE,),
            dtype=np.float32,
        )
        self.action_space = spaces.Discrete(config.ACTION_SIZE)

        self.train_team_name = train_team_name
        self.opponent_team_name = opponent_team_name
        self.control_unum = control_unum
        self.server_host = server_host
        self.server_port = server_port
        self.env_id = env_id
        self.player_python = resolve_player_python()
        self.start_script = PROJECT_ROOT / "start.sh"
        self.rcssserver_bin = config.RCSSSERVER_BIN

        self._bridge = bridge.start_bridge_server()
        self._episode_index = 0
        self._episode_id: str | None = None
        self._procs: list[subprocess.Popen] = []
        self._log_handles = []
        self._last_snapshot: StateSnapshot | None = None
        self._last_observation = np.zeros(config.OBSERVATION_SIZE, dtype=np.float32)
        self._episode_steps = 0
        self._stuck_ball_counter = 0
        self._stuck_ball_last_pos: tuple[float, float] | None = None
        self._stuck_ball_check_interval = 30
        self._stuck_ball_max_count = 5
        self._stuck_ball_min_move = 1.5

    def _episode_log_dir(self) -> Path:
        if self._episode_id is None:
            raise RuntimeError("episode id is not initialized")
        log_dir = PROJECT_ROOT / config.HOME_LOG_SUBDIR / self._episode_id
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    def _spawn(self, args: list[str], env: dict, log_path: Path, cwd: Path | None = None) -> subprocess.Popen:
        log_handle = log_path.open("w", encoding="utf-8")
        self._log_handles.append(log_handle)
        proc = subprocess.Popen(
            args,
            cwd=str(cwd or PROJECT_ROOT),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self._procs.append(proc)
        return proc

    def _launch_server(self, episode_log_dir: Path) -> None:
        if shutil.which(self.rcssserver_bin) is None and not Path(self.rcssserver_bin).exists():
            raise FileNotFoundError(f"rcssserver not found: {self.rcssserver_bin}")

        server_env = os.environ.copy()
        existing_ld = server_env.get("LD_LIBRARY_PATH", "")
        server_env["LD_LIBRARY_PATH"] = f"/usr/local/lib:{existing_ld}" if existing_ld else "/usr/local/lib"
        server_record_dir = episode_log_dir / "server_records"
        server_record_dir.mkdir(parents=True, exist_ok=True)

        args = [
            self.rcssserver_bin,
            f"server::port={self.server_port}",
            f"server::coach_port={self.server_port + 1}",
            f"server::olcoach_port={self.server_port + 2}",
            f"server::game_log_dir={server_record_dir}",
            f"server::text_log_dir={server_record_dir}",
            f"server::keepaway_log_dir={server_record_dir}",
            "server::coach_w_referee=true",
            "server::auto_mode=true",
            f"server::connect_wait={config.SERVER_CONNECT_WAIT}",
            f"server::kick_off_wait={config.SERVER_KICK_OFF_WAIT}",
            f"server::game_over_wait={config.SERVER_GAME_OVER_WAIT}",
        ]
        self._spawn(args, server_env, episode_log_dir / "rcssserver.log", cwd=server_record_dir)
        time.sleep(1.0)

    def _team_env(self, rl_enabled: bool, team_log_dir: Path) -> dict:
        env = os.environ.copy()
        env["PYTHON_BIN"] = self.player_python
        env["LOG_DIR"] = str(team_log_dir)
        env["ROBOCUP_RL_MODE"] = "1" if rl_enabled else "0"
        env["ROBOCUP_RL_CONTROL_UNUM"] = str(self.control_unum)

        if rl_enabled:
            env[config.BRIDGE_HOST_ENV] = self._bridge.host
            env[config.BRIDGE_PORT_ENV] = str(self._bridge.port)
            env[config.BRIDGE_AUTHKEY_ENV] = self._bridge.authkey
            env[config.EPISODE_ID_ENV] = self._episode_id or ""
        else:
            env.pop(config.BRIDGE_HOST_ENV, None)
            env.pop(config.BRIDGE_PORT_ENV, None)
            env.pop(config.BRIDGE_AUTHKEY_ENV, None)
            env.pop(config.EPISODE_ID_ENV, None)

        return env

    def _launch_team(self, team_name: str, rl_enabled: bool, episode_log_dir: Path, tag: str) -> None:
        team_log_dir = episode_log_dir / tag
        team_log_dir.mkdir(parents=True, exist_ok=True)
        env = self._team_env(rl_enabled=rl_enabled, team_log_dir=team_log_dir)
        args = [
            str(self.start_script),
            team_name,
            self.server_host,
            str(self.server_port),
        ]
        self._spawn(args, env, episode_log_dir / f"{tag}_launcher.log")
        time.sleep(config.PLAYER_START_DELAY)

    def _launch_match(self) -> None:
        episode_log_dir = self._episode_log_dir()
        self._launch_server(episode_log_dir)
        self._launch_team(self.train_team_name, rl_enabled=True, episode_log_dir=episode_log_dir, tag="home")
        self._launch_team(self.opponent_team_name, rl_enabled=False, episode_log_dir=episode_log_dir, tag="away")

    def _match_running(self) -> bool:
        return any(proc.poll() is None for proc in self._procs)

    def _terminate_proc(self, proc: subprocess.Popen) -> None:
        if proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                return
            proc.wait(timeout=5.0)

    def _cleanup_match(self) -> None:
        for proc in reversed(self._procs):
            self._terminate_proc(proc)
        self._procs.clear()

        for handle in self._log_handles:
            handle.close()
        self._log_handles.clear()

    def _episode_info(self, snapshot: StateSnapshot | None, extra: dict | None = None) -> dict:
        extra = extra or {}
        if snapshot is None:
            return extra
        info = {
            "episode_id": snapshot.episode_id,
            "cycle": snapshot.cycle,
            "request_id": snapshot.request_id,
            "goals_scored": snapshot.our_score,
            "goals_conceded": snapshot.opponent_score,
            "game_mode": snapshot.game_mode,
            "prev_action_source": snapshot.prev_action_source,
        }
        info.update(extra)
        return info

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        self.close()
        bridge.drain_bridge_queues()

        self._episode_index += 1
        self._episode_id = f"{self.env_id}_episode_{self._episode_index:06d}_{int(time.time() * 1000)}"
        self._episode_steps = 0
        self._last_snapshot = None
        self._last_observation = np.zeros(config.OBSERVATION_SIZE, dtype=np.float32)
        self._stuck_ball_counter = 0
        self._stuck_ball_last_pos = None
        self._stuck_ball_check_interval = 30
        self._stuck_ball_max_count = 5
        self._stuck_ball_min_move = 1.5

        self._launch_match()

        initial_message = bridge.get_state_message(
            timeout=config.STATE_TIMEOUT_SEC,
            episode_id=self._episode_id,
        )
        if initial_message is None:
            self._cleanup_match()
            raise TimeoutError("timed out waiting for initial RL state")

        snapshot = snapshot_from_message(initial_message)
        self._last_snapshot = snapshot
        self._last_observation = snapshot.observation.copy()
        return self._last_observation.copy(), self._episode_info(snapshot)

    def step(self, action: int):
        if self._last_snapshot is None or self._episode_id is None:
            raise RuntimeError("reset() must be called before step()")

        action_id = int(action)
        sent = bridge.put_action_message(
            {
                "episode_id": self._episode_id,
                "request_id": self._last_snapshot.request_id,
                "action_id": action_id,
            },
            timeout=config.ACTION_TIMEOUT_SEC,
        )
        if not sent:
            info = self._episode_info(self._last_snapshot, {"action_queue_timeout": True})
            self._cleanup_match()
            return self._last_observation.copy(), 0.0, False, True, info

        next_message = bridge.get_state_message(
            timeout=config.STATE_TIMEOUT_SEC,
            episode_id=self._episode_id,
            min_request_id=self._last_snapshot.request_id + 1,
        )
        if next_message is None:
            done = not self._match_running()
            info = self._episode_info(self._last_snapshot, {"state_queue_timeout": True})
            self._cleanup_match()
            return self._last_observation.copy(), 0.0, done, True, info

        next_snapshot = snapshot_from_message(next_message)
        reward = compute_reward(self._last_snapshot, next_snapshot, action_id)
        self._episode_steps += 1

        done = next_snapshot.game_mode == "time_over"
        truncated = self._episode_steps >= config.MAX_EPISODE_STEPS

        self._last_snapshot = next_snapshot
        self._last_observation = next_snapshot.observation.copy()
        info = self._episode_info(next_snapshot, {"episode_steps": self._episode_steps})

        if self._episode_steps % self._stuck_ball_check_interval == 0:
            current_ball_pos = (next_snapshot.ball_x, next_snapshot.ball_y)
            if self._stuck_ball_last_pos is not None:
                delta_x = current_ball_pos[0] - self._stuck_ball_last_pos[0]
                delta_y = current_ball_pos[1] - self._stuck_ball_last_pos[1]
                ball_move = float(np.hypot(delta_x, delta_y))
                if ball_move < self._stuck_ball_min_move:
                    self._stuck_ball_counter += 1
                else:
                    self._stuck_ball_counter = 0
            self._stuck_ball_last_pos = current_ball_pos

            if self._stuck_ball_counter >= self._stuck_ball_max_count:
                truncated = True
                info["truncation_reason"] = "stuck_ball"
                self._cleanup_match()

        if done or truncated:
            self._cleanup_match()

        return self._last_observation.copy(), reward, done, truncated, info

    def close(self) -> None:
        self._cleanup_match()
        bridge.drain_bridge_queues()
