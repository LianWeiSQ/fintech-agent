$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$bin = Join-Path $root ".tools\\clawhub\\node_modules\\.bin\\clawhub.cmd"

if (-not (Test-Path $bin)) {
    Write-Error "ClawHub is not installed locally. Run: npm.cmd install --prefix .tools\\clawhub clawhub@0.8.0"
}

& $bin @Args
