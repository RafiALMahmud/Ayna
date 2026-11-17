param(
    [int]$ApiPort = 8002,
    [int]$WebPort = 5175,
    [switch]$NoSeed,
    [switch]$EnableFashn,
    [string]$FashnPython = 'D:\models\fashn-vton-venv\Scripts\python.exe',
    [string]$FashnSource = 'D:\models\fashn-vton-src',
    [string]$FashnWeights = 'D:\models\fashn-vton-weights'
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$webRoot = Join-Path $projectRoot 'frontend'
$backendRoot = Join-Path $projectRoot 'backend'
$runtimeRoot = Join-Path $projectRoot '.data'
$ollamaScript = Join-Path $PSScriptRoot 'start-ollama.ps1'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Create .venv and install backend/requirements.lock first. See README.md.' }
if (-not (Test-Path -LiteralPath (Join-Path $webRoot 'node_modules'))) { throw 'Run npm ci in frontend first.' }
foreach ($portNumber in @($ApiPort, $WebPort)) {
    $probe = [System.Net.Sockets.TcpClient]::new()
    try {
        if ($probe.ConnectAsync('127.0.0.1', $portNumber).Wait(500) -and $probe.Connected) {
            throw "Port $portNumber is already occupied. Stop the existing Ayna instance or choose another port."
        }
    } catch [System.AggregateException] { } finally { $probe.Dispose() }
}
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
& $ollamaScript
$env:ENVIRONMENT = 'development'
$env:AI_PROVIDER = 'mock'
$env:DEV_AUTH_ENABLED = 'true'
$env:QUEUE_MODE = 'inline'
$env:STORAGE_BACKEND = 'local'
$env:CURRENCY = 'BDT'
$env:DEMO_PAYMENTS_ENABLED = 'true'
$env:ALLOW_PAID_AI_PROVIDERS = 'false'
$env:RAG_ENABLED = 'true'
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:OLLAMA_CHAT_MODEL = 'qwen3:0.6b'
$env:OLLAMA_EMBEDDING_MODEL = 'qwen3-embedding:0.6b'
$env:RAG_INDEX_PATH = Join-Path $backendRoot '.data\rag-products.json'
$env:TRYON_PROVIDER = 'diagnostic'
if ($EnableFashn) {
    foreach ($requiredPath in @($FashnPython, $FashnSource, $FashnWeights)) {
        if (-not (Test-Path -LiteralPath $requiredPath)) { throw "FASHN path is missing: $requiredPath" }
    }
    $env:TRYON_PROVIDER = 'fashn_vton'
    $env:TRYON_PYTHON = (Resolve-Path -LiteralPath $FashnPython).Path
    $env:TRYON_SOURCE_PATH = (Resolve-Path -LiteralPath $FashnSource).Path
    $env:TRYON_WEIGHTS_PATH = (Resolve-Path -LiteralPath $FashnWeights).Path
    $env:TRYON_TIMEOUT_SECONDS = '900'
    $env:TRYON_FASHN_NONCOMMERCIAL_DEPENDENCY_ACKNOWLEDGED = 'true'
}
$env:PYTHONUTF8 = '1'
$env:DATABASE_URL = 'sqlite:///' + (Join-Path $backendRoot '.data\ayna.db').Replace('\', '/')
$env:LOCAL_STORAGE_PATH = Join-Path $backendRoot '.data\assets'
$env:CORS_ORIGINS = '["http://localhost:' + $WebPort + '"]'
$env:STOREFRONT_URL = 'http://localhost:' + $WebPort
$env:VITE_API_BASE_URL = 'http://localhost:' + $ApiPort
Push-Location $backendRoot
try {
    & $pythonExe -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed' }
    if (-not $NoSeed) {
        & $pythonExe -m scripts.seed_shop
        if ($LASTEXITCODE -ne 0) { throw 'Demo catalog setup failed' }
    }
} finally { Pop-Location }
Push-Location $webRoot
try {
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
} finally { Pop-Location }
$apiProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$ApiPort") -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot 'api.out.log') -RedirectStandardError (Join-Path $runtimeRoot 'api.err.log')
$nodeExe = (Get-Command node.exe).Source
$viteScript = Join-Path $webRoot 'node_modules\vite\bin\vite.js'
$webProcess = Start-Process -FilePath $nodeExe -ArgumentList @("`"$viteScript`"",'preview','--host','127.0.0.1','--port',"$WebPort",'--strictPort') -WorkingDirectory $webRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot 'web.out.log') -RedirectStandardError (Join-Path $runtimeRoot 'web.err.log')
$records = @($apiProcess, $webProcess) | ForEach-Object { @{ id = $_.Id; started = $_.StartTime.ToUniversalTime().ToString('o') } }
@{ workspace = $projectRoot; processes = @($records); api_port = $ApiPort; web_port = $WebPort } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runtimeRoot 'local-processes.json') -Encoding UTF8
$ready = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    try {
        $api = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/ready" -TimeoutSec 3
        $web = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$WebPort" -TimeoutSec 3
        if ($api.status -eq 'ready' -and $web.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $ready) { throw 'Ayna did not become ready. Check .data/*.log; use scripts/stop-local.ps1 before retrying.' }
Write-Output "Ayna: http://localhost:$WebPort"
Write-Output "API docs: http://localhost:$ApiPort/docs"
Write-Output "Try-on provider: $($env:TRYON_PROVIDER)"
Write-Output 'Product assistant: qwen3:0.6b on CPU'
Write-Output 'Native local mode uses a separate SQLite database and local assets. Docker volumes are unchanged.'
