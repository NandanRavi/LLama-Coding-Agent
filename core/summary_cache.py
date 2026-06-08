import hashlib
import json
from pathlib import Path
from typing import Dict


class SummaryCache:
    def __init__(self, workdir: str):
        self.workdir = Path(workdir).resolve()
        self.agent_dir = self.workdir / ".agent"
        self.summaries_dir = self.agent_dir / "summaries"
        self.hashes_path = self.agent_dir / "file_hashes.json"

    def load_hashes(self) -> Dict[str, str]:
        if not self.hashes_path.exists():
            return {}
        try:
            return json.loads(self.hashes_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_hashes(self, hashes: Dict[str, str]) -> None:
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        self.hashes_path.write_text(json.dumps(hashes, indent=2), encoding="utf-8")

    def file_hash(self, path: str) -> str:
        full_path = (self.workdir / path).resolve()
        return hashlib.sha256(full_path.read_bytes()).hexdigest()

    def summary_path(self, path: str) -> Path:
        safe_name = path.replace("\\", "__").replace("/", "__") + ".md"
        return self.summaries_dir / safe_name

    def is_fresh(self, path: str) -> bool:
        hashes = self.load_hashes()
        summary_path = self.summary_path(path)
        if not summary_path.exists():
            return False
        try:
            return hashes.get(path) == self.file_hash(path)
        except Exception:
            return False

    def write_summary(self, path: str, content: str) -> None:
        hashes = self.load_hashes()
        hashes[path] = self.file_hash(path)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)
        self.summary_path(path).write_text(content, encoding="utf-8")
        self.save_hashes(hashes)

    def read_summary(self, path: str) -> str:
        return self.summary_path(path).read_text(encoding="utf-8")
