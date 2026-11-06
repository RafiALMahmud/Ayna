# Private try-on diagnostic

Status: **partial**. Ayna implements the customer consent, private upload, asynchronous job,
progress, failure, retention, owner-only access and deletion workflow. It does not currently
run a real virtual try-on model or provider and returns no fabricated overlay/result.

## Supported input

- Eligible categories: `shirts`, `pants`, `shoes` only.
- Shirts: upper-body or portrait full-body photograph.
- Pants and shoes: portrait full-body photograph intended to show head to feet.
- JPEG, PNG or WebP with matching signature, bounded by `TRYON_MAX_IMAGE_BYTES` and the
  common image pixel limit. The sanitized shortest edge must be at least 512 pixels.
- Explicit processing consent and acknowledgement of no model-training use are required.

The diagnostic validates file safety, dimensions and coarse aspect framing. It cannot yet
detect a missing body/feet, pose ambiguity or occlusion; those values are reported as
`not_evaluated`. It does not verify product sizing or physical fit.

## Configuration

```text
TRYON_PROVIDER=diagnostic       # or disabled
TRYON_RETENTION_HOURS=24        # 1–168
TRYON_MAX_IMAGE_BYTES=10485760
```

RQ is used in the container runtime; inline test/native mode completes the diagnostic during
the request while preserving the same persisted job states. The worker purges expired assets
at startup. Production operations should also schedule worker restarts or call the cleanup
function periodically so the retention bound does not depend on customer activity.

## API

- `POST /api/v1/try-on/products/{product_id}/jobs`: authenticated multipart request with
  `photo`, `framing`, `consent`, `no_training` and `Idempotency-Key`.
- `GET /api/v1/try-on/jobs/{job_id}`: owner-only status.
- `DELETE /api/v1/try-on/jobs/{job_id}`: owner-only immediate source/result deletion.
- `GET /api/v1/try-on/jobs/{job_id}/result`: owner-only and 404 in diagnostic mode.

Customer body photos have no public route, never appear in catalog responses and are never
included in job JSON. Original upload metadata is removed before storage. A result route is
reserved for a future approved real provider, but it still requires the authenticated owner.

## Completion criteria for a real pathway

Before changing the feature from partial, select a model/provider with verified commercial
terms, explicitly configured weights/credentials, no automatic download, and measured
operation on supported hardware. Add actual body/foot visibility, pose and occlusion handling,
representative human-reviewed clothing/shoe outputs, privacy/retention validation and clear
synthetic-result labeling. Attractive output alone is not acceptance.
