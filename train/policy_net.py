from __future__ import annotations

from pathlib import Path

import torch
from torch import nn

from train import config


class ActorCriticPolicy(nn.Module):
    def __init__(self):
        super().__init__()
        self.shared = nn.Sequential(
            nn.Linear(config.OBSERVATION_SIZE, config.HIDDEN_SIZE_1),
            nn.ReLU(),
            nn.Linear(config.HIDDEN_SIZE_1, config.HIDDEN_SIZE_2),
            nn.ReLU(),
        )
        self.actor = nn.Linear(config.HIDDEN_SIZE_2, config.ACTION_SIZE)
        self.critic = nn.Linear(config.HIDDEN_SIZE_2, 1)

    def forward(self, observation: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if observation.dim() == 1:
            observation = observation.unsqueeze(0)
        features = self.shared(observation)
        action_probs = torch.softmax(self.actor(features), dim=-1)
        state_value = self.critic(features)
        return action_probs, state_value

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"model_state_dict": self.state_dict()}, path)

    @classmethod
    def load(cls, path: str | Path, map_location: str | torch.device | None = None) -> "ActorCriticPolicy":
        payload = torch.load(path, map_location=map_location)
        model = cls()
        state_dict = payload.get("model_state_dict", payload)
        model.load_state_dict(state_dict)
        return model
