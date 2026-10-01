$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $ProjectRoot ".venv-windows"

if (-not (Test-Path (Join-Path $VenvPath "Scripts\python.exe"))) {
    # rapidocr-onnxruntime 1.4.4 要求 Python <3.13，3.13/3.14 装不上依赖
    $created = $false
    foreach ($version in @("3.11", "3.12")) {
        & py "-$version" --version *> $null
        if ($LASTEXITCODE -ne 0) { continue }
        py "-$version" -m venv $VenvPath
        if ($LASTEXITCODE -eq 0) { $created = $true; break }
    }
    if (-not $created) {
        throw "未找到 Python 3.11 或 3.12。依赖 rapidocr-onnxruntime 要求 Python <3.13，请安装后重试。"
    }
}

$PythonExe = Join-Path $VenvPath "Scripts\python.exe"
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")

Write-Host "安装完成。运行：windows\start.ps1"

