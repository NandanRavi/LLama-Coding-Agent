from agents.base_agent import BaseAgent
from core.project_index import ProjectIndex


class SearchAgent(BaseAgent):
    agent_name = "search"
    system_prompt = (
        "Identify relevant files and symbols for a coding task. "
        "Prefer exact file paths and symbol names."
    )

    def local_search(self, workdir: str, query: str):
        return ProjectIndex(workdir).search(query)
