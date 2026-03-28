"""Shared prompt/message construction and model JSON parsing utilities."""

from __future__ import annotations

import json
from typing import TypeAlias

Messages: TypeAlias = list[dict[str, str]]


def build_chat_messages(
    *,
    system_prompt: str,
    query: str,
    context: list[dict[str, str]] | None = None,
) -> Messages:
    """Build a standard chat payload with optional context turns."""
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        raise ValueError("query must be a non-empty string")

    messages: Messages = [{"role": "system", "content": system_prompt}]
    if context:
        messages.extend(context)
    messages.append({"role": "user", "content": cleaned_query})
    return messages


def extract_json_payload(text: str) -> dict:
    """Extract and parse the first JSON object present in model output text."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")
    return json.loads(text[start : end + 1])
