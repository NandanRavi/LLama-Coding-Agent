from agents.base_agent import BaseAgent


class CoderAgent(BaseAgent):
    agent_name = "coder"
    system_prompt = (
        "Generate precise code changes from the provided plan and context. "
        "Be conservative and preserve existing behavior."
    )


class ProCoderAgent(CoderAgent):
    agent_name = "coder_pro"
