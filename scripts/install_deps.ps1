Param(
  [string]$Python = "python",
  [string]$VenvDir = ".venv",
  [string]$Requirements = "requirements.txt"
)

# Mock install script (DO NOT auto-run).
# Creates a venv and installs requirements.

& $Python -m venv $VenvDir
& "$VenvDir\Scripts\pip.exe" install --upgrade pip
& "$VenvDir\Scripts\pip.exe" install -r $Requirements

Write-Host "Done: dependencies installed into $VenvDir"
