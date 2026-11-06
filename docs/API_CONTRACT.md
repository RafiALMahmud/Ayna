# Ayna — shared API and data contract (baseline, both developers)

Purpose: copy this file to `docs/API_CONTRACT.md` during the bootstrap stage. **Both branches use the same document**. It is intentionally small; implement actual OpenAPI/Pydantic models and generate TS types from FastAPI. Do not silently change response fields or enums.

## Resources

- `Product`: `id`, `seller_id`, `name`, `category`, `description`, `images[]`, `created_at`, `updated_at`, `publish_status`. Accepted `publish_status`: `draft|generating|needs_review|approved|rejected`. The 2–5 input photo requirement applies when submitting a generation job, not during first product creation.
- `ProductImage`: `id`, `product_id`, `storage_key`, `view_tag`, `sort_order` (never make private object keys or original user photos public by default).
- `GenerationJob`: `id`, `product_id`, `provider`, `status`, `progress`, `created_at`, `finished_at`, `error_code`, `model_asset_url`, `preview_asset_urls[]`. Status: `queued|processing|succeeded|failed|cancelled`. Treat `model_asset_url` as nullable until the model is ready; never expose private URLs to unauthorized clients.
- `QualityReport`: `product_id`, `job_id`, `status`, `metrics`, `notes`, `uncertain_views[]`, `reviewed_by`, `reviewed_at`. Status: `pending|pass|needs_review|failed|not_evaluated`. Missing camera alignment -> do not invent numerical fidelity scores.
- `TryOnJob`: private `id`, `user_id`, `product_id`, `provider`, `framing`, consent/retention
  timestamps, status/progress/diagnostics and nullable private source/result keys. Status:
  `queued|processing|needs_review|succeeded|failed|deleted`. Keys and customer photos are
  never public response fields.

## API prefix: `/api/v1`

- `POST /products`, `GET /products`, `GET /products/{id}`: seller-scoped product create/list/detail.
- `POST /products/{id}/images`: seller image upload, maximum five per product; two minimum before generation.
- `POST /products/{id}/generation-jobs`: queue generation and return job identifier.
- `GET /generation-jobs/{job_id}`: poll status and access authorized results.
- `GET /products/{id}/quality`: authorized quality report (may be `not_evaluated`).
- `POST /products/{id}/review`: approve/reject with notes, authorized owner only.
- `GET /store/products`, `GET /store/products/{id}`: approved products only; original photos + approved model metadata.
- `GET /health`, `GET /ready`: health endpoints.
- `POST /try-on/products/{id}/jobs`: authenticated consented multipart diagnostic for
  eligible shirts/pants/shoes; idempotent and asynchronous.
- `GET /try-on/jobs/{id}`, `DELETE /try-on/jobs/{id}`: owner-only status and deletion.
- `GET /try-on/jobs/{id}/result`: owner-only result bytes when a real configured pathway
  succeeds; diagnostic mode intentionally has no result.

## Collaboration and privacy contract

- Dev1 owns `catalog/`, `generation/`, seller UI, queue/provider integrations and storage; Dev2 owns `quality/`, `public_catalog/`, review UI and storefront viewer.
- Seed endpoints, database models and TS types in bootstrap. Extend with additive changes by PR review.
- A mock adapter is the default, and its GLB is an intentionally dummy fixture with explicit disclosure. No paid provider call in CI or default test mode.
- Ayna's 3D model is AI-generated and may contain inferred unobserved angles. Seller approval is mandatory prior to publication.
- Hide raw provider credentials, private object keys and customer photos; never present inferred product details as verified.
