from agents.base_agent import BaseAgent


class PlannerAgent(BaseAgent):
    agent_name = "planner"
    system_prompt = (
        "Create concise implementation plans for coding tasks. "
        "Return the likely files, steps, and risks. Prefer structured text."
    )
