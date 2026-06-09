import os
import re
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

KEY_PATTERN = re.compile(r"nvapi-[A-Za-z0-9_-]+")

MODEL_URLS = {
    "3B": "https://build.nvidia.com/meta/llama-3.2-3b-instruct",
    "70B": "https://build.nvidia.com/meta/llama-3_3-70b-instruct",
}

MODEL_ENV_VARS = {
    "3B": "NVIDIA_API_KEY_LLAMA_3_2_3B",
    "70B": "NVIDIA_API_KEY",
}


def select_model_interactive():
    print()
    print("  " + "=" * 58)
    print("       Generate API Key")
    print("  " + "=" * 58)
    print()
    print("  [1] Llama 3.2 3B  (saves as NVIDIA_API_KEY_LLAMA_3_2_3B)")
    print("  [2] Llama 3.3 70B (saves as NVIDIA_API_KEY)")
    print()
    while True:
        try:
            choice = input("  Select [1-2]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return "3B"
        if choice == "1":
            return "3B"
        if choice == "2":
            return "70B"
        print("  Invalid choice. Enter 1 or 2.")


def check_playwright_installed():
    try:
        import playwright
        return True
    except ImportError:
        return False


def install_playwright():
    print()
    print("  Playwright is required for browser automation.")
    print("  Would you like to install it now? [Y/n]: ", end="")
    try:
        resp = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if resp and resp[0] == "n":
        return False
    print("  Installing playwright...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
        print("  Installing Chromium browser...")
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        return True
    except subprocess.CalledProcessError:
        print("  Failed to install playwright. Please run manually:")
        print("    pip install playwright && playwright install chromium")
        return False


def save_key_to_files(api_key: str, env_var: str, workdir: str = "."):
    key_file = Path(workdir) / "nvidia_api_key.txt"
    key_file.write_text(api_key, encoding="utf-8")
    print(f"  Key saved to: {key_file}")

    env_path = Path(workdir) / ".env"
    entry = f"{env_var}={api_key}"
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        if env_var + "=" in content:
            content = re.sub(rf"{re.escape(env_var)}=.*", entry, content)
        else:
            content += f"\n{entry}\n"
        env_path.write_text(content, encoding="utf-8")
        print(f"  .env updated: {env_path}")
    else:
        env_path.write_text(f"{entry}\n", encoding="utf-8")
        print(f"  .env created: {env_path}")

    home_env = Path.home() / ".coding_agent" / ".env"
    home_env.parent.mkdir(parents=True, exist_ok=True)
    if home_env.exists():
        content = home_env.read_text(encoding="utf-8")
        if env_var + "=" in content:
            content = re.sub(rf"{re.escape(env_var)}=.*", entry, content)
        else:
            content += f"\n{entry}\n"
        home_env.write_text(content, encoding="utf-8")
    else:
        home_env.write_text(f"{entry}\n", encoding="utf-8")
    print(f"  Home .env updated: {home_env}")

    load_dotenv(env_path, override=True)
    os.environ[env_var] = api_key


def generate_api_key(model: str = "70B", workdir: str = "."):
    if model not in MODEL_URLS:
        print(f"  Unknown model '{model}'. Use '3B' or '70B'.")
        return None

    url = MODEL_URLS[model]
    env_var = MODEL_ENV_VARS[model]

    if not check_playwright_installed():
        if not install_playwright():
            print("  Cannot proceed without playwright.")
            return None

    from playwright.sync_api import sync_playwright

    found_key = None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--start-maximized"]
        )
        context = browser.new_context(no_viewport=True)
        page = context.new_page()

        def on_response(response):
            nonlocal found_key
            if found_key:
                return
            try:
                body = response.body()
                text = body.decode("utf-8", errors="ignore")
                match = KEY_PATTERN.search(text)
                if match:
                    found_key = match.group(0)
            except Exception:
                pass

        page.on("response", on_response)

        page.goto(url, wait_until="domcontentloaded")

        print()
        print("  " + "=" * 58)
        print(f"  NVIDIA API Key Generator — Llama {model}")
        print("  " + "=" * 58)
        print()
        print("  A browser window has opened to build.nvidia.com")
        print("  Please log in to your NVIDIA account in the browser.")
        print("  The key will be detected automatically once generated.")
        print()
        print(f"  It will be saved as: {env_var}")
        print()
        print("  Press Ctrl+C at any time to cancel.")
        print()

        start_time = time.time()
        timeout = 300

        while found_key is None and (time.time() - start_time) < timeout:
            try:
                body_text = page.evaluate("document.body.innerText")
                match = KEY_PATTERN.search(body_text)
                if match:
                    found_key = match.group(0)
                    break
            except Exception:
                pass

            try:
                storage_data = page.evaluate("""() => {
                    let items = [];
                    for (let i = 0; i < localStorage.length; i++) {
                        items.push(localStorage.getItem(localStorage.key(i)));
                    }
                    for (let i = 0; i < sessionStorage.length; i++) {
                        items.push(sessionStorage.getItem(sessionStorage.key(i)));
                    }
                    return JSON.stringify(items);
                }""")
                match = KEY_PATTERN.search(storage_data)
                if match:
                    found_key = match.group(0)
                    break
            except Exception:
                pass

            try:
                current_url = page.url
                match = KEY_PATTERN.search(current_url)
                if match:
                    found_key = match.group(0)
                    break
            except Exception:
                pass

            time.sleep(1)

        browser.close()

    if found_key:
        print(f"\n  API Key detected: {found_key}")
        save_key_to_files(found_key, env_var, workdir)
        return found_key
    else:
        print("\n  No API key detected within the timeout period.")
        return None
