param(
    [Parameter(Position = 0)]
    [ValidateSet("normal", "double-refund", "trace", "cost", "state", "check")]
    [string]$Command,

    [Parameter(Position = 1)]
    [string]$Trace
)

$ErrorActionPreference = "Stop"

if (-not $Command) {
    Write-Host "Usage: .\rosso.ps1 <normal|double-refund|trace|cost|state|check> [trace]"
    exit 2
}

$productRoot = $PSScriptRoot
$pythonPath = Join-Path $productRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    Write-Error "Missing .venv. Install uv, then run: uv sync"
    exit 2
}

Push-Location -LiteralPath $productRoot
try {
    switch ($Command) {
        "normal" {
            & $pythonPath -m demo.refund.experiment normal
        }
        "double-refund" {
            & $pythonPath -m demo.refund.experiment double-refund
        }
        "trace" {
            if ($Trace) {
                & $pythonPath -m demo.refund.trace $Trace
            }
            else {
                & $pythonPath -m demo.refund.trace
            }
        }
        "cost" {
            if ($Trace) {
                & $pythonPath -m demo.refund.cost $Trace
            }
            else {
                & $pythonPath -m demo.refund.cost
            }
        }
        "state" {
            & $pythonPath -m demo.refund.observe --details
        }
        "check" {
            & $pythonPath -m pytest
            if ($LASTEXITCODE -ne 0) {
                exit $LASTEXITCODE
            }
            & $pythonPath -m ruff check .
        }
    }
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
