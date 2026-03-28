param(
    [string]$VenvDir = ".venv",
    [string]$PythonBin = "python"
)

$ErrorActionPreference = "Stop"

$pythonCmd = Get-Command $PythonBin -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    throw "Error: '$PythonBin' is not installed or not on PATH."
}

& $PythonBin -m venv $VenvDir

$venvPython = Join-Path $VenvDir "Scripts/python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Virtual environment python not found at '$venvPython'."
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt

Write-Host "Setup complete."
Write-Host "Activate your environment with: $VenvDir\\Scripts\\Activate.ps1"
Write-Host "Run the app with: python app.py (after activation)"
