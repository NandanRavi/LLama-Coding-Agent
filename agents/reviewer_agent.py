from agents.base_agent import BaseAgent


class ReviewerAgent(BaseAgent):
    agent_name = "review"
    system_prompt = (
        "Review proposed code changes for bugs, syntax issues, missing imports, "
        "unsafe behavior, and missing tests. Return pass/fail and concise findings."
    )
