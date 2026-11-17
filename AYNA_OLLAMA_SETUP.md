# Ollama setup for Ayna

Installed and tested on Windows: official Winget package `Ollama.Ollama`, Ollama 0.40.15.

Models installed outside Git:

```text
qwen3:0.6b              7df6b6e09427   522 MB
qwen3-embedding:0.6b    ac6da0dfba84   639 MB
```

Start and verify the constrained service:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-ollama.ps1 -Restart
ollama ps
```

The script resolves the official executable, stops only processes under that installation root,
binds `127.0.0.1:11434`, disables cloud/GPU use, limits queue/parallelism/context, verifies both
models without downloading, runs a small generation, and fails unless placement says `100% CPU`.
Logs and a process record live under ignored `.data`.

One-time install/download, if absent:

```powershell
winget install --id Ollama.Ollama -e
ollama pull qwen3:0.6b
ollama pull qwen3-embedding:0.6b
```

Do not expose port 11434 to the LAN or public internet. After initial downloads, text generation,
embeddings, indexing, retrieval, and product filtering operate locally without an inference API.
