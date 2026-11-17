# Ayna quality and storefront implementation

The default Ayna quality engine is CPU-safe and has no CUDA dependency. It calculates
interpretable silhouette, mean-color and pixel-difference signals only when a seller photo
and a generated render carry the same known camera label. Unknown or unmatched views return
`not_evaluated`; the engine never turns missing alignment into a numeric confidence score.
Mock generation creates labelled inspection renders but never treats its dummy geometry as
corresponding to seller photos, so its report remains `not_evaluated` and seller inspection
remains mandatory.

## CPU GLB inspection rendering

`backend/app/modules/quality/rendering.py` is an isolated, deterministic software renderer.
It needs only the Pillow version already pinned in `backend/requirements.lock`; Blender,
OpenGL, CUDA, browser automation and paid services are not required. The RQ/inline generation
worker invokes it after a GLB is stored, never from a request handler.

The renderer produces private 384 px PNG inspection views labelled `front`, `left`, `right`
and `back`. Each view records its orthographic camera position, target, media type, source GLB
SHA-256 and triangle count. The mock worker stores successful images under
`models/<job-id>/quality/<view>.png` and records their private keys and render metadata in job
provenance. These keys are not public storefront URLs.

Supported input is GLB 2.0 with embedded, uncompressed triangle meshes, node transforms and
material base colors. The CPU baseline deliberately does not interpret textures, skins,
animation, morph targets, Draco/meshopt compression or external buffers. It rejects more than
20,000 triangles, GLBs over 32 MiB, accessors over 100,000 elements, deeply nested node graphs
and views that exceed the bounded raster-work budget. Image size is constrained to 64–1,024 px.
A provider using an unsupported feature must supply its own isolated renderer or leave the
report `not_evaluated`.

Rendering and fidelity evaluation are separate operations. A camera label establishes only
the requested render direction; it does not prove correspondence to a seller photograph.
`build_quality_artifacts` compares a render only when the caller supplies a reference image
with the exact same known view label. Per-view failures produce `needs_review` when another
aligned view can be evaluated. A missing renderer, invalid GLB or total render failure produces
`not_evaluated` with no similarity numbers. The dummy mock GLB is rendered for pipeline and
storage verification but is always kept `not_evaluated` because it is not a reconstruction.

Run the renderer tests without Docker or GPU support:

```powershell
cd backend
..\.venv\Scripts\python -m pytest -q tests/test_quality_rendering.py
```

## Optional local SAM 2 and DINOv2 pathway

Both pretrained features are disabled by default. When enabled, the worker creates lazy
local-model callables only after exact camera-label alignment. No model is loaded by request
handlers and no loader accepts a Hugging Face model ID or downloads weights. The normal
CPU-interpretable silhouette, color and pixel-difference results remain available if an
optional package, checkpoint or inference call fails.

Configure only local resources:

| Environment variable | Meaning |
| --- | --- |
| `QUALITY_ENABLE_SAM2` | Opt in to foreground-mask refinement; default `false`. |
| `QUALITY_SAM2_CONFIG` | Explicit package-local Tiny/Small config, such as `configs/sam2.1/sam2.1_hiera_t.yaml`. |
| `QUALITY_SAM2_CHECKPOINT` | Absolute or explicit local path to the matching `.pt` checkpoint. |
| `QUALITY_ENABLE_DINOV2` | Opt in to advisory aligned-view correspondence; default `false`. |
| `QUALITY_DINOV2_MODEL_PATH` | Local Transformers model directory containing config and weights. Model IDs are rejected. |
| `QUALITY_DEVICE` | `cpu`, `auto`, or `cuda`; default `cpu`. `auto` uses CUDA only when locally available. |
| `QUALITY_MAX_IMAGE_SIZE` | Bounded inference/comparison size, default `384`, allowed range 128-1,024 px. |

The DINOv2 loader passes `local_files_only=True` and `trust_remote_code=False`. SAM 2 accepts
only the package-local Hiera Tiny/Small config allowlist and a checkpoint file that exists on
disk. Keep all model weights outside Git. Enabling SAM 2 without both config and checkpoint,
or DINOv2 without a model path, is a configuration error.

SAM 2 receives the deterministic foreground bounding box as its prompt and can only replace
the foreground masks used by silhouette and mean-color calculations. It does not modify the
source image, generated render or GLB. DINOv2 runs only after a seller photo and render share
the exact same known camera label. Its cosine similarity is recorded as an advisory signal;
it does not change pass/review thresholds and is never evidence of product identity.

Quality output adds these fields only for enabled features:

- `views.<label>.sam2_mask_refined`: whether both masks for that aligned view were refined.
- `views.<label>.dinov2_cosine_similarity`: advisory cosine similarity from -1 to 1.
- `optional_models.<model>.status`: `applied`, `partial`, or `unavailable`.
- `optional_models.<model>.applied_views`, `failed_views`, and `devices`: auditable execution metadata without exposing local paths.
- `optional_models.dinov2.identity_proof`: always `false`.

An unavailable optional model produces no optional numeric value. The deterministic baseline
is retained and its existing status remains authoritative. CUDA out-of-memory is retried once
on CPU after releasing cached optional models; a second failure is recorded as unavailable.
Other errors are not repeatedly retried.

### RTX 4050 lab recommendations

Run `python scripts/check_gpu.py` and `nvidia-smi` first. Install a CUDA-enabled PyTorch build
that matches the current NVIDIA driver in a separate virtual environment, then install the
official SAM 2 package and/or Transformers from their official projects. Use only SAM 2
Hiera Tiny/Small and DINOv2 Small checkpoints. Store weights outside Git and configure local
paths explicitly; Ayna never downloads model weights at API startup.

The tested isolated setup is reproducible with:

```powershell
python -m venv .venv-vision
.\.venv-vision\Scripts\python -m pip install -r worker\requirements-vision.txt
.\.venv-vision\Scripts\python scripts\check_vision_runtime.py
```

Recommended settings for 6 GB VRAM are batch size one, 384 px longest edge, inference mode,
and no concurrent local model jobs. Start with:

```powershell
$env:QUALITY_DEVICE='auto'
$env:QUALITY_MAX_IMAGE_SIZE='384'
$env:QUALITY_ENABLE_SAM2='true'
$env:QUALITY_SAM2_CONFIG='configs/sam2.1/sam2.1_hiera_t.yaml'
$env:QUALITY_SAM2_CHECKPOINT='D:\models\sam2.1_hiera_tiny.pt'
python scripts/check_gpu.py
```

For an optional locally cached DINOv2 Small model, also set
`QUALITY_ENABLE_DINOV2=true` and `QUALITY_DINOV2_MODEL_PATH` to that directory.

For the RTX 4050 laptop's 6 GB VRAM, prefer SAM 2.1 Hiera Tiny first, DINOv2 Small, batch size
one, 384 px inputs and one worker process running an optional-model job at a time. Do not run
concurrent SAM/DINO jobs on the same GPU. Use `QUALITY_DEVICE=auto` so a CUDA OOM can retry on
CPU. The normal Compose stack should remain `QUALITY_DEVICE=cpu`; this is also the Intel Iris
Xe-compatible path. Optional embeddings and masks cannot recover unseen product details,
validate authenticity, or replace seller review.

## Review and publication

Every approve/reject action is owner-authorized and appended to `review_audits`. Approval
requires the latest successful model and a non-failed quality report. Public list, detail,
image and model routes re-check current approval; corruption or a missing current model is
treated as unpublished. The browser keeps original photographs visible and falls back to
them when WebGL or the GLB fails.

## OpenCV alignment and interpretable measurements

`QUALITY_ENABLE_OPENCV_ALIGNMENT=false` by default. When enabled, `opencv_alignment.py`
uses bounded ORB features, a ratio test and RANSAC homography. A view is accepted only with
at least 12 candidate matches, at least 8 inliers, an inlier ratio of 0.5, and plausible
warped-area bounds. A shared camera label alone is never sufficient. Rejected alignment
returns no comparison metrics.

After accepted alignment, the engine reports foreground silhouette IoU,
lighting-normalized LAB chroma distance, Sobel texture-gradient difference and up to three
3×3 image regions with the largest aligned pixel difference. The regions help a reviewer
look at logos, lettering or details; the system does not recognize or verify any logo/text.
The current CPU GLB renderer does not support every texture, compression, skin or animation
feature, so provider assets outside its supported subset remain `not_evaluated`.

## Optional Blender optimization

Blender is disabled by default and is not part of the API/worker CPU baseline. Configure:

```text
BLENDER_OPTIMIZATION_ENABLED=true
BLENDER_EXECUTABLE=C:\Program Files\Blender Foundation\Blender 4.3\blender.exe
BLENDER_TIMEOUT_SECONDS=180
BLENDER_TARGET_TRIANGLES=20000
```

The worker invokes Blender headlessly in a temporary directory. The source GLB is retained.
The candidate must be smaller, meet the triangle target when decimation is needed, keep
bounds within 2%, retain material/texture/image/UV manifest counts and stay within an 0.08
mean rendered-difference bound. Failure, timeout or degradation publishes the untouched
original. Tests exercise the preservation/fallback logic with a fake subprocess; Blender was
not installed on the measured host, so this pathway remains partial until tested with real
textured GLBs and `bpy`.

## Measured local model evidence — 7 November 2026

Hardware reported by `nvidia-smi`: NVIDIA GeForce RTX 4050 Laptop GPU, driver 616.92,
6,141 MiB VRAM (4,597 MiB free immediately before the final run). Official weights are
outside Git under `D:\models\ayna-vision`.

| Model | Provenance / license | SHA-256 | Result |
| --- | --- | --- | --- |
| SAM 2.1 Hiera Tiny | Meta official checkpoint; Apache-2.0 code/model project | `7402E0D864FA82708A20FBD15BC84245C2F26DFF0EB43A4B5B93452DEB34BE69` | CUDA pass; 6.905 s; 597.84 MiB peak; 102,296 foreground pixels. |
| DINOv2 Small | `facebook/dinov2-small`, revision `ed25f3a31f01632728cabb09d1542f84ab7b0056`; Apache-2.0 | `AE1E99FCEFD534ED978CDEB8326F08030C96E28B7A81FFCBC98A857C84D14BE1` | CUDA pass; 29.057 s; 104.30 MiB peak; identical-image cosine 0.99999994. |

These are inference/load sanity checks on one demo photograph, not product reconstruction,
identity, quality or fidelity acceptance. The DINO value is intentionally not a threshold or
proof. `worker/requirements-vision.txt` includes the locked backend requirements so a fresh
isolated environment can run the scripts without borrowing another environment's packages.
