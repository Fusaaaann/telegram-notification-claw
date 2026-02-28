#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v vercel >/dev/null 2>&1; then
  echo "Vercel CLI not found."
  echo "Install it first: pnpm i -g vercel"
  echo "Or: npm i -g vercel"
  exit 1
fi

echo "Deploying to Vercel (production)..."
vercel --prod --yes

echo ""
echo "Blob setup reminder:"
echo "- Create a Vercel Blob store in this project (Dashboard > Storage > Blob)."
echo "- This auto-creates BLOB_READ_WRITE_TOKEN in the project env."
echo "- To use env locally, run: vercel env pull"
