# AI Model Pipeline

## Purpose

This document explains the AI-assisted stages of the backend recommendation flow.

## Stage 1: Query Vagueness Classification

Module: `app/services/vagueness.py`

What it does:
- Determines if a query is `CLEAR`, `VAGUE`, or `RETRY`.

Why it exists:
- Avoids low-quality recommendations when user intent/context is under-specified.

How it works:
1. Build vagueness prompt from query and optional domain hint.
2. Try providers in fallback order.
3. Parse response into strict classification structure.
4. If vague, return follow-up questions.
5. If all providers fail, return retry/busy path.

Provider order:
- Groq -> OpenAI -> Gemini -> Ollama

## Stage 2: Clarification Sufficiency Planning

Module: `app/services/clarification.py`

What it does:
- Scores whether collected clarifications are sufficient.
- Generates additional follow-up questions when needed.

Why it exists:
- Enforces structured question progression before recommendation generation.

How it works:
- Uses dynamic signal extraction across domain-specific weights.
- Computes sufficiency score.
- Returns next-step plan (sufficient or more questions).

## Stage 3: Category And Product-Type Reasoning

Module: `app/services/recommender.py`

What it does:
- Produces one display category and up to 10 product types with descriptions.

Why it exists:
- Separates semantic recommendation planning from listing retrieval.

How it works:
1. Normalize conversation context.
2. Call provider adapters in fallback order.
3. Parse and validate normalized output (`CategoryReasoningResult`).
4. Return first successful provider result.

Provider order:
- Groq -> OpenAI -> Gemini -> Ollama

## Stage 4: Product Listing Retrieval

Modules:
- `app/routes/v1/query.py`
- `app/services/products.py`

What it does:
- Fetches product cards for each generated product type.

Why it exists:
- Moves from semantic planning to concrete recommendation items.

How it works:
1. Build search query per product type with context signals.
2. Try SerpAPI with bounded retries.
3. On failures/quota exhaustion, fall back to direct Google fetch.
4. Return product list or empty list/degraded response path.

## Stage 5: Chat Follow-Up Answering

Module: `app/services/chat_mode.py`

What it does:
- Answers post-recommendation user questions using session context.

Why it exists:
- Supports conversational follow-up on generated recommendations.

How it works:
- Build flattened context from session product payloads and profile metadata.
- Try provider-based answer generation.
- Fall back to heuristic answer strategies when needed.

## Inputs And Outputs Summary

## Inputs
- Query text and conversation history.
- Clarification answer list.
- Session context snapshots.
- Provider keys/models from settings.

## Outputs
- Clarification question payloads.
- Recommendation payload with category and product types.
- Product card lists with data-source and degradation metadata.
- Chat follow-up responses.

## Pipeline Constraints (Code-Evident)

- Product type count is capped (`[:10]` in query orchestration).
- Product fetch attempts are bounded and may degrade gracefully.
- Provider failure paths return retry/busy semantics instead of hard process failure.
