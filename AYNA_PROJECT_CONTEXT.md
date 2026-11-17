# Ayna Project Context

Updated: 16 November 2026 (Asia/Dhaka)

## Project summary

Ayna is a full-stack e-commerce application with optional private AI workflows:

- Customer storefront, search, filters, cart, wishlist, comparison and recently viewed items.
- BDT checkout, cash on delivery, coupons, delivery charges, orders, returns and reviews.
- Customer, seller and administrator roles with cookie-based sessions.
- Seller product studio with private product photographs and reviewed 3D previews.
- Private clothing appearance previews using local FASHN VTON.
- A local product assistant using LangChain and Ollama.

AI output is optional. Products remain sellable when AI features are unavailable. Generated
clothing images are appearance previews only; they do not verify sizing or predict physical fit.

## Repository state

- Canonical local repository: `D:\PROJECTS\Ayna-complete`
- The repository is standalone. The obsolete duplicate `D:\PROJECTS\Ayna` was deleted after
  its Git objects and branches were preserved here.
- Current branch: `feat/local-ai-completion`
- The CUDA environment-isolation follow-up is committed as `1dff007`.
- Remote: `https://github.com/7illz/Ayna.git`
- The existing branch is pushed to `origin/feat/local-ai-completion`; no merge is authorized.
- Latest committed-branch GitHub Actions run passed backend, frontend, Compose smoke and browser
  checks: `https://github.com/7illz/Ayna/actions/runs/42592338313`.
- There is currently no pull request for this branch and nothing has been merged.

### Latest try-on quality milestone

The branch includes the Ollama/FASHN CUDA environment isolation and a default-on, sleeve-aware
skin-recovery stage. Private debug capture is disabled by default. It proved that FASHN's
segmentation-free conditioning retained the source long sleeves even though the computed
replacement mask covered 99.9954% of the parsed garment region.

Long-to-short and long-to-sleeveless transitions now run a second deterministic synthesis with a
texture-preserving face/neck Lab condition, then composite only inside the refined arm support.
Other sleeve transitions skip recovery. The final measured forearm-to-face Lab delta improved
from 27.2705 to 3.0830, and the outside-support L1 difference was exactly 0.0.

Final validation: backend Ruff/MyPy/Alembic passed with 110 tests passing and two intentional
skips; the opt-in RTX integration passed separately in 150.04 seconds. Frontend generated types,
lint, typecheck, 20 component tests and the production build passed. No orphan FASHN process or
temporary directory remained.

## Technology

### Backend

- Python 3.12
- FastAPI
- SQLAlchemy and Alembic
- PostgreSQL in Docker; SQLite for the native Windows demo
- Redis and RQ for production/container background jobs
- MinIO/S3-compatible private object storage; local private files in native mode
- Pillow, PyTorch and optional vision/model environments

### Frontend

- React 19 and TypeScript 5.9
- Vite 8
- Tailwind CSS
- React Three Fiber and Three.js
- Vitest/Testing Library
- Playwright browser tests

### Local AI

- FASHN VTON v1.5 for clothing appearance previews.
- PyTorch 2.11.0+cu128 for CUDA synthesis on the RTX 4050.
- ONNX Runtime GPU 1.31.1 advertises CUDA, but requires CUDA 13 while the verified PyTorch
  runtime uses CUDA 12.8. DWPose is therefore explicitly bounded to CPU; main synthesis remains
  CUDA.
- Ollama 0.40.15 with `qwen3:0.6b` and `qwen3-embedding:0.6b`, intentionally CPU-only.
- Optional local TripoSR for experimental single-image 3D reconstruction.
- Optional SAM 2, DINOv2, OpenCV alignment and Blender quality/optimization adapters.

## Important directories

| Path | Purpose |
| --- | --- |
| `backend/app/` | FastAPI application and domain modules |
| `backend/migrations/` | Alembic database migrations |
| `backend/tests/` | Backend unit/integration tests |
| `frontend/src/` | React application |
| `frontend/tests/` | Playwright browser journeys |
| `scripts/` | Windows startup, Ollama, model runner and diagnostics scripts |
| `docs/` | API contract and detailed implementation documents |
| `.data/` | Ignored root runtime logs and process records |
| `backend/.data/` | Ignored native SQLite database, private assets, RAG index and try-on logs |

Model source, environments and weights are stored outside Git, normally below `D:\models` on
this RTX host. Never commit weights, customer images, generated private results, databases,
credentials or `.data` contents.

## Native Windows operation

One-time dependency setup from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
npm.cmd --prefix frontend ci
```

Start the ordinary local demo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-local.ps1
```

Start with the configured local FASHN model and RTX synthesis:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-local.ps1 `
  -ApiPort 8002 -WebPort 5175 -EnableFashn
```

Expected endpoints:

- Storefront: `http://localhost:5175`
- API documentation: `http://localhost:8002/docs`
- Ollama: `http://127.0.0.1:11434`

Stop the recorded Ayna API/web processes while retaining local data:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop-local.ps1
```

At the time this context was written, Ayna's API and web server were stopped. Ollama was running.
The existing `.data/local-processes.json` record may be stale and must not be trusted without
checking the recorded PID and start time.

## FASHN try-on behavior

Truthful persisted progress stages are:

| Progress | Stage |
| ---: | --- |
| 10% | Input preparation / subprocess startup |
| 20% | Model loading |
| 35% | Pose detection |
| 50% | Human parsing |
| 65% | Garment preparation |
| 75% | CUDA synthesis |
| 90% | Sleeve-aware skin recovery when applicable |
| 95% | Image encoding and output validation |
| 100% | Succeeded or failed |

Progress changes only on actual model events. CUDA synthesis is one long operation, so 75% may
remain unchanged for several minutes. A healthy RTX run should persist
`runtime.synthesis_device = "cuda"`, use approximately 5.7 GB total VRAM and show high GPU
utilization. If diagnostics say `cpu` or `cuda_available = false`, do not claim RTX execution.

The final opt-in RTX integration used the authorized 683 x 911 person image and 900 x 900 garment
and passed in 150.04 seconds including pytest/subprocess overhead. PyTorch's last measured peak
was 3,727.79 MiB. The earlier external sample observed 5,818/6,141 MiB total VRAM, so SAM 2 is not
loaded in this 6 GB recovery profile.

Timeout and cancellation terminate the full Windows process tree. Exact error codes such as
`TRYON_TIMEOUT`, `TRYON_CANCELLED`, `TRYON_OUTPUT_INVALID` and `TRYON_INFERENCE_FAILED` are
persisted. Failure logs are bounded and path-sanitized. Original uploads remain private and
unchanged after inference failure until the user deletes them or retention expires.

FASHN's required human parser carries NVIDIA noncommercial terms. This path is demo/research-only
and must not be presented as commercially licensed. Shoes are unsupported by the verified local
model.

## Privacy and security boundaries

- Try-on uploads and results are private, owner-scoped and never public product assets.
- Uploaded images are metadata-stripped and never used for model training.
- Inputs and generated results use different storage keys; inference must never overwrite input.
- User deletion removes the private upload/result. Retention cleanup removes expired bytes.
- No private paths, image bytes or credentials belong in public logs.
- Hosted paid AI providers require explicit enablement, server-side keys and positive request
  limits. Ayna never silently falls back to a paid service.
- Development accounts and demo payments are forbidden in production configuration.

## Validation commands

Backend:

```powershell
cd backend
..\.venv\Scripts\python.exe -m ruff format --check app tests ..\scripts\local_fashn_vton.py
..\.venv\Scripts\python.exe -m ruff check app tests ..\scripts\local_fashn_vton.py
..\.venv\Scripts\python.exe -m mypy app
..\.venv\Scripts\python.exe -m pytest -q --basetemp ..\.pytest-final
..\.venv\Scripts\python.exe -m alembic check
```

Frontend:

```powershell
cd frontend
npm.cmd run types:api
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run test -- --run
npm.cmd run build
```

The final candidate passed 110 backend tests with two intentional skips, Ruff, MyPy, Alembic,
20 frontend tests and the production build. The opt-in CUDA test passed separately on the RTX.

## Docker profile

Docker mode uses PostgreSQL, Redis/RQ and MinIO and is separate from native SQLite/local storage:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose config --quiet
docker compose up --build -d --wait --wait-timeout 240
docker compose exec -T api python -m scripts.seed_shop
docker compose ps
```

`docker compose down` retains volumes unless an explicit volume-removal option is supplied.

## Key documentation

- `README.md` - setup and feature overview
- `AYNA_PROGRESS.md` - implementation progress and remaining validation
- `AYNA_TRYON_DIAGNOSIS.md` - Windows FASHN timeout/process analysis
- `AYNA_GPU_PERFORMANCE.md` - measured RTX/Ollama behavior
- `AYNA_TEST_REPORT.md` - executed checks and limitations
- `AYNA_OLLAMA_SETUP.md` - local CPU-only Ollama setup
- `AYNA_RAG_CHATBOT.md` - product assistant architecture
- `AYNA_MODEL_LICENSES.md` and `docs/MODEL_LICENSE_INVENTORY.md` - model provenance/licenses
- `AYNA_FEATURE_CHECKLIST.md` - completed and outstanding feature matrix
- `docs/openapi.json` - generated API contract

## Immediate next steps

1. Review the pushed try-on quality change and its private visual proof locally.
2. Test a second authorized person/garment pair for human quality acceptance.
3. Keep the noncommercial parser limitation visible for every FASHN demo.
4. Do not merge the branch without review.
