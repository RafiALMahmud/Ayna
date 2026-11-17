# Model licenses and usage boundary

This is a technical inventory, not legal advice. Preserve upstream license/notice files and obtain
legal review before any commercial launch.

| Model | Source / revision | Recorded terms | Ayna decision |
| --- | --- | --- | --- |
| FASHN VTON v1.5 | `fashn-AI/fashn-vton-1.5` code `7c0f10a`; weights `7720683` | Main code/weights Apache-2.0. Required `fashn-human-parser` inherits NVIDIA noncommercial terms. | Research/demo only; explicit acknowledgement required. |
| DWPose / YOLOX | FASHN DWPose `548b5df` | Apache-2.0 | Demo dependency; notices retained. |
| TripoSR / DINO encoder | TripoSR `107cefd`, weights `5b52193`; DINO config `f205d5d` | MIT/Apache-2.0 as recorded by upstream cards. | Local 3D demo; output still requires seller review. |
| SAM 2.1 Tiny | Official Meta checkpoint | Apache-2.0 | Advisory foreground checks only. |
| DINOv2 Small | `facebook/dinov2-small@ed25f3a` | Apache-2.0 | Advisory similarity only. |
| Qwen3 0.6B | Ollama `qwen3:0.6b`, manifest/model ID `7df6b6e09427`; upstream Qwen card | Apache-2.0 weights | Local grounded text generation. |
| Qwen3 Embedding 0.6B | Ollama `qwen3-embedding:0.6b`, ID `ac6da0dfba84`; upstream Qwen card | Apache-2.0 weights | Local 1,024-dimensional product embeddings. |

Qwen embedding training documentation lists multiple public datasets, including MS MARCO.
The Apache weight license does not automatically resolve every underlying dataset's reuse terms;
this unresolved provenance question is recorded for legal review. Current use is a local research
demo. Sources: official Qwen Hugging Face model cards, Ollama library manifests, FASHN repository,
and the detailed hash inventory in `docs/MODEL_LICENSE_INVENTORY.md`.

Paid OpenAI, Gemini, FASHN API, Meshy, Tripo, and cloud-GPU inference are not required or called.
The demo config sets `ALLOW_PAID_AI_PROVIDERS=false`; selecting Meshy/Tripo then fails at startup.
