# Local model benchmark

| Candidate | Actual status | Peak VRAM | Time | Quality / decision |
| --- | --- | ---: | ---: | --- |
| Existing diagnostic | Tested | 0 | sub-second | Framing/privacy only; never represented as try-on. |
| FASHN VTON v1.5 | Two offline RTX executions; latest user pair completed | 3,727.79 MiB PyTorch; about 5.84 GiB total observed | 92.275 s latest; 93.942 s earlier | Best practical genuine pipeline on this laptop. Plausible garment, identity/background mostly retained; latest hands/arms need review. Selected for demo only. |
| CatVTON | License/hardware review only | Not run | Not run | Standard profile is unsuitable for a stable 6 GB Windows demo; installing another large stack was not justified after FASHN passed. CC BY-NC-SA also restricts use. |

Selected profile: FASHN VTON v1.5, bf16 main synthesis, batch one, one GPU job at a time,
external pinned weights, offline Hugging Face/Transformers flags, 900-second bound. Ayna does not
silently lower quality after arbitrary failures and never substitutes an image overlay.

Acceptance remains category- and image-specific. The model does not prove physical size or fit,
can alter hands/arms and fine patterns, and has not passed shoe, selfie-only, or all-body-style tests.
