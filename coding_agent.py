import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
load_dotenv(os.path.expanduser("~/.coding_agent/.env"))

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
if not NVIDIA_API_KEY:
    print("Error: NVIDIA_API_KEY not found.")
    print("Create a .env file with: NVIDIA_API_KEY=nvapi-xxxxx")
    print("Or set it as an environment variable.")
    sys.exit(1)

CLIENT = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)

AVAILABLE_MODELS = {
    "llama-3.3": "meta/llama-3.3-70b-instruct",
}
MODEL = AVAILABLE_MODELS["llama-3.3"]

SYSTEM_PROMPT = """You are a powerful coding agent. You help users with software engineering tasks.

You have access to tools that let you read, write, and edit files, run shell commands, and search code.

## Tool Use Format
To use a tool, output EXACTLY:

<tool>
<name>tool_name</name>
<args>
{
  "arg1": "value1",
  "arg2": "value2"
}
</args>
</tool>

After the tool executes, you'll get the result. Then continue your reasoning and either call more tools or give the final answer.

## Available Tools

1. **read_file** - Read a file's contents
   args: { "path": "path/to/file" }

2. **write_file** - Write content to a file (will overwrite!)
   args: { "path": "path/to/file", "content": "file content here" }

3. **edit_file** - Replace text in a file
   args: { "path": "path/to/file", "old_string": "text to replace", "new_string": "replacement text" }

4. **bash** - Run a shell command
   args: { "command": "command to run", "workdir": "optional working directory" }

5. **glob** - Find files by pattern
   args: { "pattern": "**/*.py", "path": "optional base path" }

6. **grep** - Search file contents
   args: { "pattern": "search regex", "include": "optional file pattern like *.py" }

7. **think** - Use this to reason about the task before responding
   args: { "thought": "your reasoning here" }

## Guidelines
- Always think step by step before acting
- Prefer editing existing files over rewriting them
- Run linting or tests after making changes
- Be concise and direct in your responses
- Use the think tool to plan your approach"""

TOOL_PATTERN = re.compile(
    r'<tool>\s*<name>(.*?)</name>\s*<args>\s*(.*?)\s*</args>\s*</tool>',
    re.DOTALL
)

class CodingAgent:
    def __init__(self):
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        self.workdir = os.getcwd()

    # --- Tool implementations ---

    def tool_read_file(self, path: str) -> str:
        full_path = Path(path)
        if not full_path.is_absolute():
            full_path = Path(self.workdir) / full_path
        if not full_path.exists():
            return f"Error: file not found: {full_path}"
        try:
            content = full_path.read_text(encoding="utf-8")
            return content
        except Exception as e:
            return f"Error reading file: {e}"

    def tool_write_file(self, path: str, content: str) -> str:
        full_path = Path(path)
        if not full_path.is_absolute():
            full_path = Path(self.workdir) / full_path
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} bytes to {full_path}"
        except Exception as e:
            return f"Error writing file: {e}"

    def tool_edit_file(self, path: str, old_string: str, new_string: str) -> str:
        full_path = Path(path)
        if not full_path.is_absolute():
            full_path = Path(self.workdir) / full_path
        if not full_path.exists():
            return f"Error: file not found: {full_path}"
        try:
            content = full_path.read_text(encoding="utf-8")
            if old_string not in content:
                return f"Error: old_string not found in {full_path}"
            new_content = content.replace(old_string, new_string, 1)
            full_path.write_text(new_content, encoding="utf-8")
            return f"Successfully edited {full_path}"
        except Exception as e:
            return f"Error editing file: {e}"

    def tool_bash(self, command: str, workdir: Optional[str] = None) -> str:
        cwd = workdir or self.workdir
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=60
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += result.stderr
            if result.returncode != 0:
                output += f"\n(exit code: {result.returncode})"
            return output.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: command timed out after 60 seconds"
        except Exception as e:
            return f"Error running command: {e}"

    def tool_glob(self, pattern: str, path: Optional[str] = None) -> str:
        base = Path(path) if path else Path(self.workdir)
        if not base.is_absolute():
            base = Path(self.workdir) / base
        try:
            files = list(base.glob(pattern))
            if not files:
                return f"No files matching '{pattern}' found in {base}"
            return "\n".join(str(f.relative_to(base)) if not path else str(f) for f in sorted(files))
        except Exception as e:
            return f"Error globbing: {e}"

    def tool_grep(self, pattern: str, include: Optional[str] = None) -> str:
        import glob as glob_mod
        results = []
        search_path = Path(self.workdir)
        glob_pattern = f"**/{include}" if include else "**/*"
        try:
            for file in search_path.glob(glob_pattern):
                if not file.is_file():
                    continue
                try:
                    with file.open("r", encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if re.search(pattern, line):
                                rel = file.relative_to(search_path)
                                results.append(f"{rel}:{i}:{line.rstrip()}")
                except Exception:
                    pass
            return "\n".join(results) if results else "(no matches)"
        except Exception as e:
            return f"Error grepping: {e}"

    def tool_think(self, thought: str) -> str:
        return f"Understood. Continuing with this reasoning in mind."

    TOOLS = {
        "read_file": tool_read_file,
        "write_file": tool_write_file,
        "edit_file": tool_edit_file,
        "bash": tool_bash,
        "glob": tool_glob,
        "grep": tool_grep,
        "think": tool_think,
    }

    # --- Agent Loop ---

    def parse_tool_calls(self, text: str):
        calls = []
        for match in TOOL_PATTERN.finditer(text):
            name = match.group(1).strip()
            try:
                args = json.loads(match.group(2).strip())
            except json.JSONDecodeError:
                args = {}
            calls.append((name, args))
        return calls

    def execute_tool(self, name: str, args: dict) -> str:
        handler = self.TOOLS.get(name)
        if not handler:
            return f"Error: unknown tool '{name}'"
        try:
            result = handler(self, **args)
            return result
        except TypeError as e:
            return f"Error: invalid arguments for {name}: {e}"
        except Exception as e:
            return f"Error executing {name}: {e}"

    def call_llm(self, messages, stream=False):
        return CLIENT.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.2,
            top_p=0.7,
            max_tokens=2048,
            stream=stream
        )

    def run_tool_loop(self, user_input: str):
        self.messages.append({"role": "user", "content": user_input})

        max_iterations = 25
        for iteration in range(max_iterations):
            response = self.call_llm(self.messages)

            reply = response.choices[0].message.content
            if not reply:
                reply = ""

            tool_calls = self.parse_tool_calls(reply)

            if not tool_calls:
                self.messages.append({"role": "assistant", "content": reply})
                return reply

            for tool_name, tool_args in tool_calls:
                if tool_name == "think":
                    result = self.execute_tool(tool_name, tool_args)
                    self.messages.append({"role": "assistant", "content": reply})
                    continue

                result = self.execute_tool(tool_name, tool_args)
                truncated = result[:1000] + "..." if len(result) > 1000 else result
                self.messages.append({
                    "role": "assistant",
                    "content": reply
                })
                self.messages.append({
                    "role": "user",
                    "content": f"[Tool {tool_name} result]\n{truncated}"
                })
                break

            if iteration == max_iterations - 1:
                self.messages.append({"role": "assistant", "content": reply})
                return reply

        return reply

    def start_cli(self):
        global MODEL
        print()
        print("  \033[1;36m" + "=" * 58 + "\033[0m")
        print("  \033[1;36m  Coding Agent CLI\033[0m")
        current_alias = next((k for k, v in AVAILABLE_MODELS.items() if v == MODEL), "unknown")
        print(f"  \033[1;36m  Model: {current_alias} ({MODEL})  |  Workdir: {os.path.basename(self.workdir)}\033[0m")
        print("  \033[1;36m" + "=" * 58 + "\033[0m")
        print()
        print("  \033[2mCommands: /exit  /new  /clear  /status  /model  /workdir  /save  /load  /undo  /compact  /help\033[0m")
        print()

        while True:
            try:
                user_input = input("\033[1;32mYou\033[0m > ")
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not user_input.strip():
                continue

            cmd = user_input.strip().lower()

            if cmd == "/exit":
                print("Goodbye!")
                break

            if cmd == "/new":
                self.messages = [self.messages[0]]
                print("New session started.")
                continue

            if cmd == "/clear":
                self.messages = [self.messages[0]]
                print("Conversation cleared.")
                continue

            if cmd == "/status":
                current_alias = next((k for k, v in AVAILABLE_MODELS.items() if v == MODEL), "unknown")
                print(f"  Messages: {len(self.messages)}")
                print(f"  Workdir: {self.workdir}")
                print(f"  Model: {current_alias} ({MODEL})")
                continue

            if cmd.startswith("/model"):
                parts = cmd.split(None, 1)
                if len(parts) > 1:
                    alias = parts[1].lower()
                    if alias in AVAILABLE_MODELS:
                        MODEL = AVAILABLE_MODELS[alias]
                        print(f"  Model switched to: {alias} ({MODEL})")
                    else:
                        print(f"  Available models: {', '.join(AVAILABLE_MODELS.keys())}")
                else:
                    current_alias = next((k for k, v in AVAILABLE_MODELS.items() if v == MODEL), "unknown")
                    print(f"  Current model: {current_alias} ({MODEL})")
                    print(f"  Available: {', '.join(AVAILABLE_MODELS.keys())}")
                    print("  Usage: /model <name>  to switch")
                continue

            if cmd.startswith("/workdir"):
                parts = cmd.split(None, 1)
                if len(parts) > 1:
                    new_dir = parts[1]
                    if os.path.isdir(new_dir):
                        self.workdir = os.path.abspath(new_dir)
                        print(f"  Workdir changed to: {self.workdir}")
                    else:
                        print(f"  Error: directory not found: {new_dir}")
                else:
                    print(f"  Current workdir: {self.workdir}")
                continue

            if cmd.startswith("/save"):
                parts = cmd.split(None, 1)
                filename = parts[1] if len(parts) > 1 else f"conversation_{int(time.time())}.json"
                try:
                    data = {
                        "model": MODEL,
                        "workdir": self.workdir,
                        "messages": self.messages
                    }
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    print(f"  Conversation saved to: {filename}")
                except Exception as e:
                    print(f"  Error saving: {e}")
                continue

            if cmd.startswith("/load"):
                parts = cmd.split(None, 1)
                if len(parts) < 2:
                    print("  Usage: /load <filename>")
                    continue
                filename = parts[1]
                if not os.path.exists(filename):
                    print(f"  Error: file not found: {filename}")
                    continue
                try:
                    with open(filename, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.messages = data.get("messages", [self.messages[0]])
                    if "workdir" in data:
                        self.workdir = data["workdir"]
                    print(f"  Conversation loaded from: {filename} ({len(self.messages)} messages)")
                except Exception as e:
                    print(f"  Error loading: {e}")
                continue

            if cmd == "/undo":
                if len(self.messages) <= 1:
                    print("  No messages to undo.")
                    continue
                self.messages = self.messages[:-2]
                print("  Last exchange undone.")
                continue

            if cmd == "/compact":
                if len(self.messages) <= 1:
                    print("  No conversation to compact.")
                    continue
                system = self.messages[0]
                summary_prompt = "Summarize the key points of the above conversation concisely for context continuation."
                compact_msgs = self.messages[1:] + [{"role": "user", "content": summary_prompt}]
                try:
                    resp = CLIENT.chat.completions.create(
                        model=MODEL, messages=compact_msgs,
                        temperature=0.2, max_tokens=512
                    )
                    summary = resp.choices[0].message.content
                    self.messages = [
                        system,
                        {"role": "system", "content": f"Previous conversation summary:\n{summary}"}
                    ]
                    print(f"  Compacted to summary ({len(summary)} chars).")
                except Exception as e:
                    print(f"  Error compacting: {e}")
                continue

            if cmd == "/help":
                print("  \033[1mCommands:\033[0m")
                print("    \033[1m/exit\033[0m         Exit the CLI")
                print("    \033[1m/new\033[0m          Start a new session")
                print("    \033[1m/clear\033[0m        Clear conversation history")
                print("    \033[1m/status\033[0m       Show session info (messages, workdir, model)")
                print("    \033[1m/model\033[0m         Show current model")
                print("    \033[1m/model <name>\033[0m  Switch model (llama-3.3, llama-3.2)")
                print("    \033[1m/workdir\033[0m      Show or change working directory")
                print("    \033[1m/workdir <path>\033[0m  Change working directory to <path>")
                print("    \033[1m/save\033[0m         Save conversation to timestamped file")
                print("    \033[1m/save <file>\033[0m  Save conversation to <file>")
                print("    \033[1m/load <file>\033[0m  Load a saved conversation")
                print("    \033[1m/undo\033[0m         Remove the last exchange")
                print("    \033[1m/compact\033[0m      Summarize conversation to save context")
                print("    \033[1m/help\033[0m         Show this help")
                print()
                print("  \033[1mWorkflow:\033[0m")
                print("    Ask coding questions or give tasks.")
                print("    The agent will use tools (read, write, edit, bash, glob, grep)")
                print("    to complete your request automatically.")
                continue

            print()
            result = self.run_tool_loop(user_input)
            print(f"\033[1;34mAgent\033[0m > {result}")
            print()


def main():
    agent = CodingAgent()
    agent.start_cli()


if __name__ == "__main__":
    main()
