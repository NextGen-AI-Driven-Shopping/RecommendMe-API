# AI Integration

## AI Responsibilities in This Backend
AI is used for four runtime functions:
1. Query vagueness classification (`CLEAR`, `VAGUE`, `AMBIGUOUS`, `OUT_OF_SCOPE`).
2. Clarification question generation (pre-clarification, round 1, round 2).
3. Recommendation plan generation (category + product types with descriptions).
4. Post-recommendation chat follow-up answers.

AI is not used to fabricate product listings; product items come from SerpAPI.

## Provider Chain and Failover

## Shared Chain
`app/services/vagueness.py::_try_provider_chain`
- Order: Groq -> OpenAI -> Gemini -> Ollama.
- Model candidates are sourced from settings (`*_MODELS`, fallback defaults).
- The chain returns first non-empty textual response.

## Vagueness-Specific Classifier
`classify_vagueness` uses provider-specific functions with retries:
- `Groq`: up to 2 attempts (each attempt can iterate candidate models)
- `OpenAI`: up to 2 attempts
- `Gemini`: up to 2 attempts
- `Ollama`: up to 2 attempts

If all fail, classification is returned as `RETRY` with provider `busy`.

## Prompt Contracts

### 1. Vagueness Classification Prompt
- File: `app/prompts/vagueness_check.py`
- Enforces strict JSON output with classification and optional out-of-scope message.
- Definitions for all classes are embedded in prompt text.

### 2. Clarification Generation Prompts
- File: `app/prompts/clarification_decision.py`
- Prompt variants:
  - pre-clarification: exactly 1 question (+ options)
  - round 1: exactly 3 questions (+ options)
  - round 2: exactly 2 targeted questions (+ options)
- Rules explicitly discourage generic and repeated questions.

### 3. Recommendation Plan Prompt
- File: `app/prompts/category_reasoning.py`
- Enforces JSON with:
  - one `category`
  - list of `product_types` containing `product_type` and `description`
- Rules prohibit product-name generation, prices, URLs, and markdown wrappers.

### 4. Chat Mode Prompt
- File: `app/services/chat_mode.py` (`CHAT_SYSTEM_PROMPT`)
- Instructs assistant to answer only from supplied recommendation context and avoid hallucinated product facts.

## Parsing and Validation
- Common JSON extraction utility: `extract_json_payload`.
- Raw provider text is parsed by finding the first `{...}` object.
- Parse failures are treated as service errors and trigger fallback or endpoint-level error.
- Recommendation parser enforces non-empty product types; max 10 accepted.

## AI Context Handling

### Recommendation Context
Input can include:
- consolidated query (`original_query` + all clarification Q&A)
- prior conversation history (`conversation_history`)
- optional user profile fields (age, interests, gender)

### Chat Mode Context
Context string includes:
- original query
- clarification Q&A pairs
- category
- product type descriptions
- product item data (name/price/rating/source/link/etc.)
- optional profile hints

## Fallback and Reliability Behavior
- Provider-level model fallback (multiple candidates per provider).
- Cross-provider fallback chain.
- Varying timeout budgets per provider (`_PROVIDER_TIMEOUT`).
- For local Ollama, both `/api/chat` and `/api/generate` are attempted.

## Failure Modes
- Empty/invalid AI output -> parsing/validation error.
- All providers unavailable -> service-specific error path.
- Endpoint behavior on failure:
  - `/v1/query`: typically 503 via `AIServiceException`.
  - `/v1/chat/mode`: safe fallback text response if all providers fail.

## Non-AI Product Data Boundary
- Product cards are assembled from SerpAPI payload (`app/services/products.py`).
- AI provides only category/product-type reasoning and conversational text.
- This boundary reduces hallucinated catalog risk.

## Practical Operational Notes
- Because provider chain is sequential, full-failure scenarios can be latency-heavy.
- Model candidate lists are configurable via environment and `provider_models.yml`.
- Health endpoint (`/v1/health`) reports configuration/probe states but not full provider quality.
