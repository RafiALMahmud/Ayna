# Ayna local product RAG

## Architecture

`POST /api/v1/chat/search` normalizes English/Bangla terms and numerals, extracts exact filters,
executes parameterized SQLAlchemy queries against only active public catalog records, and fetches
live price, variant stock, images, 3D status, and try-on eligibility. Numerical price, availability,
color, size, category, 3D, and try-on constraints are never delegated to the LLM.

Descriptive requests use LangChain `OllamaEmbeddings` with `qwen3-embedding:0.6b`. A small JSON
vector index under ignored `.data` is hash-incremental: changed records re-embed, removed/unlisted
records disappear on the next request, and live SQL is always the authority. Cosine ranking is
bounded. If Ollama is unavailable, lexical ranking and deterministic response text are clearly
labeled; inventory is never invented.

Verified cards are passed to LangChain `ChatOllama(qwen3:0.6b)` under a strict catalog-only prompt.
Descriptions are explicitly untrusted data. Raw JSON/markdown model output is rejected in favor
of deterministic text. No arbitrary SQL tool exists, result count is bounded, question length is
300 characters, and no private user/order data enters context.

The React widget supports open/close, history, loading/error states, suggestions, English/Bangla
input, actual product cards/thumbnails/BDT prices/links, and mobile layout.

Tests cover Bangla numeral parsing, live price/color/size/stock filters, SQL/prompt injection text,
and table survival. Live checks produced a correct current shirt set, a truthful no-3D response,
a coherent Qwen response, and 1,024-dimensional embeddings. Complete final live multilingual
retest is recorded in `AYNA_TEST_REPORT.md`.
