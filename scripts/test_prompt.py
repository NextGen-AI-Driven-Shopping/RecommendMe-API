"""
Developer utility: run a prompt against GPT-4o from the terminal.

Usage:
    python scripts/test_prompt.py --prompt "best noise-cancelling headphones"

Requires OPENAI_API_KEY to be set in your environment or a .env file.
"""

import argparse
import asyncio

from app.core.config import get_settings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test a prompt against GPT-4o.")
    parser.add_argument("--prompt", type=str, required=True, help="The prompt to send.")
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override the model (defaults to settings.openai_model_primary).",
    )
    return parser.parse_args()


async def run(prompt: str, model: str | None = None) -> None:
    settings = get_settings()
    target_model = model or settings.openai_model_primary
    print(f"[test_prompt] Model  : {target_model}")
    print(f"[test_prompt] Prompt : {prompt}")
    print("[test_prompt] (OpenAI call not implemented in skeleton — wire up openai.AsyncOpenAI here)")


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(run(args.prompt, args.model))
