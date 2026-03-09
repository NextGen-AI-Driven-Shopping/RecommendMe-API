"""
Developer utility: verify that Ollama is running and the configured model is loaded.

Usage:
    python scripts/check_ollama.py

Prints a PASS / FAIL status for each check performed.
Reads OLLAMA_BASE_URL and OLLAMA_MODEL from your .env file.
"""

import asyncio

import httpx

from app.core.config import get_settings


async def check_ollama() -> None:
    settings = get_settings()
    base_url = settings.ollama_base_url.rstrip("/")
    model = settings.ollama_model

    print(f"[check_ollama] Base URL : {base_url}")
    print(f"[check_ollama] Model    : {model}")
    print(f"[check_ollama] Checking connectivity ...")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/api/tags")
            response.raise_for_status()

            data = response.json()
            available_models = [m["name"] for m in data.get("models", [])]

            print(f"[check_ollama] PASS — Ollama is reachable.")
            print(f"[check_ollama] Available models: {available_models or '(none loaded)'}")

            if any(model in name for name in available_models):
                print(f"[check_ollama] PASS — Model '{model}' is loaded and ready.")
            else:
                print(
                    f"[check_ollama] WARN — Model '{model}' not found. "
                    f"Run: ollama pull {model}"
                )

    except httpx.ConnectError:
        print(
            f"[check_ollama] FAIL — Cannot connect to Ollama at {base_url}. "
            "Is Ollama running?  Start it with: ollama serve"
        )
    except httpx.HTTPStatusError as exc:
        print(f"[check_ollama] FAIL — Unexpected HTTP {exc.response.status_code} from Ollama.")
    except Exception as exc:
        print(f"[check_ollama] FAIL — Unexpected error: {exc}")


if __name__ == "__main__":
    asyncio.run(check_ollama())
