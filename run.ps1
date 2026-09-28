$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceDir = Split-Path -Parent $projectDir
$venvCandidates = foreach ($dir in @($projectDir, $workspaceDir)) {
    Get-ChildItem -Path $dir -Directory -Filter ".venv*" -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path $_.FullName "Scripts\python.exe" }
}

$python = $venvCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $python) {
    Write-Error "Nenhuma venv encontrada. Crie uma com: python -m venv .venv"
    exit 1
}

Set-Location $projectDir
& $python app.py