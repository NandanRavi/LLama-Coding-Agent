import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

load_dotenv()
load_dotenv(os.path.expanduser("~/.coding_agent/.env"))

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
if not NVIDIA_API_KEY:
    print("Error: NVIDIA_API_KEY not found.")
    print("  Run `llamacode --generate-key` to generate one via browser.")
    print("  Or create a .env file with: NVIDIA_API_KEY=nvapi-xxxxx")
    exit(1)

AVAILABLE_MODELS = {
    "llama-3.3": "meta/llama-3.3-70b-instruct"
}
MODEL = AVAILABLE_MODELS["llama-3.3"]

app = FastAPI(title="Local Coding Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "meta/llama-3.3-70b-instruct"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.2
    top_p: Optional[float] = 0.7
    max_tokens: Optional[int] = 1024
    stream: Optional[bool] = False

@app.get("/")
def root():
    return {"message": "Local Coding Agent API is running", "endpoints": {"/v1/chat/completions": "OpenAI-compatible chat endpoint"}}

@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [
            {"id": v, "object": "model"} for v in AVAILABLE_MODELS.values()
        ]
    }

@app.post("/v1/chat/completions")
def chat_completions(req: ChatCompletionRequest):
    if not req.messages or not req.messages[-1].content.strip():
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    try:
        completion = client.chat.completions.create(
            model=req.model,
            messages=messages,
            temperature=req.temperature,
            top_p=req.top_p,
            max_tokens=req.max_tokens,
            stream=False
        )
        return {
            "id": completion.id,
            "object": "chat.completion",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": completion.choices[0].message.content
                }
            }],
            "model": req.model
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def run_cli():
    global NVIDIA_API_KEY, client

    if not NVIDIA_API_KEY:
        print("NVIDIA_API_KEY not found.")
        print("Would you like to generate one now via browser? [Y/n]: ", end="")
        try:
            resp = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            resp = "n"
        if not resp or resp[0] != "n":
            from key_generator import generate_api_key
            key = generate_api_key()
            if key:
                NVIDIA_API_KEY = key
                os.environ["NVIDIA_API_KEY"] = key
                client = OpenAI(
                    base_url="https://integrate.api.nvidia.com/v1",
                    api_key=NVIDIA_API_KEY
                )
            else:
                print("Could not obtain API key.")
                return
        else:
            print("Please set NVIDIA_API_KEY in .env or as environment variable.")
            return

    print("=" * 60)
    print("  Local Coding Agent CLI")
    print("  Powered by NVIDIA Llama 3.3 70B")
    print("=" * 60)
    print("  Commands: /exit, /clear, /help")
    print()

    global MODEL
    messages = []

    while True:
        try:
            user_input = input("\n\033[1;32mYou:\033[0m ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input.strip():
            continue

        cmd = user_input.strip().lower()

        if cmd == "/exit":
            print("Goodbye!")
            break

        if cmd == "/clear":
            messages.clear()
            print("Conversation cleared.")
            continue

        if cmd == "/help":
            print("  /exit  - Exit the CLI")
            print("  /clear - Clear conversation history")
            print("  /model - Show current model")
            print("  /model <name> - Switch model (llama-3.3, llama-3.2)")
            print("  /help  - Show this help")
            continue

        if cmd.startswith("/model"):
            parts = cmd.split(None, 1)
            if len(parts) > 1:
                alias = parts[1]
                if alias in AVAILABLE_MODELS:
                    MODEL = AVAILABLE_MODELS[alias]
                    print(f"  Model switched to: {alias} ({MODEL})")
                else:
                    print(f"  Available models: {', '.join(AVAILABLE_MODELS.keys())}")
            else:
                current_alias = next((k for k, v in AVAILABLE_MODELS.items() if v == MODEL), "unknown")
                print(f"  Current model: {current_alias} ({MODEL})")
                print(f"  Available: {', '.join(AVAILABLE_MODELS.keys())}")
            continue

        messages.append({"role": "user", "content": user_input})

        try:
            print("\033[1;34mAgent:\033[0m ", end="", flush=True)
            completion = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.2,
                top_p=0.7,
                max_tokens=2048,
                stream=False
            )
            reply = completion.choices[0].message.content
            print(reply)
            messages.append({"role": "assistant", "content": reply})
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Coding Agent API Server")
    parser.add_argument("--generate-key", action="store_true",
                        help="Generate NVIDIA API key via browser")
    parser.add_argument("--server", action="store_true",
                        help="Run as API server (uvicorn)")
    args = parser.parse_args()

    if args.generate_key:
        from key_generator import generate_api_key
        key = generate_api_key()
        if key:
            print("API key generated successfully.")
        else:
            print("Failed to generate API key.")
            exit(1)
    elif args.server:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        run_cli()
