from core.model_manager import ModelManager


class BaseAgent:
    agent_name = "coder"
    system_prompt = "You are a focused coding assistant."

    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager

    def run(self, prompt: str, max_tokens: int = 1024) -> str:
        response = self.model_manager.create_chat_completion(
            agent=self.agent_name,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            top_p=0.7,
            max_tokens=max_tokens,
            stream=False,
        )
        return response.choices[0].message.content or ""
