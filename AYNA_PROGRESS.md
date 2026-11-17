# Ayna completion progress — 8 November 2026

## Long-sleeve exposed-skin recovery - 16 November 2026

- Added opt-in private intermediate capture and proved that segmentation-free conditioning,
  rather than parser or mask coverage, caused the dark exposed arms.
- Added default-on sleeve-aware recovery with a real persisted 90% stage and bounded timing,
  sleeve-case and Lab diagnostics. Non-applicable transitions skip the second pass.
- Added five sleeve-mask unit cases, an opt-in RTX integration test and
  `scripts/compare_tryon.py` for private baseline/fixed proof.
- Final Lab delta improved from 27.2705 to 3.0830 with 0.0 outside-mask L1. Exact final CUDA
  integration passed in 150.04 s; measured PyTorch peak remained 3,727.79 MiB.
- Validation passed: backend 110/2 skipped plus a separate live GPU pass; frontend 20 tests,
  generated types, lint, typecheck and build. No orphan process or temp directory remained.
- Step 1 was committed and pushed as `1dff007`. Steps 2-4 remain uncommitted for review, following
  the instruction to stop after Step 4.

## Windows FASHN reliability milestone - 9 November 2026

- Diagnosed job `ae553b3d-68d7-4047-8a24-c89937d20e89`: its real timeout was masked by a
  Windows cleanup `PermissionError` after only the launcher was killed.
- Added truthful persisted stage progress, bounded private failure logs, complete Windows process
  tree termination, exact timeout/cancellation/output errors and validated PNG output.
- Pinned incompatible ONNX Runtime CUDA 13 pose sessions to a four-thread CPU provider while
  preserving PyTorch CUDA 12.8 bf16 synthesis on the RTX 4050.
- Serialized GPU jobs, kept failed uploads, added refresh recovery and clear stage/timeout UI, and
  removed the possibility of literal `&#x20;` button text.
- Re-ran the exact unchanged pair successfully on final code in 184.237 seconds. No orphan FASHN
  process or temp directory remained; Ollama was CPU-only and unloaded.
- Automated validation: backend 105 passed/1 skipped plus Ruff/MyPy/Alembic; frontend lint,
  typecheck, 17 tests and production build all passed.

## Completed and tested

- Fetched all remotes and verified `feat/local-ai-completion` is ahead of, not behind, both
  developer histories. No user work was discarded and no unresolved conflict remains.
- Reproduced the live try-on upload stall. The FASHN subprocess filled an unread Windows pipe;
  inference now logs to a bounded job file and native uploads return immediately while one GPU
  thread processes the persisted job.
- Reprocessed private job `8ade2beb-c5e6-4517-96b9-34241ca822b3` successfully with genuine
  FASHN VTON inference: 92.275 seconds, CUDA device 0, 3,727.79 MiB peak PyTorch allocation.
- Installed official Ollama 0.40.15, pulled `qwen3:0.6b` and
  `qwen3-embedding:0.6b`, verified coherent generation and a 1,024-dimensional embedding.
- Restarted Ollama as localhost-only, one-model/one-request, 4K-context CPU inference. `ollama ps`
  reported `100% CPU`; no Ollama compute process appeared on the NVIDIA GPU.
- Added a LangChain/Ollama product assistant with parameterized live catalog filtering,
  incremental local embeddings, untrusted-description isolation, Bangla numeral/term handling,
  structured product cards, and a deterministic unavailable-model fallback.
- Added the React chat widget and upgraded try-on UI with progress, before/after comparison,
  retry, authenticated download, deletion, and accurate unavailable/failure states.
- Paid Meshy/Tripo selection now fails closed unless a separate explicit override is supplied;
  the provided demo environment keeps that override false.
- Frontend: 15/15 tests passed and production build passed. RAG backend: 3/3 tests passed.

## Remaining validation

- Execute a second new garment/person pair and obtain human acceptance. The current user result
  is technically valid but has visible hand/arm artifacts, so visual-quality acceptance is open.
- Test a physical Intel Iris Xe laptop over a trusted LAN. That device is not accessible here.
- Push the final commit and wait for required GitHub checks/review. Do not merge before review.

Final automated validation is complete: 98 backend tests passed with 1 intentional optional
OpenCV skip; Ruff, format, MyPy, Alembic current/check, OpenAPI generation, frontend lint,
typecheck, 15 component tests, and production build passed. Live English, semantic, and Bangla
requests were repeated; the Bangla no-result is correct because the demo catalog has no black shirt.

## Current blockers

- FASHN's required NVIDIA-derived human parser is noncommercial; this path is demo/research only.
- No verified shoe-on-feet model is available for this 6 GB profile.
- Cross-device validation and a second human-reviewed pair require external input/hardware.

## Files changed in this milestone

Try-on backend/tests and UI; RAG backend/tests/widget; configuration and dependency lock;
Windows Ollama/start/test scripts; required audit, performance, setup, license, and test documents.
