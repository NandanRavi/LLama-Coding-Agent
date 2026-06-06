# LLaMACode

A coding agent powered by NVIDIA Llama 3.3 (70B) that runs in your terminal. It can read, write, and edit files, run shell commands, search code, and more.

## Installation

```bash
pip install llamacode
```

## Setup

1. Get a free NVIDIA API key from [build.nvidia.com/meta/llama-3_3-70b-instruct](https://build.nvidia.com/meta/llama-3_3-70b-instruct) (click "Get API Key")

2. Set your NVIDIA API key via one of these methods:

**Option 1 — Environment variable:**

```bash
set NVIDIA_API_KEY=nvapi-xxxxx        # cmd
$env:NVIDIA_API_KEY="nvapi-xxxxx"     # PowerShell
export NVIDIA_API_KEY=nvapi-xxxxx     # bash
```

**Option 2 — .env file in home directory:**

```bash
mkdir ~\.coding_agent
echo NVIDIA_API_KEY=nvapi-xxxxx > ~\.coding_agent\.env
```

**Option 3 — .env file in current directory:**

```bash
echo NVIDIA_API_KEY=nvapi-xxxxx > .env
```

## Usage

```bash
llamacode
```

Then type your coding questions or tasks directly in the terminal.

### Commands

| Command           | Description                            |
| ----------------- | -------------------------------------- |
| `/exit`           | Exit the CLI                           |
| `/new`            | Start a new session                    |
| `/clear`          | Clear conversation history             |
| `/status`         | Show session info                      |
| `/model`          | Show current model                     |
| `/model <name>`   | Switch model (`llama-3.3`)             |
| `/workdir`        | Show working directory                 |
| `/workdir <path>` | Change working directory               |
| `/save`           | Save conversation to file              |
| `/load <file>`    | Load a saved conversation              |
| `/undo`           | Remove the last exchange               |
| `/compact`        | Summarize conversation to save context |
| `/help`           | Show help                              |

## Models

- **llama-3.3** (default) — `meta/llama-3.3-70b-instruct`
