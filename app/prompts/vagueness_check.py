from __future__ import annotations
from typing import Any

def build_vagueness_prompt(query: str, history: list | None = None) -> list[dict[str, str]]:
    system_prompt = (
        "You are a shopping assistant. Determine if the query is CLEAR or VAGUE. "
        "If VAGUE, return 3 follow-up questions. "
        "Format: JSON only. Example: {\"classification\": \"VAGUE\", \"follow_ups\": [\"...\", \"...\", \"...\"]}"
    )
    
    messages = [{"role": "system", "content": system_prompt}]

    if history:
        for msg in history:
            # Handle Pydantic objects or Dicts
            role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else "user")
            content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else "")
            
            if role in ["user", "assistant"] and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": query.strip()})
    return messages