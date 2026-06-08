from typing import Iterable, List

from core.file_manager import FileManager
from core.summary_cache import SummaryCache


class ContextManager:
    def __init__(self, workdir: str, max_messages: int = 10):
        self.workdir = workdir
        self.max_messages = max_messages
        self.file_manager = FileManager(workdir)
        self.summary_cache = SummaryCache(workdir)

    def trim_messages(self, messages: List[dict]) -> List[dict]:
        if len(messages) <= self.max_messages + 1:
            return messages
        system = messages[0:1]
        tail = messages[-self.max_messages:]
        return system + tail

    def build_file_context(self, paths: Iterable[str], lines_per_file: int = 160) -> str:
        sections = []
        for path in paths:
            if self.summary_cache.is_fresh(path):
                sections.append(f"## Summary: {path}\n{self.summary_cache.read_summary(path)}")
            else:
                sections.append(
                    f"## Chunk: {path}\n"
                    + self.file_manager.read_chunk(path, 1, lines_per_file)
                )
        return "\n\n".join(sections)
