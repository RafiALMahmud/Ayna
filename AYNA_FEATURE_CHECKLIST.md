# Ayna feature audit — 7 November 2026

Evidence: reviewed source, merged histories, automated tests and the execution record in
`AYNA_TEST_REPORT.md`. `[x]` implemented and tested; `[~]` partial; `[ ]` missing;
`[!]` implemented but broken. Tests listed here are actual test files, not proof of live
hosted inference. No feature is complete merely because a module exists.

**59 audited items: 50 complete, 9 partial, 0 missing, 0 known broken.** Real SAM 2 and
DINOv2 Small inference ran locally on the RTX 4050. Tripo, Blender, OpenCV quality and
try-on remain partial for the precise live-validation reasons shown below.

Ownership: D1 = existing bootstrap/commerce implementation (`f42bf5a`, `400c30b`);
D2 = fork `7illz/Ayna`, commits `a56edc4`, `ba710bf`, `1190fd6`;
INT = integration fixes. The named D1 seller-generation branch does not exist; attribution
follows actual commit content, not the branch names promised in the kit.

## A. E-commerce foundation

| Status | Feature / owner | Source | Coverage / issue / next action |
| --- | --- | --- | --- |
| [x] | Ayna brand/navigation — D1/D2 | `frontend/src/App.tsx`, `features/commerce/CommerceApp.tsx` | App unit tests and commerce/studio browser journeys; preserve ordinary shop as homepage. |
| [x] | Catalog/detail — D1/D2 | commerce `catalog.py`, `Catalog.tsx`, storefront `Storefront.tsx` | `test_commerce.py`, `App.test.tsx`, both e2e specs; approved 3D separate from normal listing. |
| [x] | Seller dashboard — D1 | `features/seller/Studio.tsx`, commerce `Seller.tsx` | `App.test.tsx`, seller/admin browser test; cookie seller access retained when legacy auth disabled. |
| [x] | 2–5 generation photos — D1/INT | catalog `routes.py`, `CreateProduct.tsx` | `test_workflow.py`, `test_integration.py`, workflow browser test; ordinary commerce listings may use one photo. |
| [x] | Image preview/validation — D1 | `sanitize_image`, `CreateProduct.tsx` | MIME/signature/byte/pixel/EXIF/atomic-upload tests; original files stay private. |
| [x] | PostgreSQL integration — D1/INT | `common/db.py`, `migrations/` | Fresh Linux Compose CI, migrations and live smoke; local SQLite is a separate test mode. |
| [x] | Identity/permissions — D1/INT | `common/identity.py`, `auth.py`, commerce `accounts.py` | `test_commerce.py`, `test_integration.py`; production rejects development auth. |
| [x] | Product APIs — D1/INT | catalog/commerce routes, generated OpenAPI | Workflow, commerce and contract tests; image labels/order are owner-scoped. |
| [x] | Responsive frontend — D1/D2 | `styles.css`, `commerce.css`, viewer | Desktop/Pixel 7 e2e overflow checks and visual screenshots; not a physical phone certification. |
| [x] | Seller review history — D2/INT | `ReviewAudit`, quality `routes.py` | Workflow audit assertions; repeated long notes bounded while decisions remain append-only. |

## B. AI-based 3D reconstruction

| Status | Feature / owner | Source | Coverage / issue / next action |
| --- | --- | --- | --- |
| [x] | Image preprocessing — D1 | catalog `sanitize_image` | Orientation, resize, metadata removal and validation tests; segmentation is separate below. |
| [x] | SAM 2 — D2 | quality `optional_models.py`, `scripts/vision_inference_smoke.py` | Official SAM 2.1 Hiera Tiny checkpoint ran on CUDA: 6.905 s and 597.84 MiB peak. Local-only loader, foreground-mask scope, unavailable/OOM fallback tests; no identity claim. |
| [x] | Multiple views — D1/INT | image-order endpoint, generation `meshy.py` | Front-first/distinct-labelled four-of-five selection tests; all five originals retained. No automatic sharpness ranking. |
| [~] | Meshy — INT | generation `meshy.py`, `routes.py`, `tasks.py` | HTTP simulations cover submission/poll/download/quota/worker integration. No paid task run; authorized live product comparison still required. |
| [~] | Tripo/fallback — D2 | generation `tripo.py`, routes/tasks | Current v3 upload/multiview/poll/download contract is simulated and bounded. No credential, credit budget or live reconstruction was supplied; no automatic paid-provider switching. |
| [x] | Queue/status polling — D1/D2/INT | generation routes/tasks, `worker.py` | Idempotency, failure, duplicate claim, progress and stale-job recovery tests. Known hosted IDs reconcile; ambiguous paid submission fails without a duplicate charge. |
| [x] | GLB creation/storage — D1/D2/INT | providers, `meshy.py`, storage, rendering | Deterministic GLB, embedded-resource validation, bounded downloads, private renders, live storage smoke. |
| [~] | Blender optimization — D2 | generation `blender.py`, `scripts/blender_optimize.py` | Isolated opt-in subprocess, timeout, original retention and bounds/material/UV/render/file-size gates are tested with a fake runner. Blender is not installed here, so real bpy optimization is not accepted. |
| [x] | Failed-generation handling — D1/D2/INT | generation `tasks.py`, seller UI | Queue outage, provider timeout/failure, malformed asset and render failure tests; ambiguous submissions are not retried automatically. |
| [x] | Free mock mode — D1/D2 | `MockProvider`, quality service | Deterministic/offline tests and browser/Compose smoke; dummy explicitly labelled, never scored as reconstruction. |

## C. AI quality and realism

| Status | Feature / owner | Source | Coverage / issue / next action |
| --- | --- | --- | --- |
| [x] | DINOv2 — D2 | `optional_models.py`, `scripts/vision_inference_smoke.py` | Official `facebook/dinov2-small` local weights ran on CUDA: 29.057 s and 104.30 MiB peak. Identical-image cosine is only a loader sanity/advisory signal, never product identity proof. |
| [~] | OpenCV comparison engine — D2 | quality `opencv_alignment.py` | Actual ORB/RANSAC alignment, inlier/area gates, foreground, lighting-normalized color, texture-gradient and localized-region metrics pass synthetic warp/rejection tests with real OpenCV. Representative difficult seller-photo/render acceptance is still absent. |
| [~] | Geometry/silhouette — D2 | `analysis.py`, `rendering.py` | Synthetic aligned-pair/IoU tests; no calibrated seller cameras, 3D ground truth or hidden-side verification. |
| [~] | Photo/render comparison — D2/INT | quality service, OpenCV alignment, review UI | Direction labels alone no longer authorize scores. Accepted correspondence is required; ambiguous views return `not_evaluated`. No calibrated hosted-product dataset yet. |
| [~] | Color/texture matching — D2 | `analysis.py`, `opencv_alignment.py` | Aligned raster checks normalize luminance and compare chroma/texture gradients. The CPU GLB renderer still cannot render every provider texture/compression feature. |
| [~] | Logos/important details — D2 | `opencv_alignment.py` localized regions | Top localized difference regions guide human inspection only; there is no logo/text recognition or correctness certification. |
| [x] | Quality report persistence — D1/D2 | `QualityReport`, quality service/routes | `test_quality_analysis.py`, `test_quality_rendering.py`, workflow tests; actual unknowns remain unknown. |
| [x] | Unverified angles — D1/D2 | report `uncertain_views`, review/viewer disclosure | Missing/invalid/mismatched-view tests; no fabricated percentages. |
| [x] | Seller approve/reject — D1/D2/INT | quality routes, `ReviewPanel.tsx` | Ownership/state/audit/failed-report tests, review component and browser tests; revokes public model on rejection. |
| [x] | Regeneration — D1/INT | generation routes, seller Studio | Idempotent replay, new-key regeneration and revocation tests; paid retries remain explicit and consume cap. |

## D. Customer 3D experience

| Status | Feature / owner | Source | Coverage / issue / next action |
| --- | --- | --- | --- |
| [x] | R3F/Three.js viewer — D1/D2 | `shared/ModelViewer.tsx`, `LazyModelViewer.tsx` | Viewer unit tests and loaded-GLB browser test; ordinary shop remains lazy. |
| [x] | Rotation — D2/INT | viewer OrbitControls/CameraRig | Accessible buttons and browser canvas-change assertion; rotation does not certify 360-degree product accuracy. |
| [x] | Zoom/pan/reset — D2/INT | viewer controls | Unit loading/fallback checks and browser zoom/reset interaction; pan uses pointer/touch controls. |
| [x] | Mobile layout — D1/D2 | viewer/styles | Pixel 7 browser viewport and overflow checks. |
| [x] | Loading/errors — D1/D2 | Suspense/ViewerBoundary | Component tests plus injected broken-model browser fallback. |
| [x] | Original photo comparison — D1/D2 | storefront/review/gallery | Gallery/detail tests; generated inspection views clearly distinguished from photos. |
| [x] | Approved-only model publication — D1/D2/INT | public catalog, commerce product view | Ownership/approval/current-success/archival/suspension/revocation tests; normal non-3D sales remain independent. |

## E. Infrastructure

| Status | Feature / owner | Source | Coverage / issue / next action |
| --- | --- | --- | --- |
| [x] | FastAPI — D1 | `backend/app/main.py` | Health/readiness, backend suite and live startup. |
| [x] | React/TypeScript — D1/D2 | `frontend/` | ESLint, TypeScript, Vitest, production build and browser tests. |
| [x] | PostgreSQL/migrations — D1/D2/INT | Alembic revisions | Merge revision joins commerce and review-audit heads without rewriting history; fresh/upgrade/drift validation. |
| [x] | Redis/background jobs — D1/INT | RQ/worker/Compose | Linux Compose live smoke; bounded worker timeout and idle health heartbeat. |
| [x] | Configured local/private storage — D1 | `common/storage.py`, MinIO | Path safety/signatures/real MinIO smoke. R2 uses the S3 adapter but no real R2 account was tested. |
| [x] | Docker Compose — D1/D2/INT | `compose.yaml` | Exact PR head passed GitHub Linux `docker compose config`, build/wait, PostgreSQL/Redis/RQ/MinIO generation/publication smoke, commerce smoke and Playwright. Local Windows remains blocked by missing WSL/daemon/plugin. |
| [x] | Environment configuration — D1/D2/INT | config, `.env.example`, Compose | Production/hosted-provider/optional-model guard tests; credentials kept server-side. |
| [x] | Automated tests — D1/D2/INT | backend tests, frontend tests/e2e, CI | See exact commands and final counts in `AYNA_TEST_REPORT.md`. |
| [x] | API documentation — D1/INT | schemas/OpenAPI/TS types | Generated artifacts, route uniqueness and schema drift checks; additive contract changes documented. |
| [x] | Security/uploads — D1/D2/INT | auth, storage, image sanitation, Meshy boundary | Cookie/CSRF/ownership/upload/signature/SSRF/size/replay tests; deployment still needs HTTPS/private secrets. |
| [x] | Installation instructions — D1/D2/INT | README, both-PC guide | Fresh pinned backend/frontend installs and baseline checks; optional GPU instructions not claimed executed on a second PC. |

## F. Virtual try-on

| Status | Feature / owner | Source | Coverage / issue / next action |
| --- | --- | --- | --- |
| [~] | Functioning virtual try-on — D2 | `modules/tryon/`, `TryOnPanel.tsx` | Functional private diagnostic workflow: consent, authenticated upload, async state, retention/deletion, unsupported-input/failure tests. It produces no synthetic result because no approved real model/provider is configured; sizing/fit remain unverified. |
| [x] | Selfie requirements documented — INT | `AYNA_BOTH_PC_TESTING.md` | Documentation review only; planned consented selfie/upper-body clothing path, no functional inference claim. |
| [x] | Full-body requirements documented — INT | `AYNA_BOTH_PC_TESTING.md` | Documentation review only; planned clothing/shoe placement, pose/occlusion/fallback/deletion rules. Other categories remain ordinary commerce. |

## G. Preserved commerce functionality

| Status | Feature / owner | Source | Coverage / issue / next action |
| --- | --- | --- | --- |
| [x] | Guest bag/account merge — D1 | commerce orders, identity, `Checkout.tsx` | Commerce API and registered-checkout browser tests. |
| [x] | BDT/COD checkout — D1 | commerce orders/service | Server totals, idempotency, two-buyer last-unit race, COD browser orders. Live cards need merchant setup. |
| [x] | Shipping/tax/coupons — D1 | commerce service/admin | Discount/limits/settings tests and browser coupon journey; jurisdiction tax automation is not supplied. |
| [x] | Orders/tracking/receipts — D1 | `Orders.tsx`, seller routes | Private order, item ownership and sequential delivery tests; tracking entered by staff, no carrier API. |
| [x] | Cancel/return/COD collection — D1 | commerce orders/admin | Restock-once and return/COD tests; partial-item returns and bank reconciliation remain extensions. |
| [x] | Wishlist/compare/recent — D1 | commerce catalog, Discovery/local state | Wishlist API/browser and comparison/recent browser checks; comparison/recent state is browser-local. |
| [x] | Verified reviews/moderation — D1 | commerce catalog/admin | Delivered-purchase review tests and customer browser review journey. |
| [x] | Support/notifications/admin — D1 | commerce admin/Account/Admin | Ticket ownership/reply/notifications/settings tests and seller/admin browser journey; SMTP delivery not configured. |

## Priorities

1. Authorized, single-product hosted smoke with a strict request cap; record real output
   against every reference photo before describing fidelity as verified.
2. Calibrated camera/reference alignment and texture-aware render validation; logo/detail
   review must remain human-led until measured on representative products.
3. Install Blender, run the real bpy path on textured provider GLBs, and retain visual
   pre/post evidence before enabling optimization.
4. Select and legally approve a real clothing/shoe try-on model or provider, then test
   pose, feet/body visibility, occlusion, privacy and representative outputs.
5. Run Tripo/Meshy only with an explicit one-request budget and compare actual results;
   keep mock/photo fallback explicit and never retry an ambiguous paid submission.
