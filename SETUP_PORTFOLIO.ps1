$ErrorActionPreference = 'Stop'
$envDir = Join-Path $PSScriptRoot '.venv-portfolio'
$pythonPath = Join-Path $envDir 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    if (Test-Path -LiteralPath $envDir) { throw 'Incomplete environment exists. Rename it first; no files overwritten.' }
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $launcher) { $launcher = Get-Command python -ErrorAction SilentlyContinue }
    if (-not $launcher) { throw 'Install Python 3.11+ first and reopen the terminal.' }
    & $launcher.Source -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
    if ($LASTEXITCODE -ne 0) { throw 'No compatible Python. Setup stopped.' }
    & $launcher.Source -m venv $envDir
    if ($LASTEXITCODE -ne 0) { throw 'Could not create environment.' }
}
& $pythonPath -m pip install requests numpy pandas
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $pythonPath (Join-Path $PSScriptRoot 'tools\package_training_bundle.py')
if ($LASTEXITCODE -ne 0) { throw 'Training bundle setup failed.' }
Write-Host 'Ready: double-click 00_OPEN_REPORT.cmd. The map needs no device credentials.'
