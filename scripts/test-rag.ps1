param([int]$ApiPort = 8002)
$ErrorActionPreference = 'Stop'
$banglaPoints = @(0x09E7,0x09EB,0x09E6,0x09E6,0x0020,0x099F,0x09BE,0x0995,0x09BE,0x09B0,0x0020,0x09AE,0x09A7,0x09CD,0x09AF,0x09C7,0x0020,0x0995,0x09BE,0x09B2,0x09CB,0x0020,0x09B6,0x09BE,0x09B0,0x09CD,0x099F,0x0020,0x09A6,0x09C7,0x0996,0x09BE,0x0993)
$banglaQuestion = -join ($banglaPoints | ForEach-Object { [char]$_ })
$questions = @(
    'Show the cheapest shirts',
    'Which items have 3D views?',
    $banglaQuestion
)
foreach ($question in $questions) {
    $body = @{ message = $question } | ConvertTo-Json
    $utf8Body = [System.Text.Encoding]::UTF8.GetBytes($body)
    $result = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$ApiPort/api/v1/chat/search" -ContentType 'application/json; charset=utf-8' -Body $utf8Body -TimeoutSec 90
    Write-Output "Question: $question"
    Write-Output "Mode: $($result.mode); products: $($result.products.Count)"
    Write-Output "Answer: $($result.answer)"
}
