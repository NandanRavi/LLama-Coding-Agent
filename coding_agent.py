import itertools
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from core.context_manager import ContextManager
from core.file_manager import FileManager
from core.model_manager import MODEL_ALIASES, ModelManager
from core.project_index import ProjectIndex

load_dotenv()
load_dotenv(os.path.expanduser("~/.coding_agent/.env"))

MODEL_MANAGER = ModelManager()

AVAILABLE_MODELS = MODEL_ALIASES
MODEL = AVAILABLE_MODELS["llama-3.2"]

SPINNER_CHARS = ['|', '/', '-', '\\']


class Spinner:
    def __init__(self):
        self.running = False
        self.thread = None
        self.message = ""

    def _animate(self):
        for char in itertools.cycle(SPINNER_CHARS):
            if not self.running:
                break
            sys.stdout.write(f'\r  {self.message} {char} ')
            sys.stdout.flush()
            time.sleep(0.12)

    def start(self, message="Processing"):
        self.message = message
        self.running = True
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        sys.stdout.write('\r' + ' ' * 60 + '\r')
        sys.stdout.flush()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

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

1. **read_file** - Read a file chunk
   args: { "path": "path/to/file", "start_line": 1, "end_line": 200 }

2. **write_file** - Write content to a file (will overwrite!)
   args: { "path": "path/to/file", "content": "file content here" }

3. **edit_file** - Replace text in a file
   args: { "path": "path/to/file", "old_string": "text to replace", "new_string": "replacement text" }

4. **bash** - Run a shell command
   args: { "command": "command to run", "workdir": "optional working directory" }

5. **glob** - Find files by pattern
   args: { "pattern": "**/*.py", "path": "optional base path" }

6. **grep** - Search indexed symbols first, then file contents
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
        self.context_manager = ContextManager(self.workdir)

    # --- Tool implementations ---

    def _refresh_context_helpers(self):
        self.context_manager = ContextManager(self.workdir)

    def tool_read_file(
        self,
        path: str,
        start_line: int = 1,
        end_line: Optional[int] = 200,
    ) -> str:
        return FileManager(self.workdir).read_chunk(path, start_line, end_line)

    def tool_write_file(self, path: str, content: str) -> str:
        return FileManager(self.workdir).write_file(path, content)

    def tool_edit_file(self, path: str, old_string: str, new_string: str) -> str:
        return FileManager(self.workdir).edit_file(path, old_string, new_string)

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
        results = []
        search_path = Path(self.workdir)
        glob_pattern = f"**/{include}" if include else "**/*"
        try:
            if include in (None, "*.py"):
                for match in ProjectIndex(self.workdir).search(pattern):
                    results.append(f"{match}: indexed symbol/path match")

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
            return "\n".join(dict.fromkeys(results)) if results else "(no matches)"
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

    def _model_label(self):
        alias = next((k for k, v in AVAILABLE_MODELS.items() if v == MODEL), "unknown")
        return alias

    def call_llm(self, messages, stream=False, phase=""):
        label = self._model_label()
        msg = f"{phase} ({label})" if phase else f"Agent ({label}) is working"
        with Spinner() as spinner:
            spinner.start(f"{msg}")
            response = MODEL_MANAGER.create_chat_completion(
                model_or_alias=MODEL,
                messages=messages,
                temperature=0.2,
                top_p=0.7,
                max_tokens=2048,
                stream=stream
            )
        return response

    def run_tool_loop(self, user_input: str):
        self.messages.append({"role": "user", "content": user_input})
        self.messages = self.context_manager.trim_messages(self.messages)

        phases = [
            "  Planning approach",
            "  Searching codebase",
            "  Implementing changes",
            "  Reviewing output",
        ]

        max_iterations = 25
        for iteration in range(max_iterations):
            phase = phases[iteration % len(phases)] if iteration > 0 else "  Processing request"
            response = self.call_llm(self.messages, phase=phase)

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
                self.messages = self.context_manager.trim_messages(self.messages)
                break

            if iteration == max_iterations - 1:
                self.messages.append({"role": "assistant", "content": reply})
                return reply

        return reply

    def start_cli(self):
        global MODEL
        print()
        print("  \033[1;36m" + "=" * 58 + "\033[0m")
        print("  \033[1;36m    LLaMACode - Coding Agent CLI\033[0m")
        current_alias = self._model_label()
        label_map = {"llama-3.2-1b": "Llama 3.2 1B", "llama-3.2-3b": "Llama 3.2 3B", "llama-3.3-70b": "Llama 3.3 70B", "llama-3.2": "Llama 3.2 3B", "llama-3.3": "Llama 3.3 70B"}
        friendly = label_map.get(current_alias, current_alias)
        print(f"  \033[1;36m  Model: {friendly}  |  Workdir: {os.path.basename(self.workdir)}\033[0m")
        print("  \033[1;36m" + "=" * 58 + "\033[0m")
        print()
        print("  \033[2mCommands: /exit  /new  /clear  /status  /model  /workdir  /index  /save  /load  /undo  /compact  /help\033[0m")
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
                label_map = {"llama-3.2-1b": "Llama 3.2 1B", "llama-3.2-3b": "Llama 3.2 3B", "llama-3.3-70b": "Llama 3.3 70B", "llama-3.2": "Llama 3.2 3B", "llama-3.3": "Llama 3.3 70B"}
                friendly = label_map.get(current_alias, current_alias)
                print(f"  Messages: {len(self.messages)}")
                print(f"  Workdir: {self.workdir}")
                print(f"  Model: {friendly} ({MODEL})")
                config_map = {"1B": MODEL_MANAGER.key_1b, "3B": MODEL_MANAGER.key_3b, "70B (your own)": MODEL_MANAGER.key_70b}
                for k, v in config_map.items():
                    status = "\033[1;32m✓\033[0m" if v else "\033[1;31m✗\033[0m"
                    print(f"  {k:15s} key: {status}")
                continue

            if cmd.startswith("/model"):
                parts = cmd.split(None, 1)
                if len(parts) > 1:
                    alias = parts[1].lower()
                    if alias in AVAILABLE_MODELS:
                        if alias in ("llama-3.3-70b", "llama-3.3") and not MODEL_MANAGER.key_70b:
                            print("  \033[1;33m70B model requires your own NVIDIA API key.\033[0m")
                            print("  Run \033[1mllamacode --generate-key\033[0m or set NVIDIA_API_KEY in .env")
                            continue
                        MODEL = AVAILABLE_MODELS[alias]
                        label_map = {"llama-3.2-1b": "Llama 3.2 1B", "llama-3.2-3b": "Llama 3.2 3B", "llama-3.3-70b": "Llama 3.3 70B"}
                        friendly = label_map.get(alias, alias)
                        print(f"  \033[1;32mSwitched to: {friendly}\033[0m")
                    else:
                        print(f"  Available models: llama-3.2-1b, llama-3.2-3b, llama-3.3-70b")
                else:
                    _select_model_interactive()
                continue

            if cmd.startswith("/workdir"):
                parts = cmd.split(None, 1)
                if len(parts) > 1:
                    new_dir = parts[1]
                    if os.path.isdir(new_dir):
                        self.workdir = os.path.abspath(new_dir)
                        self._refresh_context_helpers()
                        print(f"  Workdir changed to: {self.workdir}")
                    else:
                        print(f"  Error: directory not found: {new_dir}")
                else:
                    print(f"  Current workdir: {self.workdir}")
                continue

            if cmd == "/index":
                try:
                    index = ProjectIndex(self.workdir).save()
                    print(f"  Indexed {len(index)} Python files into .agent/project_index.json")
                except Exception as e:
                    print(f"  Error indexing project: {e}")
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
                    resp = MODEL_MANAGER.create_chat_completion(
                        model_or_alias=MODEL, messages=compact_msgs,
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
                print("    \033[1m/model <name>\033[0m  Switch model (llama-3.2-1b, llama-3.2-3b, llama-3.3-70b)")
                print("    \033[1m/workdir\033[0m      Show or change working directory")
                print("    \033[1m/workdir <path>\033[0m  Change working directory to <path>")
                print("    \033[1m/index\033[0m        Build .agent/project_index.json")
                print("    \033[1m/save\033[0m         Save conversation to timestamped file")
                print("    \033[1m/save <file>\033[0m  Save conversation to <file>")
                print("    \033[1m/load <file>\033[0m  Load a saved conversation")
                print("    \033[1m/undo\033[0m         Remove the last exchange")
                print("    \033[1m/compact\033[0m      Summarize conversation to save context")
                print("    \033[1m/help\033[0m         Show this help")
                print()
                print("  \033[1mWorkflow:\033[0m")
                print("    Ask coding questions or give tasks.")
                print("    The agent will use chunked reads, indexed search, and editing tools")
                print("    to complete your request automatically.")
                continue

            print()
            result = self.run_tool_loop(user_input)
            print(f"\033[1;34mAgent\033[0m > {result}")
            print()


def _select_model_interactive(show_header=True):
    global MODEL, MODEL_MANAGER
    current_alias = next((k for k, v in AVAILABLE_MODELS.items() if v == MODEL), "llama-3.2-3b")
    models = [
        ("1", "llama-3.2-1b", "Llama 3.2 1B", "Fastest, lightweight tasks", MODEL_MANAGER.key_1b),
        ("2", "llama-3.2-3b", "Llama 3.2 3B", "Balanced, default model", MODEL_MANAGER.key_3b),
        ("3", "llama-3.3-70b", "Llama 3.3 70B", "Most powerful (needs your own key)", MODEL_MANAGER.key_70b),
    ]
    if show_header:
        print()
        print("  \033[1;36m" + "=" * 58 + "\033[0m")
        print("  \033[1;36m     LLaMACode - Choose a Model\033[0m")
        print("  \033[1;36m" + "=" * 58 + "\033[0m")
        print()
    for key, alias, name, desc, has_key in models:
        icon = "\033[1;32m✓\033[0m" if has_key else "\033[1;31m✗\033[0m"
        marker = " \033[1;33m← current\033[0m" if alias == current_alias else ""
        print(f"  [{key}] {name:20s} {desc:35s} Key: {icon}{marker}")
    print()
    choice = input(f"  Select [1-3] (Enter to keep current): ").strip()
    if not choice:
        print(f"  Keeping \033[1;33m{current_alias}\033[0m.")
        return
    mapping = {"1": "llama-3.2-1b", "2": "llama-3.2-3b", "3": "llama-3.3-70b"}
    alias = mapping.get(choice)
    if not alias:
        print(f"  Keeping \033[1;33m{current_alias}\033[0m.")
        return
    if alias in ("llama-3.3-70b", "llama-3.3") and not MODEL_MANAGER.key_70b:
        print()
        print("  \033[1;33m70B needs your own NVIDIA API key.\033[0m")
        print("  Generate one now via browser? [Y/n]: ", end="")
        try:
            resp = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            resp = "n"
        if not resp or resp[0] != "n":
            from key_generator import generate_api_key
            key = generate_api_key()
            if key:
                os.environ["NVIDIA_API_KEY"] = key
                MODEL_MANAGER = ModelManager()
                MODEL = AVAILABLE_MODELS[alias]
                print(f"  \033[1;32mUsing {alias}\033[0m")
                return
        print("  \033[1;31mNo 70B key. Falling back to default.\033[0m")
        alias = "llama-3.2-3b"
    MODEL = AVAILABLE_MODELS[alias]
    label_map = {"llama-3.2-1b": "Llama 3.2 1B", "llama-3.2-3b": "Llama 3.2 3B", "llama-3.3-70b": "Llama 3.3 70B"}
    print(f"  \033[1;32mUsing {label_map.get(alias, alias)}\033[0m")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Coding Agent CLI")
    parser.add_argument("--generate-key", action="store_true",
                        help="Generate NVIDIA API key via browser")
    parser.add_argument("--model", type=str, default=None,
                        help="Model to use: llama-3.2-1b, llama-3.2-3b (default), or llama-3.3-70b")
    args = parser.parse_args()

    global MODEL_MANAGER, MODEL

    if args.generate_key:
        from key_generator import generate_api_key
        key = generate_api_key()
        if key:
            os.environ["NVIDIA_API_KEY"] = key
            MODEL_MANAGER = ModelManager()
        else:
            print("Failed to generate API key.")
            sys.exit(1)

    has_1b_or_3b = MODEL_MANAGER.key_1b or MODEL_MANAGER.key_3b
    if not has_1b_or_3b and not MODEL_MANAGER.key_70b:
        print("  \033[1;33mNo API keys found for 1B or 3B models.\033[0m")
        print("  Set NVIDIA_API_KEY_LLAMA_3_2_1B and NVIDIA_API_KEY_LLAMA_3_2_3B in .env")
        print("  or run \033[1mllamacode --generate-key\033[0m for a 70B key.")
        choice = input("  Generate 70B key now? [Y/n]: ").strip().lower() or "y"
        if choice[0] != "n":
            from key_generator import generate_api_key
            key = generate_api_key()
            if key:
                os.environ["NVIDIA_API_KEY"] = key
                MODEL_MANAGER = ModelManager()
        if not MODEL_MANAGER.has_any_key():
            print("No API keys available. Exiting.")
            sys.exit(1)

    if args.model:
        alias = args.model.lower()
        if alias in AVAILABLE_MODELS:
            if alias in ("llama-3.3-70b", "llama-3.3") and not MODEL_MANAGER.key_70b:
                print("  \033[1;31m70B model needs your own NVIDIA API key. Falling back.\033[0m")
                alias = "llama-3.2-3b"
            MODEL = AVAILABLE_MODELS[alias]
        else:
            print(f"  Unknown model '{alias}'. Using default.")
    else:
        _select_model_interactive()

    if not MODEL_MANAGER.key_for_model(MODEL):
        print(f"  \033[1;31m{MODEL_MANAGER.missing_key_message(MODEL)}\033[0m")
        for fallback_alias, fallback_model in AVAILABLE_MODELS.items():
            if MODEL_MANAGER.key_for_model(fallback_model):
                MODEL = fallback_model
                print(f"  Falling back to \033[1;33m{fallback_alias}\033[0m.")
                break
        else:
            print("  \033[1;31mNo API keys available. Exiting.\033[0m")
            sys.exit(1)

    agent = CodingAgent()
    agent.start_cli()


if __name__ == "__main__":
    main()
