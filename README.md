# LLaMACode

A multi-model coding agent powered by NVIDIA Llama that runs in your terminal. Reads, writes, and edits files, runs shell commands, searches code, browses the web, and more — all through a natural-language chat interface.

## Features

- **Two model tiers** — Llama 3.2 3B (balanced, default) and Llama 3.3 70B (most powerful)
- **Autonomous tool loop** — the agent plans, searches, edits, and verifies code on its own
- **File operations** — read, write, edit files, run shell commands, glob, grep
- **Web search** — search the internet and fetch page content (no API key needed)
- **Session persistence** — save/load conversations, undo exchanges, compact context
- **Multi-agent architecture** — planner, searcher, coder, reviewer, summarizer roles
- **Animated spinner** — shows which phase/agent is working in real time

## Installation

```bash
pip install llamacode
```

## Quick Start

You need an NVIDIA API key to use Llama models. The easiest way to get one:

```bash
llamacode --generate-key
```

If `llamacode` is not on your PATH (common on Windows with user installs), use:
```bash
python -m llamacode --generate-key
```

This opens [build.nvidia.com](https://build.nvidia.com) in a browser. Select the model (3B or 70B), log in to your NVIDIA account, and the key is saved automatically.

Then just run:

```bash
llamacode
```

You'll see an interactive model picker:

```
  ═══════════════════════════════════════════════════════════════
     LLaMACode - Choose a Model
  ═══════════════════════════════════════════════════════════════

  [1] Llama 3.2 3B        Balanced, default model             Key: ✓
  [2] Llama 3.3 70B       Most powerful (needs your own key)  Key: ✗

  Select [1-2] (Enter to keep current):
```

## API Keys

Every user must provide their own NVIDIA API key. There is no bundled key.

### Option 1 — Generate via browser (easiest)

```bash
llamacode --generate-key
```

Prompts you to pick 3B or 70B, opens build.nvidia.com, detects and saves the key automatically. Requires Playwright (installed on first use).

### Option 2 — .env file

Create a `.env` file in one of these locations:

| Location                     | Path                               |
| ---------------------------- | ---------------------------------- |
| Home directory (recommended) | `%USERPROFILE%\.coding_agent\.env` |
| Current working directory    | `.env`                             |

Contents:

```env
NVIDIA_API_KEY_LLAMA_3_2_3B=nvapi-your-3b-key-here
NVIDIA_API_KEY_LLAMA_3_3_70B=nvapi-your-70b-key-here    # optional
```

### Option 3 — Environment variable

```bash
set NVIDIA_API_KEY_LLAMA_3_2_3B=nvapi-your-key      # cmd
$env:NVIDIA_API_KEY_LLAMA_3_2_3B="nvapi-your-key"   # PowerShell
export NVIDIA_API_KEY_LLAMA_3_2_3B=nvapi-your-key   # bash
```

llamacode checks these env var names (in order):

| Model   | Env vars checked                                                                                       |
| ------- | ------------------------------------------------------------------------------------------------------ |
| **3B**  | `NVIDIA_API_KEY_LLAMA_3_2_3B`, `NVIDIA_LLAMA_3_2_3B_API_KEY`, `NVIDIA_API_KEY_3B`                      |
| **70B** | `NVIDIA_API_KEY_LLAMA_3_3_70B`, `NVIDIA_LLAMA_3_3_70B_API_KEY`, `NVIDIA_API_KEY_70B`, `NVIDIA_API_KEY` |

## Usage

```bash
llamacode                            # interactive CLI with model picker
python -m llamacode                   # same as above (fallback if not on PATH)
llamacode --model llama-3.2-3b       # skip picker, use 3B
llamacode --model llama-3.3-70b      # skip picker, use 70B
llamacode --generate-key             # generate API key via browser
python -m llamacode --generate-key     # same, fallback
```

### CLI Commands

| Command           | Description                                    |
| ----------------- | ---------------------------------------------- |
| `/exit`           | Exit the CLI                                   |
| `/new`            | Start a new session                            |
| `/clear`          | Clear conversation history                     |
| `/status`         | Show session info, model, workdir, key status  |
| `/model`          | Open interactive model picker                  |
| `/model <name>`   | Switch model (`llama-3.2-3b`, `llama-3.3-70b`) |
| `/workdir`        | Show working directory                         |
| `/workdir <path>` | Change working directory                       |
| `/index`          | Build `.agent/project_index.json`              |
| `/save`           | Save conversation to timestamped file          |
| `/save <file>`    | Save conversation to a specific file           |
| `/load <file>`    | Load a saved conversation                      |
| `/undo`           | Remove the last exchange                       |
| `/compact`        | Summarize conversation to save context         |
| `/help`           | Show help                                      |

### Switching Models at Runtime

```
/model llama-3.2-3b    → Llama 3.2 3B (balanced, default)
/model llama-3.3-70b   → Llama 3.3 70B (most powerful)
```

The 70B model switches immediately only if you have an NVIDIA API key configured (see [API Keys](#api-keys)).

## Available Models

| Alias           | Model ID                      | Size | Key Required  |
| --------------- | ----------------------------- | ---- | ------------- |
| `llama-3.2-3b`  | `meta/llama-3.2-3b-instruct`  | 3B   | User-provided |
| `llama-3.3-70b` | `meta/llama-3.3-70b-instruct` | 70B  | User-provided |

- **3B** — handles coding, reviewing, and summarizing (balanced, default).
- **70B** — most powerful; best for complex reasoning tasks. Requires your own NVIDIA API key.

## Agent Capabilities

LLaMACode has a built-in tool loop that lets the agent autonomously work through tasks:

| Tool         | Description                                             |
| ------------ | ------------------------------------------------------- |
| `read_file`  | Read a file chunk by line range                         |
| `write_file` | Write content to a file (creates directories if needed) |
| `edit_file`  | Replace specific text in an existing file               |
| `bash`       | Run a shell command with timeout                        |
| `glob`       | Find files matching a pattern                           |
| `grep`       | Search file contents and indexed symbols                |
| `web_search` | Search the internet via DuckDuckGo                      |
| `web_fetch`  | Fetch and extract text from a URL                       |
| `think`      | Internal reasoning (invisible to the user)              |

## Project Structure

```
llamacode/
├── coding_agent.py        Main CLI entry point
├── key_generator.py       Browser-based API key generation
├── api_server.py          Optional FastAPI server
├── pyproject.toml         Package config
├── MANIFEST.in            Build exclusions
├── agents/                Multi-agent wrappers
│   ├── planner_agent.py
│   ├── search_agent.py
│   ├── coder_agent.py
│   ├── reviewer_agent.py
│   └── summary_agent.py
└── core/                  Core modules
    ├── model_manager.py    Model & key resolution
    ├── context_manager.py  Message trimming
    ├── file_manager.py     Read/write/edit files
    ├── project_index.py    Symbol indexing
    └── summary_cache.py    Summary caching
```

## Development

```bash
# Clone the repo
git clone https://github.com/anomalyco/third_party_connect.git
cd third_party_connect

# Editable install
pip install -e .

# Set up API keys
echo NVIDIA_API_KEY_LLAMA_3_2_3B=nvapi-your-key > .env

# Run
llamacode
```

## Publishing to PyPI

Push a version tag to trigger the automated workflow:

```bash
git tag v1.2.1
git push origin v1.2.1
```

The GitHub Actions workflow (`.github/workflows/publish.yml`) builds, checks, and publishes to PyPI using trusted publishing (OIDC).

Manual publish:

```bash
pip install build twine
python -m build
python -m twine upload dist/*
```
