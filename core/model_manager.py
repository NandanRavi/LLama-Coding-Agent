import os
from dataclasses import dataclass
from typing import Dict, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
load_dotenv(os.path.expanduser("~/.coding_agent/.env"))

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

LLAMA_3_2_3B = "meta/llama-3.2-3b-instruct"
LLAMA_3_3_70B = "meta/llama-3.3-70b-instruct"

MODEL_ALIASES = {
    "llama-3.2-3b": LLAMA_3_2_3B,
    "llama-3.2": LLAMA_3_2_3B,
    "llama-3.3-70b": LLAMA_3_3_70B,
    "llama-3.3": LLAMA_3_3_70B,
}

AGENT_MODELS = {
    "planner": LLAMA_3_2_3B,
    "search": LLAMA_3_2_3B,
    "summary": LLAMA_3_2_3B,
    "review": LLAMA_3_2_3B,
    "coder": LLAMA_3_2_3B,
    "coder_pro": LLAMA_3_3_70B,
}


@dataclass(frozen=True)
class ModelConfig:
    model: str
    api_key: str


class ModelManager:
    """Centralizes NVIDIA model and API key selection."""

    def __init__(self):
        self.key_3b = self._env(
            "NVIDIA_API_KEY_LLAMA_3_2_3B",
            "NVIDIA_LLAMA_3_2_3B_API_KEY",
            "NVIDIA_API_KEY_3B",
        )
        self.key_70b = self._env(
            "NVIDIA_API_KEY_LLAMA_3_3_70B",
            "NVIDIA_LLAMA_3_3_70B_API_KEY",
            "NVIDIA_API_KEY_70B",
            "NVIDIA_API_KEY",
        )
        self._clients: Dict[str, OpenAI] = {}

    @staticmethod
    def _env(*names: str) -> Optional[str]:
        for name in names:
            value = os.getenv(name)
            if value:
                return value
        return None

    def available_models(self) -> Dict[str, str]:
        return dict(MODEL_ALIASES)

    def model_for_agent(self, agent: str) -> str:
        if agent not in AGENT_MODELS:
            raise ValueError(f"Unknown agent '{agent}'")
        return AGENT_MODELS[agent]

    def resolve_model(self, model_or_alias: Optional[str] = None, agent: Optional[str] = None) -> str:
        if agent:
            return self.model_for_agent(agent)
        if not model_or_alias:
            return AGENT_MODELS["coder"]
        return MODEL_ALIASES.get(model_or_alias, model_or_alias)

    def key_for_model(self, model: str) -> Optional[str]:
        if model == LLAMA_3_2_3B:
            return self.key_3b
        if model == LLAMA_3_3_70B:
            return self.key_70b
        return self.key_3b or self.key_70b

    def config_for(self, model_or_alias: Optional[str] = None, agent: Optional[str] = None) -> ModelConfig:
        model = self.resolve_model(model_or_alias, agent)
        api_key = self.key_for_model(model)
        if not api_key:
            raise RuntimeError(self.missing_key_message(model))
        return ModelConfig(model=model, api_key=api_key)

    def client_for(self, model_or_alias: Optional[str] = None, agent: Optional[str] = None) -> OpenAI:
        config = self.config_for(model_or_alias, agent)
        if config.api_key not in self._clients:
            self._clients[config.api_key] = OpenAI(
                base_url=NVIDIA_BASE_URL,
                api_key=config.api_key,
            )
        return self._clients[config.api_key]

    def create_chat_completion(self, messages, model_or_alias=None, agent=None, **kwargs):
        config = self.config_for(model_or_alias, agent)
        client = self.client_for(config.model)
        return client.chat.completions.create(
            model=config.model,
            messages=messages,
            **kwargs,
        )

    def has_default_key(self) -> bool:
        return bool(self.key_3b)

    def has_any_key(self) -> bool:
        return bool(self.key_3b or self.key_70b)

    def missing_key_message(self, model: str) -> str:
        if model == LLAMA_3_2_3B:
            return (
                "Missing API key for meta/llama-3.2-3b-instruct. "
                "Set NVIDIA_API_KEY_LLAMA_3_2_3B in .env."
            )
        if model == LLAMA_3_3_70B:
            return (
                "meta/llama-3.3-70b-instruct requires the user's own NVIDIA API key. "
                "Set NVIDIA_API_KEY_LLAMA_3_3_70B or NVIDIA_API_KEY in .env, "
                "or run `llamacode --generate-key`."
            )
        return f"Missing NVIDIA API key for {model}."
