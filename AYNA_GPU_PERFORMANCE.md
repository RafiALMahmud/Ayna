# RTX 4050 and host performance

## Sleeve skin-recovery follow-up - 16 November 2026

The authorized comparison ran locally on the RTX 4050. The deterministic baseline completed in
79.566 s and the two-pass recovery path in 148.241 s before the final CPU-only chroma adjustment.
The exact final opt-in CUDA test passed in 150.04 s including pytest/subprocess overhead, versus
the historical 184.237 s reference. The last measured PyTorch peak was **3,727.79 MiB**; no GPU
allocation code changed after it. No FASHN child or temporary directory remained.

SAM 2 remains `skipped_vram_budget`: this profile previously measured 5,818/6,141 MiB total VRAM,
so another model would violate headroom. The existing parser is unchanged; no model or CUDA
package was added.

## CUDA environment isolation follow-up - 16 November 2026

`start-ollama.ps1` now applies `CUDA_VISIBLE_DEVICES=-1` only to the spawned Ollama server and
restores the parent process environment before Ayna starts. A new private job submitted through
the running HTTP API after `start-local.ps1 -EnableFashn` persisted
`cuda_available=true`, `synthesis_device="cuda"` and
`cuda_device="NVIDIA GeForce RTX 4050 Laptop GPU"`. This proves the API-launched worker, rather
than only a manually launched worker, can see CUDA.

The authorized 683 x 911 / 900 x 900 pair completed in **111.742 seconds**. CUDA synthesis
completed at 111.425 s; PyTorch peak allocation was 3,727.79 MiB. External sampling during
synthesis measured **5,818/6,141 MiB** total VRAM, 100% utilization and 70.95 W. The output was a
valid 576 x 769 PNG. The source SHA-256 remained unchanged. After completion there was no FASHN
Python child, no `ayna-fashn-*` temporary directory and no loaded Ollama model.

The result card now renders a device line from persisted diagnostics. It names the RTX device only
when `synthesis_device` is exactly `cuda`; CPU and unknown-device states cannot claim RTX.

## Final timeout-repair run - 9 November 2026

The original failed pair completed on final code in 184.237 seconds. Startup/imports completed at
27.445 s and bounded CPU preprocessing completed at 46.914 s; CUDA synthesis completed at
183.915 s. PyTorch reported 3,727.79 MiB peak CUDA allocation. External `nvidia-smi` sampling
observed 98-100% utilization and approximately 5.76-5.78/6.14 GB total VRAM during synthesis.

PyTorch 2.11.0+cu128 uses the RTX 4050 on CUDA 12.8. ONNX Runtime GPU 1.31.1 requires CUDA 13 and
could not load `cublasLt64_13.dll`, so pose inference is deliberately pinned to a bounded CPU
session rather than relying on an implicit provider fallback. No CUDA packages were changed.
Ollama 0.40.15 remains CPU-only, one request/model at a time, and is explicitly unloaded after its
CPU-placement preflight and before FASHN work. Post-run `ollama ps` was empty.

Host measured 8 November 2026:

- AMD Ryzen 5 7535HS: 6 physical / 12 logical cores.
- 16,333,209,600 bytes physical RAM (about 15.2 GiB usable).
- NVIDIA GeForce RTX 4050 Laptop GPU: 6,141 MiB VRAM, driver 616.92.
- User confirmed AC charger and ASUS Turbo mode. Safeguards were not disabled.

Latest real FASHN run: 92.275 seconds, one CUDA job, 3,727.79 MiB peak PyTorch allocation,
approximately 5.84/6.14 GB observed total GPU memory, 100% utilization, about 2.58 GHz and 70 W at
the observed inference point. The earlier accepted execution measured 93.942 seconds and the same
3,727.79 MiB PyTorch peak. GPU work is serialized.

Ollama is intentionally CPU-only: `CUDA_VISIBLE_DEVICES=-1`, `OLLAMA_LLM_LIBRARY=cpu_avx2`, one
parallel request, one loaded model, 4,096-token context. `ollama ps` reported `100% CPU`; NVIDIA
process accounting showed no Ollama allocation. This prevents chatbot traffic from evicting FASHN.

The currently verified profile is the conservative performance profile. A higher-resolution
"quality mode" is not exposed because it has not passed repeated 6 GB runs. CUDA OOM and timeout
are bounded failures; Ayna does not loop indefinitely or report corrupted output as success.

## 17 November 2026 original-resolution preservation run

The authorized long-sleeve-to-short-sleeve white-tee pair completed on the native RTX 4050 in
**164.441 seconds**, versus the earlier 184.237-second reference run. CUDA synthesis completed at
162.928 seconds and reported **3,727.79 MiB** peak PyTorch CUDA allocation on `cuda:0`; output
parsing used CPU. The conditional preservation/recovery composite took **0.135 seconds** and the
result retained the source resolution of **683 x 911**. The run left no `ayna-tryon-*` temporary
directory. Process command-line inspection was denied by Windows CIM permissions, so the shell
could not independently enumerate command lines; the launched child itself exited with code 0.
