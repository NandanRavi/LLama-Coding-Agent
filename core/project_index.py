import ast
import json
from pathlib import Path
from typing import Dict, List


IGNORED_DIRS = {".git", ".venv", "__pycache__", "dist", "build", ".agent"}


class ProjectIndex:
    def __init__(self, workdir: str):
        self.workdir = Path(workdir).resolve()
        self.agent_dir = self.workdir / ".agent"
        self.index_path = self.agent_dir / "project_index.json"

    def build(self) -> Dict[str, Dict[str, List[str]]]:
        index: Dict[str, Dict[str, List[str]]] = {}
        for path in self.workdir.rglob("*.py"):
            if any(part in IGNORED_DIRS for part in path.relative_to(self.workdir).parts):
                continue
            rel_path = str(path.relative_to(self.workdir))
            index[rel_path] = self._index_python_file(path)
        return index

    def save(self) -> Dict[str, Dict[str, List[str]]]:
        index = self.build()
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
        return index

    def load(self) -> Dict[str, Dict[str, List[str]]]:
        if not self.index_path.exists():
            return self.save()
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            return self.save()

    def search(self, query: str) -> List[str]:
        query_lower = query.lower()
        matches = []
        for path, data in self.load().items():
            haystack = " ".join(
                [path]
                + data.get("functions", [])
                + data.get("classes", [])
                + data.get("imports", [])
            ).lower()
            if query_lower in haystack:
                matches.append(path)
        return sorted(set(matches))

    @staticmethod
    def _index_python_file(path: Path) -> Dict[str, List[str]]:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            return {"functions": [], "classes": [], "imports": [], "syntax_error": ["true"]}
        except Exception:
            return {"functions": [], "classes": [], "imports": []}

        functions = []
        classes = []
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        return {
            "functions": sorted(set(functions)),
            "classes": sorted(set(classes)),
            "imports": sorted(set(imports)),
        }
