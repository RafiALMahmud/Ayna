# Local model and license inventory

Verified 7 November 2026 from the official repositories/model cards. Model files live outside
Git and are never downloaded at application startup. A legal professional should review terms
before a commercial launch; this inventory records technical findings, not legal advice.

| Model / task | Exact source revision | Code / weight terms | Commercial-use finding | Hardware and observed status |
| --- | --- | --- | --- | --- |
| TripoSR, single-image product-to-3D | Code `VAST-AI-Research/TripoSR@107cefdc244c39106fa830359024f6a2f1c78871`; weights `stabilityai/TripoSR@5b521936b01fbe1890f6f9baed0254ab6351c04a`, SHA-256 `429E2C6B22A0923967459DE24D67F05962B235F79CDE6B032AA7ED2FFCD970EE`; encoder config `facebook/dino-vitb16@f205d5d8e640a89a2b8ef0369670dfc37cc07fc2` | MIT code and pretrained model; DINO is Apache-2.0. Preserve notices. Model card records a curated CC-BY Objaverse training subset. | Permissive for the intended commercial path, subject to ordinary input/output rights and attribution diligence. | Official default is about 6 GB VRAM. Ayna uses one isolated GPU subprocess and CPU scikit-image surface extraction on Windows. Measured 10.31 s / 1,867.54 MiB peak at 128³; output quality still requires seller rejection/approval. |
| FASHN VTON v1.5, tops/bottoms/one-pieces | Code `fashn-AI/fashn-vton-1.5@7c0f10af3f91ad4048fe9729c470a13ef905d25a`; VTON weights `fashn-AI/fashn-vton-1.5@7720683168567eb5a2a4c67f15116c6e29c83ded`; DWPose `fashn-AI/DWPose@548b5df25b84d9f4aac0611dfa1c2a7a12f15571`; parser `fashn-AI/SegFormer-B4-Clothes@1f80c34dbab321c5730dda5c3fea279fd3e97498` | Main code/weights Apache-2.0; DWPose and YOLOX Apache-2.0. Required `fashn-human-parser` inherits NVIDIA's SegFormer source license, which is noncommercial. Preserve Apache/NVIDIA notices. | **Not approved for Ayna's intended commercial path.** Optional execution requires an explicit demo-only acknowledgement and must not be marketed as commercially usable. | 2.35 GB of model files. Real offline RTX 4050 run: 93.942 s, 3,727.79 MiB peak PyTorch CUDA allocation, 561,264-byte PNG. ONNX pose estimation fell back to CPU because the installed ORT GPU build expected CUDA 13; main bf16 synthesis ran on CUDA. |
| SAM 2.1 Hiera Tiny, foreground advisory | Meta official checkpoint; SHA-256 `7402E0D864FA82708A20FBD15BC84245C2F26DFF0EB43A4B5B93452DEB34BE69` | Apache-2.0 | Compatible for advisory masking with notice retention. | Previously measured on this RTX 4050: 6.905 s, 597.84 MiB peak. This is prior branch evidence, not a reconstruction run. |
| DINOv2 Small, embedding advisory | `facebook/dinov2-small@ed25f3a31f01632728cabb09d1542f84ab7b0056`; safetensors SHA-256 `AE1E99FCEFD534ED978CDEB8326F08030C96E28B7A81FFCBC98A857C84D14BE1` | Apache-2.0 | Compatible for advisory comparison with notice retention. | Previously measured on this RTX 4050: 29.057 s, 104.30 MiB peak; identical-image sanity only. |

## Capability limits

TripoSR conditions on exactly one front/first image. Ayna still requires and privately retains
2–5 seller photographs for human comparison; the unused views do not condition inference.
Unseen surfaces are generated guesses, small text/logos may be wrong, and a result is never a scan.

No permissively licensed, locally runnable, photorealistic **shoe-on-feet** model was verified for
this 6 GB Windows GPU. Shoe generation therefore returns a clear unsupported error. Clothing can
be evaluated with FASHN only under its dependency's noncommercial restriction; selling that path
requires replacing the parser or obtaining separate permission and rerunning acceptance.

Official sources: [TripoSR repository](https://github.com/VAST-AI-Research/TripoSR),
[TripoSR model card](https://huggingface.co/stabilityai/TripoSR),
[FASHN VTON repository](https://github.com/fashn-AI/fashn-vton-1.5), and
[FASHN human parser](https://github.com/fashn-AI/fashn-human-parser).

Measured FASHN file SHA-256 values: VTON `model.safetensors`
`D6CD38286885BC29FA487EA9383F80FFEB95862E7747C630D42C5D3C05BDD35A`; DWPose
`dw-ll_ucoco_384.onnx` `724F4FF2439ED61AFB86FB8A1951EC39C6220682803B4A8BD4F598CD913B1843`;
YOLOX `yolox_l.onnx` `7860AE79DE6C89A3C1EB72AE9A2756C0CCFBE04B7791BB5880AFABD97855A411`;
parser `model.safetensors` `E43C8C8A9B04F28798F0A4630CF18CAA2CDB27A0D454FAE43A5716E6F7078244`.

## Explicit Windows setup

```powershell
git clone https://github.com/VAST-AI-Research/TripoSR.git D:\models\triposr-src
git -C D:\models\triposr-src checkout 107cefdc244c39106fa830359024f6a2f1c78871
python -m venv D:\models\triposr-venv
D:\models\triposr-venv\Scripts\python.exe -m pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu128
D:\models\triposr-venv\Scripts\python.exe -m pip install -r worker\requirements-triposr.txt
$env:HF_HUB_DOWNLOAD_TIMEOUT='600'
D:\models\triposr-venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('stabilityai/TripoSR', revision='5b521936b01fbe1890f6f9baed0254ab6351c04a', local_dir=r'D:\models\triposr-weights', local_dir_use_symlinks=False)"
curl.exe -L --fail -o D:\models\triposr-weights\dino-vitb16-config.json https://huggingface.co/facebook/dino-vitb16/resolve/f205d5d8e640a89a2b8ef0369670dfc37cc07fc2/config.json
```

Set the three `LOCAL_TRIPOSR_*` paths and `AI_PROVIDER=local_triposr` only after setup. Run once
online, then disconnect networking and repeat with `HF_HUB_OFFLINE=1`; Ayna itself forces all
Hugging Face/Transformers offline flags inside inference subprocesses.

FASHN is available strictly for noncommercial demo/evaluation unless its parser licensing is
replaced or separately cleared:

```powershell
git clone https://github.com/fashn-AI/fashn-vton-1.5.git D:\models\fashn-vton-src
git -C D:\models\fashn-vton-src checkout 7c0f10af3f91ad4048fe9729c470a13ef905d25a
python -m venv D:\models\fashn-vton-venv
D:\models\fashn-vton-venv\Scripts\python.exe -m pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu128
D:\models\fashn-vton-venv\Scripts\python.exe -m pip install -r worker\requirements-fashn-vton.txt
D:\models\fashn-vton-venv\Scripts\python.exe -m pip install --no-deps -e D:\models\fashn-vton-src
D:\models\fashn-vton-venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('fashn-AI/fashn-vton-1.5', revision='7720683168567eb5a2a4c67f15116c6e29c83ded', local_dir=r'D:\models\fashn-vton-weights')"
D:\models\fashn-vton-venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('fashn-AI/DWPose', revision='548b5df25b84d9f4aac0611dfa1c2a7a12f15571', local_dir=r'D:\models\fashn-vton-weights\dwpose')"
D:\models\fashn-vton-venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('fashn-AI/SegFormer-B4-Clothes', revision='1f80c34dbab321c5730dda5c3fea279fd3e97498', local_dir=r'D:\models\fashn-vton-weights\parser')"
```

Then configure `TRYON_PROVIDER=fashn_vton`, the three
`TRYON_*` paths, and `TRYON_FASHN_NONCOMMERCIAL_DEPENDENCY_ACKNOWLEDGED=true`. The application
forces local-only inference and never downloads weights at runtime.
