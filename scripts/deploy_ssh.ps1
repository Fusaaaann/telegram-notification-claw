Param(
  [string]$RemoteHost = "your.server",
  [string]$RemoteUser = "ubuntu",
  [string]$RemoteDir = "/opt/reminder-bot",
  [string]$ServiceName = "reminder-bot"
)

# Mock SSH deployment script (DO NOT auto-run).

Write-Host "[MOCK] Would rsync project to $RemoteUser@$RemoteHost:$RemoteDir"
Write-Host "rsync -av --exclude .venv --exclude __pycache__ ./ ${RemoteUser}@${RemoteHost}:${RemoteDir}"

Write-Host "[MOCK] Would install deps on remote and configure systemd"
Write-Host "ssh ${RemoteUser}@${RemoteHost} 'cd ${RemoteDir} && ./scripts/install_deps.sh'"
