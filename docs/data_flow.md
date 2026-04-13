# Data Flow

## End-to-End Query Flow (`POST /v1/query`)

## Stage 1: Input Validation
- `sanitize_and_validate_query` sanitizes text and enforces:
  - length bounds
  - null-byte stripping
  - simple injection pattern detection
- Invalid input raises `ValidationException` -> HTTP 422.

## Stage 2: Request De-Duplication
- `request_id` is read from payload or generated.
- In-memory `request_cache` is pruned and checked.
- If a cached payload exists (within 30s), it returns immediately.

## Stage 3: Session Initialization and Message Append
- `session_id` is read from payload or generated.
- Existing session loaded or initialized (`status=new`, timestamps).
- User message serialized and appended to session `messages`.
- `original_query` persisted for multi-step flow continuity.

## Stage 4: Pipeline Branching
Branch decision uses `clarification_round` and count of `clarification` answers:
- `>=5 answers` or `round=2` -> generate recommendations.
- `>=3 answers` or `round=1` -> generate round-2 questions.
- `round=0` and at least one answer -> generate round-1 questions.
- otherwise classify vagueness first.

## Stage 5: Vagueness Classification
- Service: `classify_vagueness`.
- Provider order: Groq -> OpenAI -> Gemini -> Ollama.
- Provider attempts: 2 per provider.
- Outcomes:
  - `OUT_OF_SCOPE`: return out-of-scope response.
  - `VAGUE`/`AMBIGUOUS`: pre-clarification question generation.
  - `CLEAR`: round-1 question generation.
  - `RETRY`: currently treated as AI failure path upstream (503).

## Stage 6A: Pre-Clarification (Round 0)
- Service: `generate_preclarification_question`.
- Output: one question with options.
- Session status -> `clarification_needed`, `clarification_round=0`.

## Stage 6B: Clarification Round 1
- Service: `generate_round1_questions`.
- Output: exactly 3 question slots (pads fallback questions if AI returns fewer).
- Session stores `pending_questions`, `clarification_round=1`.

## Stage 6C: Clarification Round 2
- Service: `generate_round2_questions` with first 3 Q&A pairs.
- Output: exactly 2 question slots (pads if needed).
- Session stores round-2 pending questions.

## Stage 7: Recommendation Plan Generation
- Build consolidated query:
  - `original_query`
  - all clarification Q&A pairs in text form
- Service: `generate_recommendation_plan`.
- AI output expected as JSON:
  - one category
  - up to ten product types with descriptions
- Parse/validation failures raise `RecommendationServiceError` -> HTTP 503.

## Stage 8: Product Retrieval Fan-Out
- For each product type:
  - call `fetch_product_items` (SerpAPI)
  - mark `serp_error` on per-type failure
- Parallelization:
  - `asyncio.gather`
  - bounded by `Semaphore(4)`
- Serp retrieval behavior:
  - one retry if first attempt returns no items/fails
  - max 10 items/type
  - price normalization helper applies INR-style formatting

## Stage 9: Response Assembly
- `build_recommendation_response` maps internal models to API schema.
- Only product items with required card fields are emitted to response (`pt.valid_items`).
- Session snapshot updated with:
  - status `recommendations`
  - category and product type payload
  - `latest_response`
  - appended assistant message

## Stage 10: Return and Cache
- Response cached in request de-dup store for request id TTL window.
- Returned to caller.

## Session Data Model
Session entries contain fields observed in current code paths:
- `session_id`
- `status` (`new`, `clarification_needed`, `recommendations`)
- `title`
- `user_id` (optional)
- `messages[]`
- `created_at`, `updated_at`
- `original_query`
- `clarification_round`
- `pending_questions`
- `clarification_answers`
- `category`
- `product_types`
- `latest_response`

## Auth/Profile Data Flow

### Signup/Login
- Signup writes CSV user row (`auth_csv`), creates default profile (`profile_store`), emits signed token.
- Login validates CSV record and password hash, returns token and profile.
- If session id is provided at login, session store is updated with authenticated user id.

### Password Reset
- Forgot-password stores reset token + expiry in profile JSON.
- Reset-password validates token lookup from profile store and rewrites password hash/salt in CSV.

### Profile Updates
- Profile upsert/update persists in JSON store keyed by user id.
- Avatar upload writes binary file to configured upload directory and stores local file path in profile.

## Chat Mode Data Flow (`POST /v1/chat/mode`)
1. Load session by id.
2. Validate recommendation context exists.
3. Build full textual context (query, clarifications, product data, optional user profile).
4. Ask AI provider chain for answer.
5. Append user + assistant messages to session and persist.
6. Return `ChatModeResponse`.

## Error Flow
- Business/validation errors raise explicit HTTP exceptions.
- Query validation and AI failures map to 422/503.
- Unknown exceptions are logged with traceback and emitted as 500 generic message.
