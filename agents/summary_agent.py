from agents.base_agent import BaseAgent


class SummaryAgent(BaseAgent):
    agent_name = "summary"
    system_prompt = (
        "Summarize code for future context. Include purpose, important functions, "
        "classes, dependencies, and likely change points."
    )
