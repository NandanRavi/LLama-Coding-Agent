# LLaMACode

A coding agent powered by NVIDIA Llama models that runs in your terminal. It can read, write, and edit files, run shell commands, search code, and more.

Choose from two model tiers — **3B** (balanced, default) or **70B** (most powerful, needs your own API key).

## Installation

```bash
pip install llamacode
```

## API Keys

LLaMACode uses NVIDIA's hosted Llama models. Different models need different API keys:

### 3B Model (pre-configured)

The **Llama 3.2 3B** model comes with a pre-configured API key bundled in the project.  
It works out of the box — no additional setup required.

### 70B Model (bring your own key)

The **Llama 3.3 70B** model requires your **own NVIDIA API key**. Get one via:

**Option 1 — Automatic browser generation (recommended):**

```bash
llamacode --generate-key
```

Launches a browser to [build.nvidia.com](https://build.nvidia.com/meta/llama-3_3-70b-instruct) — you log in and the key is detected and saved automatically. Playwright will be installed on first use if missing.

**Option 2 — Environment variable:**

```bash
set NVIDIA_API_KEY=nvapi-xxxxx        # cmd
$env:NVIDIA_API_KEY="nvapi-xxxxx"     # PowerShell
export NVIDIA_API_KEY=nvapi-xxxxx     # bash
```

**Option 3 — .env file in home directory:**

```bash
mkdir ~\.coding_agent
echo NVIDIA_API_KEY=nvapi-xxxxx > ~\.coding_agent\.env
```

**Option 4 — .env file in current directory:**

```bash
echo NVIDIA_API_KEY=nvapi-xxxxx > .env
```

## Usage

```bash
llamacode                        # interactive CLI with model selection
llamacode --model llama-3.2-3b   # start with a specific model
llamacode --model llama-3.3-70b  # use 70B model (requires your own API key)
llamacode --generate-key         # generate API key via browser
```

On first run, you'll see an interactive model picker:

```
  ══════════════════════════════════════════════════════════════
     LLaMACode - Choose a Model
  ══════════════════════════════════════════════════════════════

  [1] Llama 3.2 3B        Balanced, default model                  Key: ✓
  [2] Llama 3.3 70B       Most powerful (needs your own key)       Key: ✗

  Select [1-2] (Enter to keep current):
```

While processing, you'll see an animated spinner showing which phase is active:

```
  / Planning approach (llama-3.2-3b)
  \ Implementing changes (llama-3.2-3b)
```

### Commands

| Command           | Description                            |
| ----------------- | -------------------------------------- |
| `/exit`           | Exit the CLI                           |
| `/new`            | Start a new session                    |
| `/clear`          | Clear conversation history             |
| `/status`         | Show session info & API key status     |
| `/model`          | Show current model                     |
| `/model <name>`   | Switch model on the fly                |
| `/workdir`        | Show working directory                 |
| `/workdir <path>` | Change working directory               |
| `/save`           | Save conversation to file              |
| `/load <file>`    | Load a saved conversation              |
| `/undo`           | Remove the last exchange               |
| `/compact`        | Summarize conversation to save context |
| `/help`           | Show help                              |

### Switching Models at Runtime

Use `/model` to switch models during a session:

```
/model llama-3.2-3b    → Llama 3.2 3B (balanced, default)
/model llama-3.3-70b   → Llama 3.3 70B (most powerful)
```

## Available Models

| Alias              | Model ID                         | Size | Key Required         |
| ------------------ | -------------------------------- | ---- | -------------------- |
| `llama-3.2-3b`     | `meta/llama-3.2-3b-instruct`    | 3B   | Pre-configured (env) |
| `llama-3.3-70b`    | `meta/llama-3.3-70b-instruct`   | 70B  | Your own key         |

- **3B model** handles coding, reviewing, and summarizing (balanced, default).
- **70B model** is the most powerful — use it for complex tasks. Requires your own NVIDIA API key.
