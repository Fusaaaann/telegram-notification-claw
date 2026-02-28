$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

$vercel = Get-Command vercel -ErrorAction SilentlyContinue
if (-not $vercel) {
  Write-Host "Vercel CLI not found."
  Write-Host "Install it first: npm i -g vercel"
  Write-Host "Or: pnpm i -g vercel"
  exit 1
}

Write-Host "Deploying to Vercel (production)..."
& vercel --prod --yes

Write-Host ""
Write-Host "Blob setup reminder:"
Write-Host "- Create a Vercel Blob store in this project (Dashboard > Storage > Blob)."
Write-Host "- This auto-creates BLOB_READ_WRITE_TOKEN in the project env."
Write-Host "- To use env locally, run: vercel env pull"
