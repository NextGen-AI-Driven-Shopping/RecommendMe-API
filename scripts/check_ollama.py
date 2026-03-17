"""
Developer utility: verify that Ollama is running and the configured model is loaded.

Usage:
    python scripts/check_ollama.py
"""

import asyncio
import httpx

from app.core.config import get_settings


async def check_ollama():

    settings = get_settings()

    base_url = settings.ollama_base_url.rstrip("/")
    model = settings.ollama_model

    print("\nChecking Ollama server\n")

    print("Base URL:", base_url)
    print("Model:", model)
    print()

    try:

        async with httpx.AsyncClient(timeout=5.0) as client:

            response = await client.get(f"{base_url}/api/tags")

            response.raise_for_status()

            data = response.json()

            models = [m["name"] for m in data.get("models", [])]

            print("PASS: Ollama server reachable")

            if models:
                print("Available models:", models)
            else:
                print("No models found")

            if model in models:
                print(f"PASS: Model '{model}' is loaded")
            else:
                print(f"WARNING: Model '{model}' not found")
                print(f"Run: ollama pull {model}")

    except httpx.ConnectError:

        print("FAIL: Cannot connect to Ollama")
        print("Start Ollama with: ollama serve")

    except Exception as exc:

        print("Unexpected error:", exc)


if __name__ == "__main__":
    asyncio.run(check_ollama())