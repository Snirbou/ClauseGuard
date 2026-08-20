<#
.SYNOPSIS
    Full ClauseGuard verification suite: database, backend, live API, frontend.

.DESCRIPTION
    Runs every automated check the project has, in dependency order, and prints
    a PASS/FAIL summary. Exits 0 only if every check passes.

    Sections:
      1. Database  - Postgres reachable (starts docker compose if needed)
      2. Backend   - ruff lint, unit tests, migrations at head + no drift
      3. Live API  - starts uvicorn if needed, health, 63-check smoke test
      4. Frontend  - TypeScript typecheck, ESLint, (optional) production build

.PARAMETER SkipFrontendBuild
    Skip the ~1-2 min "next build" (still runs tsc + eslint).

.PARAMETER SkipDocker
    Do not try to start Postgres via docker compose (assume it is already up).

.PARAMETER Port
    Backend port for the live API section (default 8000).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .claude\skills\verify-clauseguard\run_checks.ps1

NOTE: This file must stay ASCII-only. Windows PowerShell 5.1 reads .ps1 files
as the system codepage unless they carry a UTF-8 BOM, so a stray non-ASCII
character (em dash, box-drawing, emoji) corrupts the parser.
#>
param(
    [switch]$SkipFrontendBuild,
    [switch]$SkipDocker,
    [int]$Port = 8000
)

$ErrorActionPreference = 'Continue'

# --- Locate the repo root (walk up until backend/ and frontend/ both exist) ---
$dir = $PSScriptRoot
while ($dir -and -not ((Test-Path (Join-Path $dir 'backend')) -and (Test-Path (Join-Path $dir 'frontend')))) {
    $parent = Split-Path -Parent $dir
    if ($parent -eq $dir) { break }
    $dir = $parent
}
$RepoRoot = $dir
$Backend = Join-Path $RepoRoot 'backend'
$Frontend = Join-Path $RepoRoot 'frontend'
$Python = Join-Path $Backend 'venv\Scripts\python.exe'
$DbPing = Join-Path $PSScriptRoot '_db_ping.py'

if (-not (Test-Path $Python)) {
    Write-Host "FATAL: backend venv python not found at $Python" -ForegroundColor Red
    Write-Host "Create it: cd backend; python -m venv venv; venv\Scripts\pip install -r requirements.txt"
    exit 2
}

# --- Result tracking ---------------------------------------------------------
$Results = [System.Collections.Generic.List[object]]::new()
function Add-Result($name, $ok, $detail = '') {
    $Results.Add([pscustomobject]@{ Name = $name; Ok = [bool]$ok; Detail = $detail })
    $tag = if ($ok) { 'PASS' } else { 'FAIL' }
    $color = if ($ok) { 'Green' } else { 'Red' }
    Write-Host ("  [{0}] {1}" -f $tag, $name) -ForegroundColor $color
    if ($detail -and -not $ok) { Write-Host ("        {0}" -f $detail) -ForegroundColor DarkYellow }
}
function Section($title) {
    Write-Host ""
    Write-Host "== $title ==" -ForegroundColor Cyan
}

# Run a native command in a directory, capture combined output + exit code.
function Invoke-Check($name, $workdir, $exe, [string[]]$cmdArgs) {
    Push-Location $workdir
    try {
        $out = & $exe @cmdArgs 2>&1 | Out-String
        $code = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    $ok = ($code -eq 0)
    $tail = ($out -split "`n" | Where-Object { $_.Trim() } | Select-Object -Last 3) -join ' | '
    Add-Result $name $ok $tail
    return $ok
}

function Test-Db {
    Push-Location $Backend
    try {
        $out = & $Python $DbPing 2>&1 | Out-String
    } finally {
        Pop-Location
    }
    return ($out -match 'OK')
}

function Test-Health {
    param([int]$p)
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$p/api/health" -UseBasicParsing -TimeoutSec 4
        return ($r.StatusCode -eq 200 -and $r.Content -match 'database')
    } catch {
        return $false
    }
}

Write-Host "ClauseGuard verification" -ForegroundColor White
Write-Host "repo: $RepoRoot"

# ============================================================================
# 1. Database
# ============================================================================
Section "1. Database"
$dbUp = Test-Db
if (-not $dbUp -and -not $SkipDocker) {
    Write-Host "  Postgres not reachable; starting docker compose..." -ForegroundColor DarkYellow
    Push-Location $RepoRoot
    & docker compose up -d 2>&1 | Out-Null
    Pop-Location
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 2
        if (Test-Db) { $dbUp = $true; break }
    }
}
$dbHint = ''
if (-not $dbUp) { $dbHint = 'Start it: docker compose up -d' }
Add-Result "Postgres reachable" $dbUp $dbHint

# ============================================================================
# 2. Backend (static)
# ============================================================================
Section "2. Backend"
Invoke-Check "ruff lint"  $Backend $Python @('-m','ruff','check','.')  | Out-Null
# tests/ and ml_training/tests/ run as separate invocations: both define a
# top-level `src` / `features` module, so collecting them together trips
# pytest's default import mode. Run apart, exactly as each is designed.
Invoke-Check "unit tests (api)"      $Backend $Python @('-m','pytest','tests/','-q')              | Out-Null
Invoke-Check "unit tests (ml)"       $Backend $Python @('-m','pytest','ml_training/tests/','-q')  | Out-Null
Invoke-Check "import app" $Backend $Python @('-c','import main')       | Out-Null

if ($dbUp) {
    Invoke-Check "migrations upgrade head"  $Backend $Python @('-m','alembic','upgrade','head') | Out-Null
    # "alembic check" fails if the ORM models have drifted from the migrations.
    Invoke-Check "no model/migration drift" $Backend $Python @('-m','alembic','check')          | Out-Null
    # Exactly one head; a fork would make "upgrade head" ambiguous.
    Push-Location $Backend
    $headsOut = & $Python -m alembic heads 2>&1 | Out-String
    Pop-Location
    $headCount = ([regex]::Matches($headsOut, '\(head\)')).Count
    Add-Result "single migration head" ($headCount -eq 1) "found $headCount head(s)"
} else {
    Add-Result "migrations (skipped)" $false "database not reachable"
}

# ============================================================================
# 3. Live API (smoke test)
# ============================================================================
Section "3. Live API"
$serverProc = $null
$startedByUs = $false
if ($dbUp) {
    if (-not (Test-Health -p $Port)) {
        Write-Host "  Starting uvicorn on port $Port..." -ForegroundColor DarkYellow
        $serverProc = Start-Process -FilePath $Python `
            -ArgumentList @('-m','uvicorn','main:app','--port',"$Port",'--host','127.0.0.1') `
            -WorkingDirectory $Backend -WindowStyle Hidden -PassThru
        $startedByUs = $true
        for ($i = 0; $i -lt 60; $i++) {
            Start-Sleep -Milliseconds 900
            if (Test-Health -p $Port) { break }
        }
    }
    $healthy = Test-Health -p $Port
    Add-Result "API health" $healthy
    if ($healthy) {
        Invoke-Check "smoke test (E2E)" $Backend $Python @('smoke_test.py','--base-url',"http://127.0.0.1:$Port") | Out-Null
    } else {
        Add-Result "smoke test (skipped)" $false "API did not become healthy"
    }
    if ($startedByUs -and $serverProc) {
        Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue
    }
} else {
    Add-Result "live API (skipped)" $false "database not reachable"
}

# ============================================================================
# 4. Frontend
# ============================================================================
Section "4. Frontend"
if (-not (Test-Path (Join-Path $Frontend 'node_modules'))) {
    Write-Host "  Installing frontend deps (npm ci)..." -ForegroundColor DarkYellow
    Invoke-Check "npm ci" $Frontend 'npm' @('ci') | Out-Null
}
Invoke-Check "typescript (tsc)" $Frontend 'npx' @('--no-install','tsc','--noEmit') | Out-Null
Invoke-Check "eslint"           $Frontend 'npx' @('--no-install','eslint','src')   | Out-Null
if (-not $SkipFrontendBuild) {
    Invoke-Check "next build" $Frontend 'npx' @('--no-install','next','build') | Out-Null
} else {
    Write-Host "  (next build skipped via -SkipFrontendBuild)" -ForegroundColor DarkGray
}

# ============================================================================
# Summary
# ============================================================================
$passed = ($Results | Where-Object { $_.Ok }).Count
$failed = ($Results | Where-Object { -not $_.Ok }).Count

Write-Host ""
Write-Host "============================================================" -ForegroundColor White
$summaryColor = if ($failed -eq 0) { 'Green' } else { 'Red' }
Write-Host ("SUMMARY: {0} passed, {1} failed" -f $passed, $failed) -ForegroundColor $summaryColor
if ($failed -gt 0) {
    Write-Host "Failed checks:" -ForegroundColor Red
    foreach ($r in $Results) {
        if (-not $r.Ok) { Write-Host ("  - {0}" -f $r.Name) -ForegroundColor Red }
    }
}
Write-Host "============================================================" -ForegroundColor White

if ($failed -eq 0) { exit 0 } else { exit 1 }
