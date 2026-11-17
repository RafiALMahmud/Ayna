# Virtual try-on diagnosis

## Long-sleeve to short-sleeve quality diagnosis - 16 November 2026

Private debug capture is behind `TRYON_DEBUG` (off by default) and writes only to the Git-ignored
`.data/tryon-debug/` tree. It records inputs, poses, parser IDs and legend, replacement mask,
prepared garment, raw outputs and final composite. These artifacts and paths never enter public
logs or persisted job diagnostics.

On the authorized pair, the parser produced 151,805 source `top` pixels but only 18 `arms` pixels
and 183 `hands` pixels: it classified the long jacket sleeves as garment, as expected. The
computed replacement mask covered 99.9954% of those top pixels. The defect was not a missing mask
or gamma conversion. FASHN v1.5 defaults to `segmentation_free=True`, so production bypassed the
correct mask and conditioned synthesis on the original long sleeves. This is diagnosis category
**(c), bad conditioning region**; the evidence rules out (a), (b) and (d).

`TRYON_SKIN_RECOVERY` now defaults on. Long-to-short and long-to-sleeveless cases build refined
arm, hand, neck and old-sleeve masks, run a second deterministic synthesis with a texture-
preserving face/neck Lab skin condition, normalize low-frequency arm color, and composite only
inside the feathered support. Other sleeve transitions skip recovery. SAM 2 is not loaded because
the measured 6 GB profile already reaches about 5.8 GB total VRAM.

The truthful sequence now includes skin recovery at 90% between CUDA synthesis at 75% and output
validation at 95%. Recovery timing, sleeve case, application status and Lab deltas persist in
bounded runtime diagnostics. The final private proof measured forearm-to-face Lab delta **27.2705
before** and **3.0830 after**, with outside-support L1 exactly **0.0**. Visual review rejected two
intermediate blocky variants before accepting the texture-preserving path.

## 17 November 2026 visible-skin preservation follow-up

The final compositor now parses the unpadded raw output and derives the output garment region
from garment labels plus thresholded changes adjacent to that region. Source face, hair, hands,
already-visible skin and background outside the garment region are restored from the source with
a four-pixel feather; the eroded preservation core is pixel-identical. Newly exposed skin is the
only area eligible for low-frequency recovery. Recovery removes model detail, matches the nearest
real source skin in Lab space and retains only broad illumination.

The output-resolution policy is explicit: the generated image is resized to the **original input
width and height** with Lanczos before compositing. The source is never downscaled to the model's
output resolution. A measured long-sleeve-to-short-sleeve run returned 683 x 911 from a 683 x 911
source in 164.441 seconds. CUDA synthesis used `cuda:0` and reported 3,727.79 MiB peak PyTorch
allocation; output parsing ran on CPU and the recovery/composite stage took 0.135 seconds.

The requested bare-arm tattoo fixture was not present under `.data/fixtures`; the supplied prompt
contained the literal placeholder `<PATH, under .data/fixtures>`. Consequently the required
recovery-off/on/three-seed diagnosis is not yet measurable, and no claim is made about which stage
introduces tattoos on that photograph. The opt-in regression test is ready and skips unless the
authorized fixture paths, CUDA and weights are supplied.

The stage sequence adds `output_parsing` at 85% between CUDA synthesis (75%) and conditional skin
recovery (90%). Skin recovery is omitted entirely when its real mask is empty.

Optional `detail_restoration` runs at 93% after compositing and before encoding. It is a classical
unsharp pass restricted to the parsed garment/new-skin edit region; the preservation core is
restored from the source afterward. `TRYON_RESTORE` defaults off because no consented real-fixture
evaluation is available.

## 9 November 2026 timeout investigation

Job `ae553b3d-68d7-4047-8a24-c89937d20e89` used a 683 x 911 RGB person image and a
900 x 900 garment image. It remained at the old generic 30% state and reached the configured
900-second deadline. The primary error was `TRYON_TIMEOUT`, but Windows temporary-directory
cleanup raised `PermissionError` because `process.kill()` stopped only the virtual-environment
launcher while its child Python process still held files. That cleanup exception masked the
timeout, so the database incorrectly stored `TRYON_FAILED`.

The slow work was DWPose preprocessing, not CUDA synthesis. PyTorch 2.11.0+cu128 correctly sees
the NVIDIA GeForce RTX 4050. ONNX Runtime GPU 1.31.1 advertises CUDA and TensorRT providers, but
its CUDA provider requires CUDA 13/cuDNN 9 and failed to load `cublasLt64_13.dll` on this verified
CUDA 12.8 PyTorch environment. Both DWPose sessions therefore fell back to CPU. No CUDA package
was installed or replaced. DWPose now uses an explicit bounded CPU provider (four intra-op
threads, one inter-op thread); FASHN bf16 synthesis remains on CUDA.

## Repair

- The child emits persisted events for process startup, model loading, pose detection, human
  parsing, garment preparation, CUDA synthesis, image encoding and output validation. Progress
  changes only on those real events: 10, 20, 35, 50, 65, 75, 95 and 100 percent.
- Each FASHN launcher gets its own Windows process group. Timeout/cancellation runs
  `taskkill /PID <pid> /T /F`, waits for the tree, drains the log, then removes the temporary
  directory. Cleanup warnings are diagnostic metadata and cannot replace the primary error.
- Failures retain a private, path-sanitized, bounded 16,000-character inference log. Public logs
  and job diagnostics contain no private image bytes or paths.
- Exact codes such as `TRYON_TIMEOUT`, `TRYON_CANCELLED` and output-validation failures persist.
  Failed source uploads remain until user deletion or retention expiry.
- GPU work is serialized. The API rejects a second active FASHN request, and the worker has a
  same-process lock as a second guard. Ollama is CPU-only, uses bounded concurrency and unloads
  before GPU work.
- Output must be a decodable PNG with valid dimensions before success. The result is stored under
  a separate key; neither input is overwritten.

## Final real RTX 4050 evidence

The same job and unchanged input pair succeeded on the final code in **184.237 seconds**. Persisted
stage completion times were: startup/imports 27.445 s, model loading 43.885 s, pose 45.678 s,
human parsing 46.894 s, garment preparation 46.914 s, CUDA synthesis 183.915 s, image encoding
184.236 s and output validation 184.237 s. Main synthesis used `cuda:0` with bf16 and reported
3,727.79 MiB peak PyTorch CUDA allocation. External sampling observed 98-100% GPU utilization and
about 5.76-5.78/6.14 GB total VRAM.

The result is a valid 576 x 769 PNG (584,207 bytes). Person and garment SHA-256 hashes were
identical before and after both retries. After completion, Ollama had no loaded model, no FASHN
Python/CUDA process remained, and no `ayna-fashn-*` temporary directory remained. Four stale
private temp directories left by the old implementation were also removed after their owning
processes were confirmed absent.

## Earlier deadlock repair

An earlier upload stall had a separate cause: verbose FASHN output filled an unread Windows pipe.
The child now writes to a file that the parent incrementally drains, and native inline mode starts
real FASHN work after returning the persisted job response. Both the pipe deadlock and the later
process-tree/cleanup masking failure are covered by the current implementation.
