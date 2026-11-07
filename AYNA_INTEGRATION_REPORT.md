# Ayna integration report — 7 November 2026

## Local AI completion addendum

`local_triposr` is additive and does not replace ordinary commerce or mock mode. It uses
explicit external Python/source/weight paths, forces offline inference, runs one disposable
subprocess per task, consumes only the front/first seller image and stores a validated private
GLB. Seller review remains mandatory. Queue depth, timeout, cancellation and recurring
recovery/retention maintenance are enforced; late try-on results cannot recreate deleted assets.

The CPU inspection renderer now handles embedded base-color textures and vertex colors with
explicit limitations. A real Blender 5.2.3 run demonstrated the acceptance gate rejecting a
larger output that lost one texture/image. No paid provider is enabled by the free profile.

Optional FASHN VTON generated a real offline clothing preview on the RTX 4050 in 93.942 seconds
with 3,727.79 MiB peak PyTorch CUDA allocation. It is guarded as demo-only because its required
human-parser dependency inherits noncommercial NVIDIA terms. No suitable permissive local
shoe-on-feet model was verified, so shoes fail clearly instead of returning a fake result.

## Current completion branch synchronization

- [x] Preserved the existing `D:\PROJECTS\Ayna` worktree on `feat/quality-storefront`
  at `1190fd6`; it was clean and was not switched or rewritten.
- [x] Verified primary `https://github.com/RafiALMahmud/Ayna.git` and fork
  `https://github.com/7illz/Ayna.git`, fetched both, and confirmed primary `main` at
  `bf9e16c` already contains the earlier Developer 2 head.
- [x] Created separate worktree `D:\PROJECTS\Ayna-complete` and branch
  `feat/complete-remaining-features` directly from current primary `main`.
- [x] No merge, force-push, paid provider call or volume deletion was performed.

## Phase 1 — synchronization and provenance

- [x] Verified remote: `https://github.com/RafiALMahmud/Ayna.git`.
- [x] Executed `git fetch --all --prune`; origin contains `main` (`deab6cc`),
  `chore/bootstrap` (`f42bf5a`), `feat/commerce-platform` (`400c30b`).
- [x] Checked every origin branch, remote PR head, all PRs, tags and direct forks.
  Origin has PRs #1/#2 and no Developer 2 branch/PR. The direct fork `7illz/Ayna`
  contains `feat/quality-storefront` (`1190fd6`), including `a56edc4`, `ba710bf`.
- [x] Fetched that actual branch as `dev2/feat/quality-storefront`, inspected its
  diff against the common `f42bf5a` base and preserved its commits via a merge.
- [x] Created `integration/ayna-full-system` from latest `origin/main` in the separate
  worktree `E:\Ayna-integration`. Merged bootstrap, commerce, then Developer 2.
- [x] Resolved conflicts in README, backend configuration, public catalog and Compose.
  Retained commerce/auth and D2 quality flags, successful-current-model guards and viewer.
- [x] Preserved the original worktree's uncommitted `04_GITHUB_AND_TESTING.md` edit;
  it was never stashed, discarded, staged or included in integration commits.

Developer 1's expected `feat/seller-generation` branch was never pushed. Actual D1
contributions are the shared stack, seller upload/mock generation/private storage and the
regular commerce platform from the bootstrap/commerce commits. Developer 2 supplied
quality analysis/rendering, optional local-only vision loaders, audit records, viewer
controls/lazy loading and associated tests/docs from the discovered fork. Historical
commits are preserved, not squashed into falsely attributed replacement code.

## Phase 2 — source audit

- [x] Read the original kit, D2's retrieved `03_CODEX_DEV2.md`, shared contracts,
  implementation reports and current source. Historical reports remain attributed
  evidence, not new execution claims.
- [x] Re-audited `AYNA_FEATURE_CHECKLIST.md`: **59 items; 50 complete, 9 partial,
  0 missing, 0 known broken**. Partial means an implemented boundary still lacks live
  provider/tool/model acceptance; it is not relabeled complete.
- [x] Preserved the user's regular-commerce scope: 3D is optional; clothing/shoe try-on
  is a distinct future project, not the definition of the whole store.

## Phase 3 — compatibility repairs

- [x] Joined independent commerce and review-audit migration heads with the additive
  `e90d9ea58b33` merge revision; existing revision IDs/down-revisions are unchanged.
- [x] Combined publication guards: approval + latest successful model + not archived +
  ordinary listing status (where commerce SKU exists) + active seller. Normal photo-only
  product sales do not require 3D approval.
- [x] Preserved API UUIDs/status enums/storage conventions and generated TS contracts.
- [x] Exposed D2's previously stored-but-inaccessible inspection renders through
  expiring owner-signed image routes and the seller UI. Private keys stay server-side.
- [x] Restored explicit dummy labels in the enhanced viewer while supporting hosted
  disclosures; label ordinary hosted results as estimated previews, never scans.
- [x] Made studio creation work with authenticated seller cookies when development
  header auth is disabled. Provider UI/cost labels follow actual configuration.
- [x] Bounded repeated review-note updates to the database column while retaining every
  full approve/reject note in the append-only audit table.
- [x] Added owner-scoped photograph direction/order edits with front-first validation,
  active-job protection and publication revocation on changed references.
- [x] Normalized viewer model bounds to keep different provider scales within camera view.
- [x] Serialized studio status polls and ignored stale job/quality responses after product
  selection changes; retained actual rotate/zoom pixel assertions with bounded graphics waits.
- [x] Resolved a delayed-login redirect race: refresh the merged cart before publishing
  signed-in navigation, then redirect immediately. Slow cart loads cannot undo seller navigation.
- [x] Enabled CI for integration branches and retained all commerce/browser workflows.

## Phase 4 — critical missing generation path

- [x] Implemented the required opt-in Meshy multi-image HTTP adapter against the
  [official current API](https://docs.meshy.ai/en/api/multi-image-to-3d).
- [x] Explicit key + positive rolling-24-hour server request cap + RQ requirement;
  per-seller cap; transactional cross-instance quota serialization; idempotent replay.
- [x] Front first; at most four selected views from all stored inputs. No paid submission
  retries, automatic paid-provider fallback or live provider calls in tests.
- [x] Provider task ID persisted as soon as available; bounded polling/progress/timeouts,
  controlled error codes, model existence checks, streamed size limits and embedded GLB
  validation. Asset downloads allow only HTTPS `assets.meshy.ai`, no redirects and no
  API credentials forwarded to storage. No external GLB buffer/image URI is accepted.
- [x] Wired successful hosted GLB storage into D2's isolated quality service. No reference
  alignment is invented: hosted reports remain unknown pending defensible correspondence.
- [~] Meshy HTTP contract is tested with a simulated provider; an authorized real
  product/paid account fidelity assessment remains required.
- [x] Real official SAM 2.1 Hiera Tiny and DINOv2 Small local-weight inference ran on the
  RTX 4050; measured device, latency and peak allocation are in `AYNA_TEST_REPORT.md`.
- [~] Hosted Tripo v3, Blender optimization, OpenCV alignment and try-on remain bounded partials.
  Local TripoSR and FASHN synthesis both ran offline; TripoSR geometry failed human acceptance,
  Blender's real output failed texture/size acceptance, OpenCV lacks a representative calibrated
  dataset, and FASHN's parser license blocks commercial use.

## Phase 5 — remaining-feature implementation

- [x] Added Tripo v3 multipart upload, named multiview submission, bounded task polling,
  strict CDN download and embedded GLB validation. Only an explicitly selected provider
  is used; ambiguous submission is never retried and no paid call ran.
- [x] Added generation heartbeats plus idempotent stale-job recovery. Mock/never-submitted
  jobs requeue; known hosted IDs resume polling without POST; unknown in-flight paid jobs
  fail `AMBIGUOUS_PROVIDER_SUBMISSION` rather than risk another charge.
- [x] Added opt-in ORB/RANSAC alignment gates. Same direction labels alone now produce
  `not_evaluated`; metrics exist only after correspondence evidence. Localized differences
  are human inspection cues, not logo/text recognition.
- [~] Added isolated optional Blender decimation with timeout and strict pre/post size,
  geometry, bounds, material/texture/UV and rendered-appearance gates. Blender 5.2.3 ran on a
  textured GLB; the candidate failed acceptance and the original was preserved.
- [~] Added clothing/shoe private jobs and UI: authenticated consent, sanitation, framing,
  async state, owner-only generated results, recurring 24-hour retention and deletion. FASHN
  clothing inference ran offline; its noncommercial parser blocks commercial acceptance and
  shoes remain explicitly unsupported. Results never claim sizing or fit.
- [x] Added reversible `24df91a0bc72` migration, regenerated OpenAPI then TypeScript types,
  and retained ordinary catalog, checkout, seller, admin, orders and 3D behavior.

## Phase 6 — execution evidence

Exact commands, final test counts, earlier failures/fixes and unexecuted GPU/paid tests
are recorded in `AYNA_TEST_REPORT.md`. Original and commerce tests remain enabled.
Desktop/mobile browser checks include actual canvas changes after rotate/zoom, inspection
renders, photo fallback and shopping/seller/admin flows.

## Docker host repair during integration

The user's startup error was local Docker Desktop storage configuration, not GitHub.
`%LOCALAPPDATA%\Docker\wsl\disk` was a junction to the missing directory
`D:\bari\.docker-data\disk`. The D: volume existed, but that target and its parent did not.
Recreated only the missing target directory. Normal Desktop shutdown timed out, so used
the supported `docker desktop stop --force --timeout 20` and relaunched Desktop hidden.
`docker info` then returned **29.1.3** and Desktop status became `running`.

Docker initialized a new `docker_data.vhdx` at that target. No old VHD, WSL distribution,
volume or database was deleted. This repairs engine startup; it does not recover a
previously moved/deleted data disk. Original native Ayna data remains separate. Container
validation uses project `ayna-integration` with separate volumes and ports 8004/5177.

Reference: [Docker's WSL storage documentation](https://docs.docker.com/desktop/features/wsl/).

## Phase 6 — GitHub delivery

Integration is pushed as [PR #3](https://github.com/RafiALMahmud/Ayna/pull/3) targeting `main`.
Local final results: 70 backend tests, 12 frontend tests, 6 native browser journeys and
6 container browser journeys passed, along with both live storage/queue/commerce smokes.
Merge is permitted by the user's current
request, superseding historical kit instructions that prohibited automatic merge. Merge
is performed only against the reviewed head SHA after required checks succeed and without
bypassing branch protection. Final PR/SHA/status is reported in the completion message;
this document records the tested implementation rather than guessing a future merge SHA.

## Phase 7 — both-PC instructions

- [x] `AYNA_BOTH_PC_TESTING.md` contains CPU/native/Compose checks, explicitly capped
  hosted testing, CUDA diagnostics and separate real local-weight inference commands.
- [x] Records which commands require external packages/weights/merchant authorization.
- [x] Documents planned consented selfie/full-body clothing/shoe try-on requirements.
- [ ] Both humans still need to execute and record acceptance on their own physical PCs.

Remaining priorities: authorized hosted fidelity smoke; calibrated texture-aware comparison;
actual RTX Small-model inference; stale-job/provider reconciliation; optional optimization
and try-on. Live payment, mail and courier production setup also remain merchant tasks.
