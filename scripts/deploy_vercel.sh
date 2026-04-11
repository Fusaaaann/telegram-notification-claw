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

if [[ ! -f .vercel/project.json ]]; then
  echo "Vercel project is not linked for this repo."
  echo "Run: vercel link"
  exit 1
fi

if ! ACCOUNT="$(vercel whoami 2>/dev/null)"; then
  echo "Vercel CLI is not authenticated."
  echo "Run: vercel login"
  exit 1
fi

PROJECT_NAME="$(node -e 'const fs=require("fs"); const p=JSON.parse(fs.readFileSync(".vercel/project.json","utf8")); if(!p.projectId || !p.orgId){process.exit(1)} process.stdout.write(p.projectName || "")')"

echo "Linked project: ${PROJECT_NAME:-unknown}"
echo "Vercel account: $ACCOUNT"
echo "Deploying to Vercel (production)..."
vercel deploy --prod --yes

echo ""
echo "Blob setup reminder:"
echo "- Create a Vercel Blob store in this project (Dashboard > Storage > Blob)."
echo "- This auto-creates BLOB_READ_WRITE_TOKEN in the project env."
echo "- Production env should include REMINDER_ADMIN_TOKEN and TELEGRAM_BOT_TOKEN."
echo "- To use env locally, run: vercel env pull"
