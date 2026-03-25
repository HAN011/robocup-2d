from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.distributions import Categorical

from train import config
from train.env import RoboCupEnv
from train.policy_net import ActorCriticPolicy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a RoboCup 2D PPO policy")
    parser.add_argument("--resume", nargs="?", const="latest", default=None, help="resume from checkpoint path or latest")
    parser.add_argument("--episodes", type=int, default=config.TOTAL_EPISODES, help="number of training episodes")
    parser.add_argument("--device", default="auto", help="training device: auto/cpu/cuda")
    parser.add_argument(
        "--rollout-device",
        default=config.ROLLOUT_DEVICE,
        help="device used inside rollout workers; cpu is recommended for multi-worker sampling",
    )
    parser.add_argument("--control-unum", type=int, default=config.CONTROL_UNUM, help="controlled player uniform number")
    parser.add_argument("--num-workers", type=int, default=config.NUM_WORKERS, help="number of parallel rollout workers")
    parser.add_argument("--base-port", type=int, default=config.SERVER_PORT, help="base rcssserver port for worker 0")
    parser.add_argument(
        "--port-stride",
        type=int,
        default=config.SERVER_PORT_STRIDE,
        help="port gap between rollout workers to avoid collisions",
    )
    parser.add_argument(
        "--heartbeat-interval",
        type=int,
        default=config.HEARTBEAT_INTERVAL,
        help="print a heartbeat every N environment steps; set 0 to disable",
    )
    return parser


def resolve_device(device_name: str) -> torch.device:
    if device_name == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device_name)


def latest_checkpoint(checkpoint_dir: Path) -> Path | None:
    checkpoints = sorted(checkpoint_dir.glob("ppo_episode_*.pt"))
    return checkpoints[-1] if checkpoints else None


def load_checkpoint(
    model: ActorCriticPolicy,
    optimizer: torch.optim.Optimizer,
    checkpoint_path: Path,
    device: torch.device,
) -> int:
    payload = torch.load(checkpoint_path, map_location=device)
    state_dict = payload["model_state_dict"]

    actor_bias = state_dict.get("actor.bias")
    if actor_bias is not None and int(actor_bias.shape[0]) != config.ACTION_SIZE:
        raise ValueError(
            "incompatible checkpoint: {path} was trained with action_size={ckpt_size}, "
            "but current code expects action_size={current_size}. "
            "The action space changed, so start a fresh run without --resume."
            .format(
                path=checkpoint_path,
                ckpt_size=int(actor_bias.shape[0]),
                current_size=config.ACTION_SIZE,
            )
        )

    try:
        model.load_state_dict(state_dict)
    except RuntimeError as exc:
        raise ValueError(
            f"incompatible checkpoint: {checkpoint_path}. "
            "Model architecture does not match the current code. "
            "Start a fresh run without --resume."
        ) from exc
    optimizer.load_state_dict(payload["optimizer_state_dict"])
    return int(payload.get("episode", 0)) + 1


def save_checkpoint(
    model: ActorCriticPolicy,
    optimizer: torch.optim.Optimizer,
    checkpoint_dir: Path,
    episode: int,
) -> Path:
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    path = checkpoint_dir / f"ppo_episode_{episode:06d}.pt"
    torch.save(
        {
            "episode": episode,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
        },
        path,
    )
    model.save(checkpoint_dir / "policy_latest.pt")
    return path


def compute_gae(
    rewards: np.ndarray,
    values: np.ndarray,
    dones: np.ndarray,
    gamma: float,
    gae_lambda: float,
) -> tuple[np.ndarray, np.ndarray]:
    advantages = np.zeros_like(rewards, dtype=np.float32)
    gae = 0.0
    next_value = 0.0

    for index in range(len(rewards) - 1, -1, -1):
        mask = 1.0 - float(dones[index])
        delta = rewards[index] + gamma * next_value * mask - values[index]
        gae = delta + gamma * gae_lambda * mask * gae
        advantages[index] = gae
        next_value = values[index]

    returns = advantages + values
    return advantages, returns


def update_policy(
    model: ActorCriticPolicy,
    optimizer: torch.optim.Optimizer,
    trajectory: dict[str, np.ndarray],
    device: torch.device,
) -> None:
    observations = torch.as_tensor(trajectory["observations"], dtype=torch.float32, device=device)
    actions = torch.as_tensor(trajectory["actions"], dtype=torch.int64, device=device)
    old_log_probs = torch.as_tensor(trajectory["log_probs"], dtype=torch.float32, device=device)
    returns = torch.as_tensor(trajectory["returns"], dtype=torch.float32, device=device)
    advantages = torch.as_tensor(trajectory["advantages"], dtype=torch.float32, device=device)
    advantages = (advantages - advantages.mean()) / (advantages.std(unbiased=False) + 1.0e-8)

    num_samples = observations.shape[0]
    if num_samples == 0:
        return

    for _ in range(config.EPOCHS_PER_UPDATE):
        permutation = torch.randperm(num_samples, device=device)
        for start in range(0, num_samples, config.BATCH_SIZE):
            batch_index = permutation[start : start + config.BATCH_SIZE]
            batch_obs = observations[batch_index]
            batch_actions = actions[batch_index]
            batch_old_log_probs = old_log_probs[batch_index]
            batch_returns = returns[batch_index]
            batch_advantages = advantages[batch_index]

            action_probs, state_values = model(batch_obs)
            dist = Categorical(action_probs)
            new_log_probs = dist.log_prob(batch_actions)
            entropy = dist.entropy().mean()

            ratios = torch.exp(new_log_probs - batch_old_log_probs)
            unclipped = ratios * batch_advantages
            clipped = torch.clamp(ratios, 1.0 - config.CLIP_EPSILON, 1.0 + config.CLIP_EPSILON) * batch_advantages

            policy_loss = -torch.min(unclipped, clipped).mean()
            value_loss = F.mse_loss(state_values.squeeze(-1), batch_returns)
            loss = (
                policy_loss
                + config.VALUE_LOSS_COEF * value_loss
                - config.ENTROPY_COEF * entropy
            )

            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.MAX_GRAD_NORM)
            optimizer.step()


def merge_trajectories(trajectories: list[dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
    if not trajectories:
        raise ValueError("no trajectories to merge")

    merged = {}
    for key in trajectories[0]:
        merged[key] = np.concatenate([trajectory[key] for trajectory in trajectories], axis=0)
    return merged


def worker_policy_state_dict(model: ActorCriticPolicy) -> dict[str, torch.Tensor]:
    return {key: value.detach().cpu() for key, value in model.state_dict().items()}


def collect_episode(
    env: RoboCupEnv,
    model: ActorCriticPolicy,
    device: torch.device,
    episode: int,
    heartbeat_interval: int,
    worker_label: str = "main",
) -> tuple[dict[str, np.ndarray], dict]:
    observation, info = env.reset()
    episode_reward = 0.0

    observations = []
    actions = []
    log_probs = []
    values = []
    rewards = []
    dones = []

    done = False
    truncated = False
    step_count = 0
    while not done and not truncated:
        obs_tensor = torch.as_tensor(observation, dtype=torch.float32, device=device).unsqueeze(0)
        with torch.no_grad():
            action_probs, state_value = model(obs_tensor)
            dist = Categorical(action_probs)
            action = dist.sample()
            log_prob = dist.log_prob(action)

        next_observation, reward, done, truncated, info = env.step(int(action.item()))

        observations.append(observation)
        actions.append(int(action.item()))
        log_probs.append(float(log_prob.item()))
        values.append(float(state_value.squeeze(-1).item()))
        rewards.append(float(reward))
        dones.append(bool(done or truncated))

        observation = next_observation
        episode_reward += reward
        step_count += 1

        if heartbeat_interval > 0 and step_count % heartbeat_interval == 0:
            print(
                "heartbeat worker={worker} episode={episode} step={step} total_reward={reward:.3f} "
                "cycle={cycle} goals_scored={goals_scored} goals_conceded={goals_conceded}".format(
                    worker=worker_label,
                    episode=episode,
                    step=step_count,
                    reward=episode_reward,
                    cycle=info.get("cycle", -1),
                    goals_scored=info.get("goals_scored", 0),
                    goals_conceded=info.get("goals_conceded", 0),
                ),
                flush=True,
            )

    trajectory = {
        "observations": np.asarray(observations, dtype=np.float32).reshape((-1, config.OBSERVATION_SIZE)),
        "actions": np.asarray(actions, dtype=np.int64),
        "log_probs": np.asarray(log_probs, dtype=np.float32),
        "values": np.asarray(values, dtype=np.float32),
        "rewards": np.asarray(rewards, dtype=np.float32),
        "dones": np.asarray(dones, dtype=np.bool_),
    }
    trajectory["advantages"], trajectory["returns"] = compute_gae(
        rewards=trajectory["rewards"],
        values=trajectory["values"],
        dones=trajectory["dones"],
        gamma=config.GAMMA,
        gae_lambda=config.GAE_LAMBDA,
    )

    episode_info = {
        "episode": episode,
        "worker": worker_label,
        "reward": episode_reward,
        "steps": len(rewards),
        "goals_scored": int(info.get("goals_scored", 0)),
        "goals_conceded": int(info.get("goals_conceded", 0)),
        "prev_action_source": info.get("prev_action_source", "unknown"),
    }
    return trajectory, episode_info


def collect_episode_worker(
    model_state_dict: dict[str, torch.Tensor],
    rollout_device_name: str,
    episode: int,
    heartbeat_interval: int,
    worker_index: int,
    server_port: int,
    control_unum: int,
    train_team_name: str,
    opponent_team_name: str,
) -> tuple[dict[str, np.ndarray], dict]:
    torch.set_num_threads(1)
    rollout_device = resolve_device(rollout_device_name)

    model = ActorCriticPolicy().to(rollout_device)
    model.load_state_dict(model_state_dict)
    model.eval()

    env = RoboCupEnv(
        train_team_name=train_team_name,
        opponent_team_name=opponent_team_name,
        control_unum=control_unum,
        server_port=server_port,
        env_id=f"worker{worker_index}",
    )

    try:
        return collect_episode(
            env,
            model,
            rollout_device,
            episode=episode,
            heartbeat_interval=heartbeat_interval,
            worker_label=f"worker{worker_index}",
        )
    finally:
        env.close()


def maybe_save_checkpoint(
    model: ActorCriticPolicy,
    optimizer: torch.optim.Optimizer,
    checkpoint_dir: Path,
    previous_episode: int,
    current_episode: int,
) -> Path | None:
    if current_episode <= 0:
        return None
    if current_episode // config.SAVE_INTERVAL == previous_episode // config.SAVE_INTERVAL:
        return None
    return save_checkpoint(model, optimizer, checkpoint_dir, current_episode)


def run_parallel_training(
    args: argparse.Namespace,
    model: ActorCriticPolicy,
    optimizer: torch.optim.Optimizer,
    checkpoint_dir: Path,
    device: torch.device,
    start_episode: int,
) -> int:
    last_completed_episode = start_episode - 1
    mp_context = mp.get_context("spawn")

    print(
        f"training_start device={device} rollout_device={args.rollout_device} episodes={args.episodes} "
        f"start_episode={start_episode} control_unum={args.control_unum} num_workers={args.num_workers}",
        flush=True,
    )

    with ProcessPoolExecutor(max_workers=args.num_workers, mp_context=mp_context) as executor:
        next_episode = start_episode
        while next_episode <= args.episodes:
            batch_size = min(args.num_workers, args.episodes - next_episode + 1)
            model_state_dict = worker_policy_state_dict(model)
            futures = []

            for worker_index in range(batch_size):
                episode = next_episode + worker_index
                server_port = args.base_port + worker_index * args.port_stride
                futures.append(
                    executor.submit(
                        collect_episode_worker,
                        model_state_dict,
                        args.rollout_device,
                        episode,
                        args.heartbeat_interval,
                        worker_index,
                        server_port,
                        args.control_unum,
                        config.TRAIN_TEAM_NAME,
                        config.OPPONENT_TEAM_NAME,
                    )
                )

            trajectories = []
            episode_infos = []
            for future in as_completed(futures):
                trajectory, episode_info = future.result()
                trajectories.append(trajectory)
                episode_infos.append(episode_info)
                print(
                    "episode={episode} worker={worker} reward={reward:.3f} steps={steps} "
                    "goals_scored={goals_scored} goals_conceded={goals_conceded} action_source={action_source}".format(
                        episode=episode_info["episode"],
                        worker=episode_info["worker"],
                        reward=episode_info["reward"],
                        steps=episode_info["steps"],
                        goals_scored=episode_info["goals_scored"],
                        goals_conceded=episode_info["goals_conceded"],
                        action_source=episode_info["prev_action_source"],
                    ),
                    flush=True,
                )

            merged_trajectory = merge_trajectories(trajectories)
            update_policy(model, optimizer, merged_trajectory, device)

            previous_episode = last_completed_episode
            last_completed_episode = max(info["episode"] for info in episode_infos)
            checkpoint_path = maybe_save_checkpoint(
                model,
                optimizer,
                checkpoint_dir,
                previous_episode=previous_episode,
                current_episode=last_completed_episode,
            )

            batch_reward = sum(info["reward"] for info in episode_infos)
            batch_steps = sum(info["steps"] for info in episode_infos)
            checkpoint_note = f" checkpoint={checkpoint_path}" if checkpoint_path is not None else ""
            print(
                "batch_complete episodes={start}-{end} samples={samples} total_steps={steps} total_reward={reward:.3f}{checkpoint}".format(
                    start=next_episode,
                    end=last_completed_episode,
                    samples=merged_trajectory["observations"].shape[0],
                    steps=batch_steps,
                    reward=batch_reward,
                    checkpoint=checkpoint_note,
                ),
                flush=True,
            )

            next_episode += batch_size

    if last_completed_episode > 0:
        save_checkpoint(model, optimizer, checkpoint_dir, last_completed_episode)
    return last_completed_episode


def run_single_worker_training(
    args: argparse.Namespace,
    model: ActorCriticPolicy,
    optimizer: torch.optim.Optimizer,
    checkpoint_dir: Path,
    device: torch.device,
    start_episode: int,
) -> int:
    env = RoboCupEnv(control_unum=args.control_unum, server_port=args.base_port, env_id="main")
    last_completed_episode = start_episode - 1

    print(
        f"training_start device={device} rollout_device={device} episodes={args.episodes} "
        f"start_episode={start_episode} control_unum={args.control_unum} num_workers=1",
        flush=True,
    )

    try:
        for episode in range(start_episode, args.episodes + 1):
            print(f"episode_start episode={episode}", flush=True)
            trajectory, episode_info = collect_episode(
                env,
                model,
                device,
                episode=episode,
                heartbeat_interval=args.heartbeat_interval,
                worker_label="main",
            )
            update_policy(model, optimizer, trajectory, device)

            previous_episode = last_completed_episode
            last_completed_episode = episode
            checkpoint_path = maybe_save_checkpoint(
                model,
                optimizer,
                checkpoint_dir,
                previous_episode=previous_episode,
                current_episode=last_completed_episode,
            )

            checkpoint_note = f" checkpoint={checkpoint_path}" if checkpoint_path is not None else ""
            print(
                "episode={episode} worker={worker} reward={reward:.3f} steps={steps} goals_scored={goals_scored} "
                "goals_conceded={goals_conceded} action_source={action_source}{checkpoint}".format(
                    episode=episode_info["episode"],
                    worker=episode_info["worker"],
                    reward=episode_info["reward"],
                    steps=episode_info["steps"],
                    goals_scored=episode_info["goals_scored"],
                    goals_conceded=episode_info["goals_conceded"],
                    action_source=episode_info["prev_action_source"],
                    checkpoint=checkpoint_note,
                ),
                flush=True,
            )
    finally:
        env.close()

    if last_completed_episode > 0:
        save_checkpoint(model, optimizer, checkpoint_dir, last_completed_episode)
    return last_completed_episode


def main() -> int:
    args = build_parser().parse_args()
    device = resolve_device(args.device)
    checkpoint_dir = Path(config.CHECKPOINT_DIR)
    args.num_workers = max(1, args.num_workers)
    args.port_stride = max(4, args.port_stride)

    model = ActorCriticPolicy().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.LEARNING_RATE)

    start_episode = 1
    if args.resume:
        resume_path = latest_checkpoint(checkpoint_dir) if args.resume == "latest" else Path(args.resume)
        if resume_path is None or not resume_path.exists():
            raise FileNotFoundError(f"checkpoint not found: {args.resume}")
        start_episode = load_checkpoint(model, optimizer, resume_path, device)

    last_completed_episode = start_episode - 1
    try:
        if args.num_workers == 1:
            last_completed_episode = run_single_worker_training(
                args,
                model,
                optimizer,
                checkpoint_dir,
                device,
                start_episode,
            )
        else:
            last_completed_episode = run_parallel_training(
                args,
                model,
                optimizer,
                checkpoint_dir,
                device,
                start_episode,
            )
    except KeyboardInterrupt:
        if last_completed_episode > 0:
            save_checkpoint(model, optimizer, checkpoint_dir, last_completed_episode)
        raise

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
