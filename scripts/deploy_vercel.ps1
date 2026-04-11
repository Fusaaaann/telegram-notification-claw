$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

$vercel = Get-Command vercel -ErrorAction SilentlyContinue
if (-not $vercel) {
  Write-Host "Vercel CLI not found."
  Write-Host "Install it first: npm install -g vercel"
  Write-Host "Or: bun install -g vercel"
  exit 1
}

$projectFile = Join-Path $root ".vercel/project.json"
if (-not (Test-Path $projectFile)) {
  Write-Host "Vercel project is not linked for this repo."
  Write-Host "Run: vercel link"
  exit 1
}

try {
  $project = Get-Content $projectFile -Raw | ConvertFrom-Json
} catch {
  Write-Host "Failed to read .vercel/project.json."
  throw
}

if ([string]::IsNullOrWhiteSpace($project.projectId) -or [string]::IsNullOrWhiteSpace($project.orgId)) {
  Write-Host ".vercel/project.json is missing project linkage fields."
  Write-Host "Run: vercel link"
  exit 1
}

$account = [string](& vercel whoami 2>$null)
$account = $account.Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($account)) {
  Write-Host "Vercel CLI is not authenticated."
  Write-Host "Run: vercel login"
  exit 1
}

Write-Host "Linked project: $($project.projectName)"
Write-Host "Vercel account: $account"
Write-Host "Deploying to Vercel (production)..."
& vercel deploy --prod --yes

Write-Host ""
Write-Host "Blob setup reminder:"
Write-Host "- Create a Vercel Blob store in this project (Dashboard > Storage > Blob)."
Write-Host "- This auto-creates BLOB_READ_WRITE_TOKEN in the project env."
Write-Host "- Production env should include REMINDER_ADMIN_TOKEN and TELEGRAM_BOT_TOKEN."
Write-Host "- To use env locally, run: vercel env pull"
