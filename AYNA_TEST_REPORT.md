# Ayna integration test report — 7 November 2026

## Local-AI completion branch — new evidence

Branch `feat/local-ai-completion` starts at `30ecc48`. No paid API, credit card, hosted
inference endpoint or trial was used.

| Check | Actual result |
| --- | --- |
| Offline TripoSR, Ayna demo bag, 128³ extraction | PASS: valid 584,172-byte GLB, 29,156 triangles; CUDA 10.31 s and 1,867.54 MiB peak. Output SHA-256 `D943FBB1CF0D1BCBFBA7E5C93A580D89103AEDE651A86C08AF9DED86A4D3D248`. Human review rejected the inferred back/side geometry as poor. |
| Offline TripoSR + bounded OpenCV GrabCut, demo headphones | PASS technically: valid 598,172-byte GLB, 29,856 triangles; CUDA 22.88 s and 1,867.54 MiB peak. Output SHA-256 `5151008E240E81C6E4A89F09885A682CC844D1F0B7E95D0477CD4E7D1A5B994C`. Human review again found poor inferred geometry; not approved for storefront publication. |
| Texture/vertex-color inspection renderer | PASS on the TripoSR vertex-color GLB and Khronos DamagedHelmet textured GLB: deterministic four-view renders. Metallic/roughness, animation, skins and compressed meshes remain unsupported. |
| Blender 5.2.3 real `bpy` run | EXECUTED on Khronos DamagedHelmet (evaluation asset with a CC BY-NC antecedent): 3,773,916 → 8,193,144 bytes at a 5,000-triangle target. Export lost one of five texture/image entries, so acceptance correctly failed and the production adapter retained the original. This is real failure-path acceptance, not an optimization PASS. |
| Offline FASHN VTON v1.5 official example | PASS technically: generated 768×1024, 561,264-byte PNG in 93.942 s with 3,727.79 MiB peak PyTorch CUDA allocation; SHA-256 `977A72620A563781AED34E70A46B96468E220927D0AD4E53B12CFF8381948E91`. Main bf16 synthesis used CUDA; ONNX pose estimation fell back to CPU. Human review found a coherent clothing preview. This remains demo-only because the required parser has noncommercial terms. |
| Backend suite and static gates | PASS: 94 passed, 1 skipped in 121.90 s; Ruff check, Ruff format check and MyPy all PASS. The skip is the optional OpenCV case in the ordinary backend environment. |
| Frontend lint/type/component/build | PASS: 15 tests in 7 files; production build PASS. Existing 809.04 kB lazy Three chunk warning remains. |
| Native desktop/mobile browser journeys | PASS after installing the matching Playwright Chromium: 6/6 in 40.9 s. Commerce, seller/admin, mock 3D review/approval and customer viewer journeys ran against local SQLite/files/inline mode. This is not PostgreSQL/RQ/MinIO evidence. |
| Local container integration | BLOCKED: Docker CLI 29.9.2 is present, but its config is access-denied, the `docker_engine` pipe is absent and this CLI has no Compose plugin. Existing GitHub Linux Compose evidence remains historical, not relabeled as this branch's local execution. |
| GitHub Actions, PR #5 run `42391764271` | PASS on commit `04d5d8b`: backend 1m34s, frontend 42s, Compose smoke 4m46s. The Linux Compose job is current-branch PostgreSQL/Redis/RQ/MinIO/browser evidence, but is not relabeled as a local Windows or second-physical-PC run. |

TripoSR checkpoint SHA-256 is
`429E2C6B22A0923967459DE24D67F05962B235F79CDE6B032AA7ED2FFCD970EE`.
Inference ran with network access disabled and local model/config paths. The CPU profile does not
claim practical TripoSR inference. Peak value is PyTorch CUDA allocation, not whole-process RAM.

## Remaining-features branch — current host evidence

Worktree: `D:\PROJECTS\Ayna-complete`, branch `feat/complete-remaining-features`, based on
primary `main` `bf9e16c`. No paid-provider key, request or credit was used.

| Exact command | Result |
| --- | --- |
| `python -m pytest -q --basetemp ..\.pytest-full` (backend) | PASS: **91 passed, 1 skipped**, 77.14 s. Skip is the optional OpenCV test in the CPU environment. |
| Vision environment `pytest tests/test_opencv_alignment.py -q` with backend packages on `PYTHONPATH` | PASS: **2 passed**, real OpenCV/NumPy, 3.20 s. |
| `python -m ruff check .` / `python -m ruff format --check .` / `python -m mypy app` | PASS; 73 files formatted, 45 app files type-checked. |
| `python -m alembic heads` / `upgrade head` / `check` | PASS; single `24df91a0bc72` head, no new operations. |
| `python -m scripts.export_openapi` then `npm run types:api` | PASS; OpenAPI and TypeScript generated sequentially. |
| `npm run lint` / `npm run typecheck` / `npm test -- --run` | PASS; **15 tests in 7 files**. |
| `npm run build` | PASS; main 353.22 kB raw/102.94 kB gzip, ModelViewer 182.21/58.01, Three viewer 809.04/204.70. Existing large lazy Three chunk warning remains. |
| Tripo/Meshy/Blender/recovery focused backend tests | PASS within the 91-test suite; provider HTTP and Blender subprocess are simulated, not live acceptance. |
| `docker version` | BLOCKED: CLI 29.9.2 exists, Docker config is access-denied and `docker_engine` pipe is absent. |
| `docker compose config --quiet` | BLOCKED: this CLI has no Compose plugin (`unknown flag: --quiet`). |
| `wsl --status` | BLOCKED: WSL is not installed. No volumes or data were deleted. |
| `blender --version` | BLOCKED: Blender is not installed or on PATH. |

`nvidia-smi` reports an NVIDIA GeForce RTX 4050 Laptop GPU, driver 616.92, 6,141 MiB
VRAM and 4,597 MiB free immediately before the final measurements. The OS API did not
return a reliable RAM total, so the previously stated 16 GB was not relabeled as a new
measurement.

Real official local-weight inference, weights outside Git:

| Exact command scope | Result |
| --- | --- |
| `vision_inference_smoke.py --model sam2 ... --device auto` | PASS on CUDA: SAM 2.1 Hiera Tiny, 6.905 s, 597.84 MiB peak, 102,296 mask pixels. |
| `vision_inference_smoke.py --model dinov2 ... --device auto` | PASS on CUDA: DINOv2 Small, 29.057 s, 104.30 MiB peak, identical-image cosine 0.99999994. This is advisory sanity only, not identity or fidelity. |

SAM checkpoint SHA-256 is
`7402E0D864FA82708A20FBD15BC84245C2F26DFF0EB43A4B5B93452DEB34BE69`;
DINO safetensors SHA-256 is
`AE1E99FCEFD534ED978CDEB8326F08030C96E28B7A81FFCBC98A857C84D14BE1`,
Hugging Face revision `ed25f3a31f01632728cabb09d1542f84ab7b0056`. Both projects declare
Apache-2.0. Model weights, customer photos and credentials are untracked.

Not executed on this branch: paid Meshy/Tripo requests or visual fidelity comparison,
real Blender/bpy optimization, a real try-on model/provider, local Windows Docker execution,
real Stripe/SMTP/carrier services, or a second physical PC. Reasons are respectively absent
spending authorization/keys, missing Blender, no approved try-on model, missing local
WSL/daemon/Compose plugin, and absent external infrastructure.

GitHub Actions run `42298719303` on commit `73840bb` supplied current Linux container
evidence: backend PASS (1m34s), frontend PASS (42s), and Compose smoke PASS (4m23s).
The Compose job executed config validation, full build/wait, migrations/startup,
PostgreSQL/Redis/RQ/MinIO mock generation/publication/revocation smoke, commerce smoke and
Playwright desktop/mobile journeys, then retained browser artifacts and stopped containers.
This is exact-branch CI evidence, not a second physical-PC claim. The local Windows Docker
blocker remains accurately recorded above.

Run in `E:\Ayna-integration` on Windows 11, Python 3.12.6, Node 22 and Chromium.
This is one host plus independently executed GitHub Linux CI, not two physical laptop
acceptances. No paid AI task, model weight download, real payment or outbound mail ran.

## Executed baseline and integration checks

Commands use the new worktree's `.venv` unless noted. Initial source review tests used
the existing identically pinned `E:\Ayna\.venv`; a fresh worktree environment was then
installed successfully and `pip check` reported no broken requirements.

| Exact command (working directory) | Result |
| --- | --- |
| `git fetch --all --prune` (original repo) | PASS; three origin branches discovered. |
| `git ls-remote --heads https://github.com/7illz/Ayna.git` | PASS; located the missing D2 feature branch. |
| `git fetch https://github.com/7illz/Ayna.git refs/heads/feat/quality-storefront:refs/remotes/dev2/feat/quality-storefront` | PASS; latest `1190fd6`. |
| `python -m venv .venv` / `.venv\Scripts\python.exe -m pip install -r backend/requirements.lock` (root) | PASS; fresh pinned backend installation. |
| `npm.cmd ci` (frontend) | PASS; 291 packages; 10 moderate development advisories reported. |
| `.venv\Scripts\python.exe -m pip check` (root) | PASS; no broken requirements. |
| `E:\Ayna\.venv\Scripts\python.exe -m pytest -q` (backend, merged D1/D2 baseline) | PASS; 47 tests. |
| Same command after provider/integration fixes (backend) | PASS; 67 tests, 104.86 seconds. |
| `..\.venv\Scripts\python.exe -m pytest -q` (backend, final suite with prior-head and route-uniqueness tests) | PASS; **70 tests**, 135.98 seconds. |
| `..\.venv\Scripts\python.exe -m pytest -q tests/test_migration_paths.py` (backend) | PASS; 2 prior-head upgrade/data-preservation tests. |
| `..\.venv\Scripts\python.exe -m ruff check .` (backend) | PASS. |
| `..\.venv\Scripts\python.exe -m ruff format --check .` (backend) | PASS; 58 files. |
| `E:\Ayna\.venv\Scripts\python.exe -m mypy app` (backend) | PASS; 38 application source files. |
| `..\.venv\Scripts\python.exe -m alembic heads` (backend) | PASS; one head, `e90d9ea58b33`. |
| `..\.venv\Scripts\python.exe -m alembic upgrade head` (backend, via native helper) | PASS; fresh schema at merged head. |
| `..\.venv\Scripts\python.exe -m alembic check` (backend, native SQLite settings) | PASS; no new operations detected. |
| `..\.venv\Scripts\python.exe -m scripts.export_openapi` (backend) | PASS; regenerated contract. |
| `npm.cmd run types:api` (frontend) | PASS; generated shared TypeScript schema. |
| `npm.cmd run lint` / `npm.cmd run typecheck` (frontend) | PASS. |
| `npm.cmd run test -- --run` (frontend) | PASS; **12 tests across 6 files**, including hosted-mode labels, cookie-seller studio access, single-flight/stale-response polling and delayed-cart login ordering. |
| `npm.cmd run build` (frontend) | PASS; Vite production build, separate lazy Three/viewer chunks. |
| `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-local.ps1 -ApiPort 8003 -WebPort 5176` (root) | PASS; native API and production preview ready. |
| Native helper stop + `start-local.ps1 -NoSeed -ApiPort 8003 -WebPort 5176` | PASS; owned processes stopped, data preserved and rebuilt. |
| `..\.venv\Scripts\python.exe -m scripts.smoke` (backend, native settings below) | PASS; two/five photos, dummy GLB, quality, approval/rejection, ownership and publication/revocation. Native mode uses inline work despite the historical script's RQ progress label. |
| `..\.venv\Scripts\python.exe -m scripts.commerce_smoke` (backend, native settings below) | PASS; concurrent last-unit checkout, COD, private order, cancel/restock. |
| `npm.cmd run test:e2e` (frontend, native settings below) | PASS; 6 journeys, desktop/Pixel 7, 1.6 minutes. |

Native live-check environment:

```powershell
$env:PYTHONUTF8='1'
$env:SMOKE_API_URL='http://localhost:8003'
$env:STOREFRONT_URL='http://localhost:5176'
$env:PLAYWRIGHT_BASE_URL='http://localhost:5176'
$env:E2E_API_URL='http://localhost:8003'
```

Browser coverage includes guest bag/coupon/register/COD, saved address, delivery tracking,
verified review, wishlist, comparison/removal/recent items, support; seller photos/options
and admin tools; studio photograph direction editing, generation, signed inspection renders,
actual changed canvas pixels after rotate/zoom, reset, approval, public original photos,
mobile overflow and broken-model photo fallback. Screenshots/traces are in the ignored
`frontend/test-results/`; they are not a second physical-PC result.

Hosted-provider tests use `httpx.MockTransport` and controlled fake data only. They cover
single submission, bounded polls, success/failure/incomplete output, task IDs, request caps,
four-of-five/front-first selection, no automatic retries, host restrictions, no redirects,
size limits, GLB validity and worker/private-storage integration. A simulated response does
not establish paid API availability or the appearance/fidelity of a real Meshy result.

## Initial failures found and corrected

- Four merge conflicts: resolved by combining both feature sets, not removing tests.
- Two migration heads: joined by an additive merge revision, tested from both old heads.
- First frontend type/build check failed because its config fixture lacked the new
  `seller_authenticated` field; corrected the typed fixture and reran successfully.
- A new hosted-mode unit assertion used Playwright's `exact` option in Testing Library;
  corrected it to an anchored accessible-name expression before the final build.
- Initial lint findings in new tests were formatting/import issues; corrected and reran.
- A generation round-trip check found stale generated types after parallel API/type
  generation. Regenerated OpenAPI first and TypeScript second; final stable regeneration
  is checked independently and again in CI.
- Docker engine initially failed because a junction pointed to a nonexistent D: directory.
  Recreated the directory and restarted Desktop; `docker info` returned 29.1.3.
- The first container-unit command supplied JSON through PowerShell/Docker argument
  quoting incorrectly and failed configuration parsing. Isolated unit-test CORS/storefront
  settings in `conftest.py`, matching its existing test-only database/queue settings, so
  tests work independently of the live server's custom ports without shell JSON overrides.
- Private inspection renders had been stored but were not accessible in the seller UI;
  added signed routes and browser coverage. Mock label regression and authenticated studio
  permissions were fixed. Review notes are bounded; full decisions remain in audit rows.
- First local Docker browser run: 5 passed, 1 failed because approval's successful HTTP
  response took 5.687 seconds during concurrent heavy checks, exceeding the assertion's
  5-second default. Trace confirmed HTTP 200. The test now awaits and verifies that
  response/body before asserting the UI, with a bounded rendering allowance. No product
  or quality check was removed.
- A second container-browser run hit the 5-second mobile canvas-change limit. Kept the
  pixel-change assertion with a bounded 15-second graphics allowance. Source review also
  found overlapping asynchronous polls and late responses after product changes; polling
  is now single-flight with cancellation guards, covered by a deferred-response unit test.
- Another local run exposed a real login race: seller navigation became available before
  cart refresh completed, then the delayed login redirect replaced the seller page. Moved
  the cart refresh before publishing signed-in navigation and added a deferred-cart UI test.

## Historical integration-host GPU and other unavailable tests

| Executed command | Actual result |
| --- | --- |
| `E:\Ayna\.venv\Scripts\python.exe scripts/check_gpu.py` | Diagnostic ran: no `nvidia-smi`, no installed torch, no CUDA/GPU reported on this host. Not an RTX acceptance. |
| `E:\Ayna\.venv\Scripts\python.exe scripts/check_vision_runtime.py` | Exit 1 / unavailable: `No module named 'cv2'`. Optional vision packages were not installed into the CPU backend. |

Not executed: real SAM 2 masks, real DINOv2 embeddings, GPU memory/latency/OOM experiments,
live Meshy credits/output fidelity, Tripo, Blender optimization, virtual try-on, real R2,
Stripe settlement/refunds, SMTP delivery and carrier integration. Reasons: no configured
credentials/local weights or applicable GPU here, or feature not implemented. Developer
2's earlier GPU-import/tensor results remain attributed to their report, not relabelled
as this engineer's inference tests. Run the exact separate commands in
`AYNA_BOTH_PC_TESTING.md` on the RTX machine; Intel Iris Xe can run all normal mock tests.

Non-failing notices: existing Starlette/httpx TestClient deprecation, lazy Three chunk
larger than 500 kB, and development dependency advisories. Do not force breaking dependency
downgrades to silence them. Docker startup repair initialized a new disk at the missing
junction target; no earlier disk/volume was deleted or restored.

## Container and GitHub evidence

Container validation uses a distinct Compose project `ayna-integration` and ports 8004/5177,
with BDT/COD/mock/CPU defaults. Remote CI repeats checks on Linux. The final integration PR
contains the immutable tested head SHA, CI links and merge result. Results below are added
only when their commands finish successfully; earlier bootstrap/commerce CI is not reused
as proof that this integration passed.

Executed container environment:

```powershell
$env:API_PORT='8004'
$env:WEB_PORT='5177'
$env:VITE_API_BASE_URL='http://localhost:8004'
$env:STOREFRONT_URL='http://localhost:5177'
$env:CORS_ORIGINS='["http://localhost:5177"]'
```

| Exact command (repository root) | Result |
| --- | --- |
| `docker compose -p ayna-integration config --quiet` | PASS. |
| `docker compose -p ayna-integration up --build -d --wait --wait-timeout 240` | PASS; fresh images built; API/web/worker/PostgreSQL/Redis/MinIO healthy; migration/storage init exited 0. |
| `docker compose -p ayna-integration up --build -d --wait --wait-timeout 240 api worker` | PASS; refreshed backend image with final test files; data retained. |
| `docker compose -p ayna-integration exec -T api python -m scripts.seed_shop` | PASS. |
| `docker compose -p ayna-integration exec -T api alembic check` | PASS; no new upgrade operations. |
| `docker compose -p ayna-integration exec -T api python -m scripts.smoke` | PASS; real PostgreSQL/RQ/Redis/MinIO, two/five-photo generation and publication/revocation. |
| `docker compose -p ayna-integration exec -T api python -m scripts.commerce_smoke` | PASS; PostgreSQL last-unit race/COD/private order/cancel/restock. |
| `docker compose -p ayna-integration exec -T api ruff check .` | PASS. |
| `docker compose -p ayna-integration exec -T api ruff format --check .` | PASS. |
| `docker compose -p ayna-integration exec -T api mypy app` | PASS; 38 source files. |
| `docker compose -p ayna-integration build api` followed by `docker compose -p ayna-integration run --rm --no-deps api pytest -q` | PASS; **70 tests**, 206.77 seconds, isolated test databases/files. |
| `docker compose -p ayna-integration build web` and `docker compose -p ayna-integration up -d --no-deps --wait --wait-timeout 120 web` | PASS; final polling/login fixes loaded without resetting infrastructure. |
| `npm.cmd run test:e2e` with web `http://localhost:5177` and API `http://localhost:8004` | Final rerun **PASS: 6/6**, 2.3 minutes, desktop/mobile, real PostgreSQL/RQ/MinIO. |

GitHub CI on initial integration head `f996383` passed all backend/frontend/Compose jobs:
[PR run](https://github.com/RafiALMahmud/Ayna/actions/runs/42205604466),
[push run](https://github.com/RafiALMahmud/Ayna/actions/runs/42205529095).
The final small test-isolation/UI assertion fixes are checked again on the exact PR head
before merge; final SHA/CI evidence is attached to PR #3.
