from pathlib import Path
from typing import Optional


class FileManager:
    def __init__(self, workdir: str):
        self.workdir = Path(workdir).resolve()

    def resolve(self, path: str) -> Path:
        full_path = Path(path)
        if not full_path.is_absolute():
            full_path = self.workdir / full_path
        return full_path.resolve()

    def read_chunk(
        self,
        path: str,
        start_line: int = 1,
        end_line: Optional[int] = 200,
    ) -> str:
        full_path = self.resolve(path)
        if not full_path.exists():
            return f"Error: file not found: {full_path}"
        if start_line < 1:
            start_line = 1
        try:
            lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
            total = len(lines)
            stop = total if end_line is None else min(end_line, total)
            if start_line > total:
                return f"Error: start_line {start_line} is beyond end of file ({total} lines)"
            selected = lines[start_line - 1:stop]
            numbered = [
                f"{line_number}: {line}"
                for line_number, line in enumerate(selected, start=start_line)
            ]
            header = f"[{full_path} lines {start_line}-{stop} of {total}]"
            return header + "\n" + "\n".join(numbered)
        except Exception as e:
            return f"Error reading file chunk: {e}"

    def write_file(self, path: str, content: str) -> str:
        full_path = self.resolve(path)
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} bytes to {full_path}"
        except Exception as e:
            return f"Error writing file: {e}"

    def edit_file(self, path: str, old_string: str, new_string: str) -> str:
        full_path = self.resolve(path)
        if not full_path.exists():
            return f"Error: file not found: {full_path}"
        try:
            content = full_path.read_text(encoding="utf-8")
            if old_string not in content:
                return f"Error: old_string not found in {full_path}"
            full_path.write_text(content.replace(old_string, new_string, 1), encoding="utf-8")
            return f"Successfully edited {full_path}"
        except Exception as e:
            return f"Error editing file: {e}"
