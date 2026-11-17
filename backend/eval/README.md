# Ayna private try-on evaluation

Every person and garment image must be authorized for this local evaluation. Each manifest row
requires `"consent": true`; the loader refuses a missing or false flag. Real manifests contain
50–100 cases and cover `long-to-short`, `bare-arm`, and `non-tee` transitions. Store all images and
outputs below the Git-ignored `.data/` tree—never in this directory.

`manifest.synthetic.json` demonstrates the format with generated placeholder paths. The unit
tests create those pixels at runtime. `ab.html` is an offline randomized preference page and
exports votes as JSON. No browser request or remote analytics are used.

`manifest.template.json` contains 50 placeholder rows with consent deliberately set to false.
Replace the paths and set a row true only after recording authorization; otherwise the runner
refuses it. Add `--generate --python <FASHN-venv-python> --runner <local_fashn_vton.py>
--weights <local-weights>` to generate each named configuration sequentially before scoring.
