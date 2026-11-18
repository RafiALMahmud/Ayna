# Ayna

A multi-category e-commerce platform with optional 3D product previews and local AI work. Experimental virtual try-on and additional 3D/AI workflows are documented on the [`feat/local-ai-completion` branch](https://github.com/RafiALMahmud/Ayna/tree/feat/local-ai-completion); those features are not part of `main` yet.

**Stack:** React, TypeScript, Tailwind, FastAPI, SQLAlchemy/Alembic, PostgreSQL, Redis/RQ, and private MinIO storage.

**Demo:** Local setup instructions are below. <!-- TODO: add an approved public screenshot or demo URL. -->

## What I built

I built the regular shopping, checkout, seller, and admin workflows. I also developed local AI, virtual try-on, and 3D experiments on the feature branch; try-on is a generated appearance preview and does not predict sizing or physical fit.

## Run locally

Use Python 3.12 and Node 22.21 or newer; follow the Windows instructions below.
## Shop functionality

- Search, categories, filters, sorting, pagination, product photos, stock and size/color options.
- Guest shopping bag, account cart merge, wishlist, comparison and recently viewed products.
- Customer registration, cookie sessions, profile/password management, recovery and saved addresses.
- BDT checkout with server-calculated totals, coupons, delivery charges and cash on delivery.
- Private order history, receipts, fulfillment tracking, cancellation and return requests.
- Verified-purchase reviews, notifications and customer support tickets.
- Seller photo listings, SKUs, option inventory, sales totals and fulfillment.
- Administrator reporting, users/roles, listings, orders, returns, coupons, categories,
  review moderation, support replies and delivery/tax settings.
- Optional Stripe hosted checkout/webhooks/refunds and SMTP password recovery adapters.

Products can be sold without generating a 3D model. The separate product studio retains
its reviewed, explicitly labeled **dummy GLB** workflow. Hosted reconstruction has an
explicitly enabled Meshy adapter, tested with simulated HTTP responses but not a paid
live task. Photorealistic accuracy is unverified. Clothing/shoe try-on remains
unimplemented; the mock provider never reconstructs the uploaded product.

Integration audit and operating instructions:
[feature checklist](AYNA_FEATURE_CHECKLIST.md), [integration report](AYNA_INTEGRATION_REPORT.md),
[executed test report](AYNA_TEST_REPORT.md), [both-PC instructions](AYNA_BOTH_PC_TESTING.md).
The integrated branch preserves the regular shop and Developer 2's quality/viewer work.

## Run locally on Windows

Use Python 3.12 and Node 22.21 or newer. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock
npm.cmd --prefix frontend ci
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-local.ps1
```

Shop: **http://localhost:5175**. API explorer: **http://localhost:8002/docs**.
The helper migrates and seeds a separate SQLite database, builds the web app, then runs
both servers in the background. Logs and process records are in `.data/`; local database
and assets are in `backend/.data/`. Closing the terminal leaves the servers running.
Choose alternate ports with `-ApiPort 8003 -WebPort 5176`. The helper refuses occupied ports.
Use `-NoSeed` on later starts to skip sample catalog setup.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop-local.ps1
```

This stops only the recorded Ayna processes and preserves data. Restart after source changes.
Native mode uses SQLite, local files and inline mock jobs; Docker uses PostgreSQL,
Redis workers and MinIO. These modes have separate data.

## Sample accounts

| Role | Email | Password |
| --- | --- | --- |
| Customer | shopper@ayna.local | AynaDemo!2026 |
| Seller | seller@ayna.local | AynaDemo!2026 |
| Administrator | admin@ayna.local | AynaDemo!2026 |

These public credentials are development fixtures. The seed script refuses production.
It adds eight photographed products and `WELCOME10` (10% off, minimum BDT 1,000).
It does not replenish stock or reset existing passwords when rerun. The development
payment simulator is labeled in the UI; COD does not require payment credentials.
Browser tests create additional labeled fixtures and orders in the local database.

## Docker / PostgreSQL

Start Docker Desktop with Linux containers; `docker info` must succeed.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose config --quiet
docker compose up --build -d --wait --wait-timeout 240
docker compose exec -T api python -m scripts.seed_shop
docker compose ps
```

Defaults: web http://localhost:5173, API http://localhost:8000/docs, private MinIO
console http://localhost:9001. Set `API_PORT`, `WEB_PORT`, `VITE_API_BASE_URL`,
`STOREFRONT_URL`, and `CORS_ORIGINS` together when changing ports. An existing ignored
`.env` can override these defaults. Stop native servers first if reusing their ports.
`docker compose down` retains volumes. Initial image builds need internet.

## Verification

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m ruff format --check .
..\.venv\Scripts\python.exe -m mypy app
cd ..\frontend
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run test -- --run
npm.cmd run build
npx.cmd playwright install chromium
$env:PLAYWRIGHT_BASE_URL='http://localhost:5175'
$env:E2E_API_URL='http://localhost:8002'
npm.cmd run test:e2e
```

Live transaction smoke, with the native server running:

```powershell
cd backend
$env:SMOKE_API_URL='http://localhost:8002'
$env:STOREFRONT_URL='http://localhost:5175'
..\.venv\Scripts\python.exe -m scripts.commerce_smoke
```

CI runs backend and frontend checks, migration/API schema drift checks and the full
PostgreSQL/Redis/MinIO mock workflow plus desktop/mobile browser journeys. See
[commerce implementation notes](docs/COMMERCE.md) and [executed checks](docs/COMMERCE_TEST_RESULTS.md).
The original kit and [bootstrap readme](docs/BOOTSTRAP_README.md) describe the earlier
3D-only foundation; the user's subsequent request expanded the application to commerce.

## Deployment configuration

Production requires HTTPS with same-site web/API domains, restricted CORS, private
storage, real secrets, `ENVIRONMENT=production`, `DEV_AUTH_ENABLED=false`,
`DEMO_PAYMENTS_ENABLED=false`, and RQ workers. Use an empty production database;
never expose the seeded development database. Cookie sessions provide real role checks;
the legacy seller-ID header is only a development studio shortcut.

COD is the default. Real card settlement needs an eligible Stripe merchant account,
both Stripe secrets and a reachable signed webhook; it has not been exercised with
live money. Password recovery needs SMTP in production. Courier updates and COD
collection are recorded by staff; there is no carrier or banking integration.
Store policies/contact details are editable development examples and need merchant review.
Photo credits and demo brand disclosures: [DEMO_PHOTOS.md](docs/DEMO_PHOTOS.md).

## Integrated quality and viewer

Developer 2 adds private CPU GLB inspection renders, advisory aligned-view quality checks,
append-only seller review history, accessible rotate/zoom/pan controls and photograph fallback.
Optional SAM 2/DINOv2 run only with explicitly supplied local models. See
[quality implementation](docs/DEV2_QUALITY_STOREFRONT.md). Mock geometry remains unrelated
to the product and is never given a fabricated fidelity score.
