# Try-on blockers

This file records optional or private inputs that are intentionally not downloaded or committed.

## Part A tattoo regression fixture

- Missing item: the authorized bare-arm person photograph and short-sleeve polo garment named in
  the task. No concrete path was supplied and `.data/fixtures/` is absent.
- Required placement: any private paths below `.data/fixtures/`; set
  `AYNA_TRYON_TATTOO_PERSON` and `AYNA_TRYON_TATTOO_GARMENT` to those files.
- Size: user-supplied image files; unknown until supplied.
- License/consent: the operator must have consent and authorization for local evaluation. Images
  remain Git-ignored and must not be committed.
- Effect: the three-seed tattoo diagnosis and opt-in GPU regression cannot run. The test skips
  honestly; the existing authorized long-sleeve-to-short-sleeve pair was used only for the
  measured original-resolution/CUDA check.

## Part B optional learned evaluation metrics

- LPIPS: the `lpips` package and its AlexNet/VGG weights are not installed. Download size and
  transitive model license must be reviewed before installation; no download was attempted.
- KID: an approved Inception or equivalent feature extractor is not installed. KID is selected
  over FID because KID's polynomial-MMD estimator is unbiased at small sample sizes. Exact weight
  size/license depend on the extractor selected by the operator.
- Face identity: no consent-reviewed face-embedding model is installed. The harness reports this
  metric unavailable rather than substituting a misleading pixel metric.
- LS-TON: availability and dataset license for the 770-triplet UR-VTON benchmark must be verified
  by the operator. The dataset must be placed below `.data/fixtures/ls-ton/`; it is never scraped
  or downloaded automatically. Until then its loader remains disabled.

## Part C learned restoration models

No learned restoration checkpoint is installed, so `TRYON_RESTORE` uses only a classical
edge-aware unsharp pass and defaults off. Candidate models require review before any download:
Real-ESRGAN (BSD-3-Clause code; model weights and roughly 64–67 MB checkpoint provenance must be
verified) and SwinIR (Apache-2.0 code; checkpoint size varies by task). Their actual RTX 4050 VRAM
footprints are unmeasured and therefore not claimed. Any future model must load only after FASHN
is unloaded and must remain below the 6 GB limit.
