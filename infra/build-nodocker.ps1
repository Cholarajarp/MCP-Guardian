<#
  Build the MCP Guardian Lambda artifact WITHOUT Docker and WITHOUT a local
  Python 3.12 interpreter.

  Why this exists: `sam build` needs either Docker (--use-container) or a host
  `python` binary matching the function runtime. On a machine with only Python
  3.14 and no Docker, neither is available.

  How it works: pip can download wheels built FOR another platform and ABI
  without ever executing them --
      --platform manylinux2014_x86_64   Lambda OS/arch
      --python-version 3.12             function runtime
      --only-binary=:all:               never build from source (a source build
                                        would target the HOST and produce a
                                        Windows binary Lambda cannot load)
  That matters for pydantic-core, which ships a compiled extension; the rest of
  the runtime set is pure Python.

  Output: a directory with vendored dependencies plus the `app` package, and a
  template whose CodeUri points at it, ready for `sam deploy`.

  The platform check at the end is the point: a wrong-platform wheel builds
  cleanly and only fails after deploy, so the script refuses to emit one.
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$Runtime  = "3.12"
)

$ErrorActionPreference = "Stop"

# $PSScriptRoot is not reliably populated inside param() defaults under Windows
# PowerShell 5.1, so the repo root is resolved here in the body instead.
if (-not $RepoRoot) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $RepoRoot  = (Resolve-Path (Join-Path $scriptDir "..")).Path
}

$outDir      = Join-Path $RepoRoot ".aws-sam-nodocker"
$buildDir    = Join-Path $outDir "build"
$templateOut = Join-Path $outDir "template.yaml"
$backendDir  = Join-Path $RepoRoot "backend"
$reqFile     = Join-Path $backendDir "requirements.txt"

Write-Host "==> Reset output directory" -ForegroundColor Cyan
if (Test-Path -LiteralPath $outDir) {
    [System.IO.Directory]::Delete($outDir, $true)
}
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null

# --- any working local Python can drive pip; it never runs the wheels --------
$driver = $null
$venvPy = Join-Path $backendDir ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPy) { $driver = $venvPy }
if (-not $driver) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $driver = $cmd.Source }
}
if (-not $driver) { throw "No usable Python found to drive pip." }
Write-Host "    pip driver: $driver" -ForegroundColor DarkGray

Write-Host "==> Vendor runtime dependencies for linux/x86_64, python $Runtime" -ForegroundColor Cyan
& $driver -m pip install `
    --requirement $reqFile `
    --target $buildDir `
    --platform manylinux2014_x86_64 `
    --python-version $Runtime `
    --implementation cp `
    --only-binary=:all: `
    --upgrade --no-compile --quiet
if ($LASTEXITCODE -ne 0) { throw "pip vendoring failed (exit $LASTEXITCODE)." }

Write-Host "==> Copy application package" -ForegroundColor Cyan
Copy-Item -Path (Join-Path $backendDir "app") -Destination $buildDir -Recurse -Force
# Stale local bytecode compiled by a different Python must not ship.
foreach ($cacheDir in (Get-ChildItem -Path $buildDir -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue)) {
    [System.IO.Directory]::Delete($cacheDir.FullName, $true)
}

# --- verification: the exact failure this script exists to prevent ----------
Write-Host "==> Verify the artifact targets Linux, not Windows" -ForegroundColor Cyan
$coreDir = Join-Path $buildDir "pydantic_core"
if (-not (Test-Path -LiteralPath $coreDir)) { throw "pydantic_core missing from the artifact." }
$winPyd = Get-ChildItem -Path $coreDir -Filter "*.pyd" -ErrorAction SilentlyContinue
if ($winPyd) { throw "Windows .pyd in the artifact - it would crash on Lambda. Aborting." }
$linuxSo = Get-ChildItem -Path $coreDir -Filter "*.so" -ErrorAction SilentlyContinue
if (-not $linuxSo) { throw "No Linux .so for pydantic_core - wheels resolved for the wrong platform." }
Write-Host "    OK: $($linuxSo[0].Name)" -ForegroundColor Green

foreach ($required in @("fastapi", "mangum", "boto3", "httpx", "pydantic", "app\main.py", "app\guard.py")) {
    if (-not (Test-Path -LiteralPath (Join-Path $buildDir $required))) {
        throw "Artifact incomplete: $required missing."
    }
}
Write-Host "    OK: app plus all runtime dependencies present" -ForegroundColor Green

# --- emit a deploy template pointing at the prepared directory -------------
Write-Host "==> Write deploy template" -ForegroundColor Cyan
$source = Get-Content -LiteralPath (Join-Path $RepoRoot "infra\template.yaml") -Raw
# Only CodeUri changes: SAM must upload the vendored directory rather than
# re-resolve backend/, which would trigger the build it cannot perform here.
$patched = $source.Replace("CodeUri: ../backend", "CodeUri: build")
if ($patched -eq $source) { throw "CodeUri rewrite failed - check infra/template.yaml." }
Set-Content -LiteralPath $templateOut -Value $patched -Encoding utf8

$bytes  = (Get-ChildItem -Path $buildDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
$sizeMb = [math]::Round($bytes / 1MB, 1)
Write-Host ""
Write-Host "Build complete." -ForegroundColor Green
Write-Host "  artifact: $buildDir  ($sizeMb MB unzipped; Lambda allows 250 MB)"
Write-Host "  template: $templateOut"
Write-Host ""
Write-Host "Deploy with:" -ForegroundColor Cyan
Write-Host "  sam deploy --template `"$templateOut`" --stack-name mcp-guardian --capabilities CAPABILITY_IAM --resolve-s3 --region us-east-1"
