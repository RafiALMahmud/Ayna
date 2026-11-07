# Ayna — testing on both Windows PCs

These are reproducible commands, not a claim that this integration engineer accessed two
physical PCs. Developer 2's submitted hardware observations remain in
`docs/DEV2_TEST_RESULTS.md`; this integration run independently verifies only its own host
and GitHub's Linux CI. Never copy another machine's PASS into your acceptance record.

## Shared checkout and CPU baseline

PowerShell, Python **3.12**, Node **22.21+**, Git, and (for container checks) Docker Desktop
with WSL2 Linux containers are required. Before merge use `integration/ayna-full-system`;
after the integration PR is merged use `main`.

```powershell
git clone https://github.com/RafiALMahmud/Ayna.git
Set-Location Ayna
git fetch --all --prune
git switch main
git pull --ff-only origin main
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock
npm.cmd --prefix frontend ci
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

If you already have a checkout with uncommitted changes, preserve them and use a separate
worktree instead of switching across conflicting files. Do not reset or discard them.
Keep `AI_PROVIDER=mock`, `MESHY_DAILY_REQUEST_LIMIT=0`, `QUALITY_DEVICE=cpu`, and both
optional quality flags false for baseline testing. Inspect your existing ignored `.env`;
the commands above intentionally do not overwrite it.

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m ruff format --check .
..\.venv\Scripts\python.exe -m mypy app
..\.venv\Scripts\python.exe -m scripts.export_openapi
Set-Location ..\frontend
npm.cmd run types:api
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run test -- --run
npm.cmd run build
Set-Location ..
git diff --exit-code docs/openapi.json frontend/src/shared/api-schema.d.ts
```

For PostgreSQL/Redis/MinIO integration:

```powershell
docker info
docker compose config --quiet
docker compose up --build -d --wait --wait-timeout 240
docker compose exec -T api python -m scripts.seed_shop
docker compose ps
docker compose exec -T api alembic current
docker compose exec -T api alembic check
docker compose exec -T api python -m scripts.smoke
docker compose exec -T api python -m scripts.commerce_smoke
Set-Location frontend
npx.cmd playwright install chromium
$env:PLAYWRIGHT_BASE_URL='http://localhost:5173'
$env:E2E_API_URL='http://localhost:8000'
npm.cmd run test:e2e
Set-Location ..
docker compose down
```

Default web/API ports are 5173/8000; adjust the two browser variables to match your `.env`.
Never add `-v` to shutdown if you need to preserve data. Native fallback:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-local.ps1
# Shop: http://localhost:5175  API: http://localhost:8002/docs
Set-Location frontend
$env:PLAYWRIGHT_BASE_URL='http://localhost:5175'
$env:E2E_API_URL='http://localhost:8002'
npm.cmd run test:e2e
Set-Location ..\backend
$env:PYTHONUTF8='1'
$env:SMOKE_API_URL='http://localhost:8002'
$env:STOREFRONT_URL='http://localhost:5175'
..\.venv\Scripts\python.exe -m scripts.smoke
..\.venv\Scripts\python.exe -m scripts.commerce_smoke
Set-Location ..
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop-local.ps1
```

Native SQLite/files/inline mode is not a PostgreSQL/RQ/MinIO certification. Each machine
should complete `docs/TEST_RESULTS_TEMPLATE.md` with its SHA, commands, screenshots,
PASS/FAIL and actual environment. Both browser viewport projects run on one machine;
they are not tests of two laptops or a physical phone.

## Developer 1 — Intel Iris Xe

Run the entire shared baseline above. No CUDA, NVIDIA driver, PyTorch, weights or paid key
is needed. Mock generation uses a magenta dummy GLB; quality is `not_evaluated` and original
photos stay authoritative. Test both two-photo and five-photo inputs, invalid files, owner
isolation, approval/rejection/revocation, keyboard rotate/zoom/reset, and photo fallback.

Hosted Meshy testing is a **separate, potentially paid** action only after merchant
authorization. The app never runs it from CI. Enter a key only in the ignored `.env` and
set these values deliberately (do not paste a real key into command history or Git):

```text
AI_PROVIDER=meshy
MESHY_API_KEY=<enter privately in .env>
MESHY_DAILY_REQUEST_LIMIT=1
GENERATION_SELLER_DAILY_LIMIT=1
MESHY_TIMEOUT_SECONDS=900
```

Restart API and worker with `docker compose up -d --force-recreate api worker`. The native
start helper deliberately forces mock mode; use Compose/RQ for hosted work. In Product
studio, upload front first plus a second view, label directions, then click the explicitly
priced Meshy generation button once. Five photos remain stored; the adapter selects at
most four with front first. Record task ID, actual credits from the provider dashboard,
GLB, errors and all visual mismatches. Never retry an ambiguous submission before checking
the provider dashboard. Failed/cancelled requests still consume the local rolling-24-hour
request allowance. Tripo is also available only when selected explicitly with its own key
and positive `TRIPO_DAILY_REQUEST_LIMIT`; it requires at least two named views total,
including `front`.
Never switch automatically or retry an ambiguous submission. Revert to mock and cap zero
after testing.

Reference: [official Meshy multi-image API](https://docs.meshy.ai/en/api/multi-image-to-3d).
The adapter is tested with HTTP simulations; this guide is not a live-provider PASS.

## Developer 2 — RTX 4050, 6 GB VRAM / 16 GB RAM

For free real reconstruction, complete the pinned commands in
`docs/MODEL_LICENSE_INVENTORY.md`, then set:

```text
AI_PROVIDER=local_triposr
LOCAL_TRIPOSR_PYTHON=D:\models\triposr-venv\Scripts\python.exe
LOCAL_TRIPOSR_SOURCE=D:\models\triposr-src
LOCAL_TRIPOSR_MODEL_PATH=D:\models\triposr-weights
LOCAL_TRIPOSR_MC_RESOLUTION=128
```

The measured 6 GB profile uses CUDA for inference and CPU scikit-image surface extraction.
Only the front/first photo conditions TripoSR; all other uploaded photos remain comparison
evidence. Keep mock mode on the CPU PC. Do not describe the measured 10–23 second GPU runs as
CPU support.

Run the same CPU/Compose tests first. Then use an isolated optional vision environment:

```powershell
nvidia-smi
python -m venv .venv-vision
.\.venv-vision\Scripts\python.exe -m pip install -r worker/requirements-vision.txt
.\.venv-vision\Scripts\python.exe scripts/check_gpu.py
.\.venv-vision\Scripts\python.exe scripts/check_vision_runtime.py
.\.venv-vision\Scripts\python.exe -c "import torch; print('CUDA:', torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only')"
```

The pinned optional requirements came from Developer 2. If your driver cannot support
that CUDA wheel, select a compatible build using [PyTorch's official installer](https://pytorch.org/get-started/locally/)
in the isolated environment and record the exact versions. Do not change the CPU backend
lock to fix a local GPU installation. Import success and a random CUDA convolution do not
prove SAM 2 or DINOv2 inference works.

Obtain licensed Tiny/Small weights explicitly from the official projects outside Git:
[SAM 2](https://github.com/facebookresearch/sam2),
[DINOv2](https://github.com/facebookresearch/dinov2).
SAM config and checkpoint versions must match. DINOv2 must be a complete local Transformers
directory, not a remote model ID. No weights are downloaded by Ayna.

```powershell
# Replace these existing local paths with your own weights.
.\.venv-vision\Scripts\python.exe scripts/vision_inference_smoke.py --model sam2 --image backend/fixtures/demo/bag.jpg --checkpoint D:\models\sam2.1_hiera_tiny.pt --sam2-config configs/sam2.1/sam2.1_hiera_t.yaml --device auto
.\.venv-vision\Scripts\python.exe scripts/vision_inference_smoke.py --model dinov2 --image backend/fixtures/demo/bag.jpg --checkpoint D:\models\dinov2-small --device auto
```

These commands run real local mask/embedding inference only if packages and weights exist.
They report elapsed time, actual device and peak CUDA allocation. DINO uses an identical-image
sanity check, not product-identity verification. Record failures instead of marking PASS
when a package/checkpoint is absent. Optional loader and OOM fallback logic is tested with
substitutes in the baseline suite. On 7 November 2026 this host also ran real local inference:
SAM 2.1 Hiera Tiny on CUDA in 6.905 s / 597.84 MiB peak, and DINOv2 Small in 29.057 s /
104.30 MiB peak. This is a loader and identical-image sanity acceptance, not product-fidelity
or identity validation.

Use batch one, 384 px, inference mode and one GPU job at a time. The runtime retries CUDA
OOM once on CPU after clearing cached models. A second failure remains unavailable.
Keep these experiments outside the baseline Docker image. Configure optional paths/flags
only in the isolated worker environment, with the selected weights mounted read-only.

The explicit TripoSR profile above is the supported local reconstruction experiment. Keep its
weights outside Git, use one isolated process, and retain seller review: the measured examples
fit 6 GB VRAM but failed human geometry acceptance. Never claim photorealistic reconstruction
simply because CUDA inference completed.

## Virtual try-on — real clothing synthesis, commercial acceptance remains partial

The implemented diagnostic is available only for shirts, pants and shoes. It requires an
authenticated customer, explicit processing consent and no-training acknowledgement.
Shirts accept upper- or full-body framing; pants/shoes require a portrait full-body image.
The upload is validated, metadata-stripped, stored privately, processed as an asynchronous
job, retained for at most `TRYON_RETENTION_HOURS` (24 by default) and deletable immediately.

Set `TRYON_PROVIDER=diagnostic` for the safe lifecycle-only pathway or `disabled` to turn it off. It checks
dimensions/aspect framing only. Body/feet visibility, pose, occlusion and placement remain
`not_evaluated`; no result image is created. The UI and API explicitly say it does not verify
sizing or fit. Test account isolation, consent, invalid framing, deletion and retention with
`pytest -q tests/test_tryon.py` and the `TryOnPanel` frontend tests.

For a real generated clothing preview, complete the exact pinned FASHN setup in
`docs/MODEL_LICENSE_INVENTORY.md`, configure the three external paths, set
`TRYON_PROVIDER=fashn_vton`, and explicitly acknowledge the noncommercial parser dependency.
The official example ran fully offline on this RTX 4050 in 93.942 seconds with 3,727.79 MiB peak
PyTorch CUDA allocation. Shirts and pants map to FASHN tops/bottoms; shoe-on-feet generation is
unsupported. Generated previews never prove sizing or physical fit.

Commercial completion still requires replacing or separately licensing the noncommercial parser,
a permissive shoe model, broader representative human review, and explicit surfaced pose/
occlusion diagnostics. A rotating GLB is not try-on.
