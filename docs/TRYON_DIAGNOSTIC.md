# Private try-on diagnostic

Status: **partial**. Diagnostic mode implements customer consent, private upload, asynchronous
job progress, failure, retention, owner-only access and deletion without fabricating a result.

The completion branch also contains a tested opt-in `fashn_vton` local clothing backend. It produces
real generated pixels only when explicitly configured weights are present, but is restricted to
demo/evaluation: its required `fashn-human-parser` inherits NVIDIA noncommercial terms. Shoes are
rejected because FASHN supports clothing, not shoe-on-feet synthesis. This restriction prevents
the feature from being called commercially complete. Late results are discarded if the owner
deleted the job or retention expired while inference was running.

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

For the generated clothing preview, follow the pinned setup in `MODEL_LICENSE_INVENTORY.md`,
set `TRYON_PROVIDER=fashn_vton`, configure `TRYON_PYTHON`, `TRYON_SOURCE_PATH` and
`TRYON_WEIGHTS_PATH`, and explicitly acknowledge the noncommercial parser dependency. A real
offline RTX 4050 example completed in 93.942 seconds with 3,727.79 MiB peak PyTorch CUDA
allocation. The result is a generated appearance preview, never sizing or physical-fit evidence.

RQ is used in the container runtime; inline test/native mode completes the diagnostic during
the request while preserving the same persisted job states. The worker runs stale-job recovery
and expired-asset cleanup at startup and every `MAINTENANCE_INTERVAL_SECONDS` while alive.

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
