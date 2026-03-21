#!/usr/bin/env bash
# End-to-end API test script for the deployed Vercel reminder bot.
# Uses `vercel curl` for automatic deployment auth/bypass handling.
# Config is loaded from .env.test in the repo root (copy from .env.test.example).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env.test"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE"; set +a
fi

DEPLOYMENT="${DEPLOYMENT:?Set DEPLOYMENT in .env.test (e.g. https://your-app.vercel.app)}"
ADMIN_TOKEN="${ADMIN_TOKEN:?Set ADMIN_TOKEN in .env.test}"
TEST_USER_ID="${TEST_USER_ID:-111111111}"
USER_ID_B="${USER_ID_B:-222222222}"

BYPASS_ARGS=()
if [[ -n "${VERCEL_BYPASS_TOKEN:-}" ]]; then
  BYPASS_ARGS=(--protection-bypass "$VERCEL_BYPASS_TOKEN")
fi

PASS=0
FAIL=0

green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }

pass() { green "  PASS: $1"; ((PASS++)) || true; }
fail() { red   "  FAIL: $1 — $2"; ((FAIL++)) || true; }

# Run vercel curl, capture full response (headers + body) via --include.
# Outputs: sets global RESP_STATUS and RESP_BODY.
vcurl() {
  local path="$1"; shift
  local raw
  raw=$(vercel curl "$path" --deployment "$DEPLOYMENT" "${BYPASS_ARGS[@]}" -- --silent --include "$@" 2>/dev/null || true)
  RESP_STATUS=$(echo "$raw" | grep -m1 '^HTTP/' | awk '{print $2}')
  RESP_BODY=$(echo "$raw" | awk 'BEGIN{body=0} /^\r?$/{body=1; next} body{print}')
}

check_status() {
  local label="$1" expected="$2"
  if [[ "$RESP_STATUS" == "$expected" ]]; then
    pass "$label (HTTP $RESP_STATUS)"
  else
    fail "$label" "expected HTTP $expected, got $RESP_STATUS — $RESP_BODY"
  fi
}

check_field() {
  local label="$1" field="$2" expected="$3"
  local actual
  actual=$(echo "$RESP_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$field','<missing>'))" 2>/dev/null || echo "<parse error>")
  if [[ "$actual" == "$expected" ]]; then
    pass "$label ($field=$actual)"
  else
    fail "$label" "expected $field=$expected, got $field=$actual — $RESP_BODY"
  fi
}

check_contains() {
  local label="$1" needle="$2"
  if echo "$RESP_BODY" | grep -q "$needle"; then
    pass "$label (contains '$needle')"
  else
    fail "$label" "expected to find '$needle' in: $RESP_BODY"
  fi
}

check_not_contains() {
  local label="$1" needle="$2"
  if ! echo "$RESP_BODY" | grep -q "$needle"; then
    pass "$label (does not contain '$needle')"
  else
    fail "$label" "did NOT expect to find '$needle' in: $RESP_BODY"
  fi
}

jq_field() {
  local field="$1"
  echo "$RESP_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['$field'])" 2>/dev/null || true
}

echo "================================================================"
echo "  Reminder Bot API Tests"
echo "  DEPLOYMENT=$DEPLOYMENT"
echo "  TEST_USER_ID=$TEST_USER_ID"
echo "================================================================"

# ---------------------------------------------------------------------------
# 0. Cleanup: delete all reminders for test users before running
# ---------------------------------------------------------------------------
echo
echo "--- 0. Pre-test Cleanup ---"
for uid in "$TEST_USER_ID" "$USER_ID_B"; do
  vcurl /v1/admin/reminders \
    --header "Authorization: Bearer $ADMIN_TOKEN" \
    --header "X-Reminder-User-Id: $uid"
  IDS=$(echo "$RESP_BODY" | python3 -c "import sys,json; print(' '.join(str(r['id']) for r in json.load(sys.stdin)))" 2>/dev/null || true)
  for id in $IDS; do
    vcurl "/v1/admin/reminders/$id" \
      --request DELETE \
      --header "Authorization: Bearer $ADMIN_TOKEN" \
      --header "X-Reminder-User-Id: $uid" || true
  done
done
echo "  cleanup done"

# ---------------------------------------------------------------------------
# 1. Health check
# ---------------------------------------------------------------------------
echo
echo "--- 1. Health Check ---"
vcurl /health
check_status "health endpoint" "200"
check_field  "health ok=true"  "ok" "True"

# ---------------------------------------------------------------------------
# 2. Issue user token
# ---------------------------------------------------------------------------
echo
echo "--- 2. Admin: Issue User Token ---"
vcurl "/v1/admin/users/$TEST_USER_ID/token" \
  --request POST \
  --header "Authorization: Bearer $ADMIN_TOKEN"
check_status "issue user token" "200"

USER_TOKEN=$(jq_field token)
if [[ ${#USER_TOKEN} -ge 40 ]]; then
  pass "user token length (${#USER_TOKEN} chars)"
else
  fail "user token length" "got: '$USER_TOKEN'"
fi

# Wait for blob to propagate the new token
sleep 1

# ---------------------------------------------------------------------------
# 3. Admin: Create reminders
# ---------------------------------------------------------------------------
echo
echo "--- 3. Admin: Create Reminders ---"
vcurl /v1/admin/reminders \
  --request POST \
  --header "Authorization: Bearer $ADMIN_TOKEN" \
  --header "X-Reminder-User-Id: $TEST_USER_ID" \
  --header "Content-Type: application/json" \
  --data '{"text":"buy milk","due_at":null,"visibility":"user"}'
check_status "admin create (no due_at)" "200"
check_field  "admin create text"        "text" "buy milk"
check_field  "admin create done=false"  "done" "False"

REMINDER_ID=$(jq_field id)

vcurl /v1/admin/reminders \
  --request POST \
  --header "Authorization: Bearer $ADMIN_TOKEN" \
  --header "X-Reminder-User-Id: $TEST_USER_ID" \
  --header "Content-Type: application/json" \
  --data '{"text":"pay rent","due_at":"2026-03-10T09:00:00","visibility":"user"}'
check_status "admin create (with due_at)" "200"
check_field  "admin create due_at set"    "text" "pay rent"

# ---------------------------------------------------------------------------
# 4. Admin: List reminders
# ---------------------------------------------------------------------------
echo
echo "--- 4. Admin: List Reminders ---"
vcurl /v1/admin/reminders \
  --header "Authorization: Bearer $ADMIN_TOKEN" \
  --header "X-Reminder-User-Id: $TEST_USER_ID"
check_status   "admin list (all)" "200"
check_contains "admin list contains buy milk" "buy milk"
check_contains "admin list contains pay rent" "pay rent"

vcurl "/v1/admin/reminders?include_done=false" \
  --header "Authorization: Bearer $ADMIN_TOKEN" \
  --header "X-Reminder-User-Id: $TEST_USER_ID"
check_status   "admin list (include_done=false)" "200"
check_contains "admin list no-done has buy milk" "buy milk"

# ---------------------------------------------------------------------------
# 5. Admin: Get single reminder
# ---------------------------------------------------------------------------
echo
echo "--- 5. Admin: Get Single Reminder ---"
vcurl "/v1/admin/reminders/$REMINDER_ID" \
  --header "Authorization: Bearer $ADMIN_TOKEN" \
  --header "X-Reminder-User-Id: $TEST_USER_ID"
check_status "admin get existing"    "200"
check_field  "admin get correct id"  "id" "$REMINDER_ID"

vcurl /v1/admin/reminders/99999999 \
  --header "Authorization: Bearer $ADMIN_TOKEN" \
  --header "X-Reminder-User-Id: $TEST_USER_ID"
check_status "admin get non-existent → 404" "404"

# ---------------------------------------------------------------------------
# 6. Admin: Update reminder
# ---------------------------------------------------------------------------
echo
echo "--- 6. Admin: Update Reminder ---"
vcurl "/v1/admin/reminders/$REMINDER_ID" \
  --request PATCH \
  --header "Authorization: Bearer $ADMIN_TOKEN" \
  --header "X-Reminder-User-Id: $TEST_USER_ID" \
  --header "Content-Type: application/json" \
  --data '{"done":true}'
check_status "admin update done=true"  "200"
check_field  "admin update done field" "done" "True"

vcurl "/v1/admin/reminders?include_done=false" \
  --header "Authorization: Bearer $ADMIN_TOKEN" \
  --header "X-Reminder-User-Id: $TEST_USER_ID"
check_status       "admin list after done"        "200"
check_not_contains "done reminder filtered out"   "buy milk"
check_contains     "undone reminder still listed" "pay rent"

# ---------------------------------------------------------------------------
# 7. Admin: Delete reminder
# ---------------------------------------------------------------------------
echo
echo "--- 7. Admin: Delete Reminder ---"
vcurl "/v1/admin/reminders/$REMINDER_ID" \
  --request DELETE \
  --header "Authorization: Bearer $ADMIN_TOKEN" \
  --header "X-Reminder-User-Id: $TEST_USER_ID"
check_status "admin delete"       "200"
check_field  "admin delete ok=true" "ok" "True"

vcurl "/v1/admin/reminders/$REMINDER_ID" \
  --header "Authorization: Bearer $ADMIN_TOKEN" \
  --header "X-Reminder-User-Id: $TEST_USER_ID"
check_status "admin get deleted → 404" "404"

# ---------------------------------------------------------------------------
# 8. User token: CRUD
# ---------------------------------------------------------------------------
echo
echo "--- 8. User Token: CRUD ---"
vcurl /v1/user/reminders \
  --request POST \
  --header "Authorization: Bearer $USER_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{"text":"user reminder"}'
check_status "user create"      "200"
check_field  "user create text" "text" "user reminder"

USER_REMINDER_ID=$(jq_field id)

vcurl /v1/user/reminders \
  --header "Authorization: Bearer $USER_TOKEN"
check_status   "user list"             "200"
check_contains "user list has reminder" "user reminder"

vcurl "/v1/user/reminders/$USER_REMINDER_ID" \
  --request PATCH \
  --header "Authorization: Bearer $USER_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{"text":"updated text","done":true}'
check_status "user update"      "200"
check_field  "user update text" "text" "updated text"
check_field  "user update done" "done" "True"

vcurl "/v1/user/reminders/$USER_REMINDER_ID" \
  --request DELETE \
  --header "Authorization: Bearer $USER_TOKEN"
check_status "user delete"         "200"
check_field  "user delete ok=true" "ok" "True"

# ---------------------------------------------------------------------------
# 9. Auth: Negative cases
# ---------------------------------------------------------------------------
echo
echo "--- 9. Auth: Negative Cases ---"
vcurl /v1/admin/reminders \
  --header "Authorization: Bearer wrong-token" \
  --header "X-Reminder-User-Id: $TEST_USER_ID"
check_status "wrong admin token → 401" "401"

vcurl /v1/admin/reminders \
  --header "Authorization: Bearer $ADMIN_TOKEN"
check_status "admin list without scope returns globals" "200"

vcurl /v1/admin/reminders \
  --request POST \
  --header "Authorization: Bearer $ADMIN_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{"text":"missing scope","visibility":"user"}'
check_status "user-visible admin create without scope → 400" "400"

vcurl /v1/user/reminders \
  --header "Authorization: Bearer invalid-user-token"
check_status "invalid user token → 401" "401"

vcurl /v1/admin/reminders \
  --header "Authorization: Bearer $USER_TOKEN" \
  --header "X-Reminder-User-Id: $TEST_USER_ID"
check_status "user token on admin route → 401" "401"

# ---------------------------------------------------------------------------
# 10. User isolation
# ---------------------------------------------------------------------------
echo
echo "--- 10. User Isolation ---"
vcurl "/v1/admin/users/$USER_ID_B/token" \
  --request POST \
  --header "Authorization: Bearer $ADMIN_TOKEN"
check_status "issue token for user B" "200"
USER_TOKEN_B=$(jq_field token)

# Wait for blob to propagate the new token
sleep 1

vcurl /v1/user/reminders \
  --request POST \
  --header "Authorization: Bearer $USER_TOKEN_B" \
  --header "Content-Type: application/json" \
  --data '{"text":"user B secret reminder"}'
check_status "user B create reminder" "200"

# Re-issue user A token (issuing user B's token doesn't affect user A)
vcurl "/v1/admin/users/$TEST_USER_ID/token" \
  --request POST \
  --header "Authorization: Bearer $ADMIN_TOKEN"
USER_TOKEN=$(jq_field token)

# Wait for blob to propagate the re-issued token
sleep 1

vcurl /v1/user/reminders \
  --header "Authorization: Bearer $USER_TOKEN"
check_status       "user A list (isolation)"         "200"
check_not_contains "user A cannot see user B's data" "user B secret reminder"

vcurl /v1/admin/reminders \
  --header "Authorization: Bearer $ADMIN_TOKEN" \
  --header "X-Reminder-User-Id: $USER_ID_B"
check_status   "admin sees user B's reminders"       "200"
check_contains "user B reminder visible to admin"    "user B secret reminder"

# ---------------------------------------------------------------------------
# 12. Blob persistence (basic smoke test)
# ---------------------------------------------------------------------------
echo
echo "--- 12. Blob Persistence ---"
vcurl /v1/admin/reminders \
  --request POST \
  --header "Authorization: Bearer $ADMIN_TOKEN" \
  --header "X-Reminder-User-Id: $TEST_USER_ID" \
  --header "Content-Type: application/json" \
  --data '{"text":"persistence test","visibility":"user"}'
check_status "blob: create reminder" "200"
PERSIST_ID=$(jq_field id)

sleep 3

vcurl "/v1/admin/reminders/$PERSIST_ID" \
  --header "Authorization: Bearer $ADMIN_TOKEN" \
  --header "X-Reminder-User-Id: $TEST_USER_ID"
check_status   "blob: reminder survives re-fetch"  "200"
check_contains "blob: correct reminder retrieved"  "persistence test"

# Cleanup
vcurl "/v1/admin/reminders/$PERSIST_ID" \
  --request DELETE \
  --header "Authorization: Bearer $ADMIN_TOKEN" \
  --header "X-Reminder-User-Id: $TEST_USER_ID"

# ---------------------------------------------------------------------------
# 13. Telegram delivery smoke test
# ---------------------------------------------------------------------------
echo
echo "--- 13. Telegram Delivery ---"
if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${NOTIFY_USER_ID:-}" ]]; then
  echo "  SKIP: set TELEGRAM_BOT_TOKEN and NOTIFY_USER_ID in .env.test to enable"
else
  TG_RESP=$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${NOTIFY_USER_ID}" \
    --data-urlencode "text=🔔 [test] reminder delivery check")
  TG_OK=$(echo "$TG_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('ok',''))" 2>/dev/null || echo "false")
  if [[ "$TG_OK" == "True" ]]; then
    pass "telegram sendMessage (check your Telegram)"
  else
    fail "telegram sendMessage" "$TG_RESP"
  fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo
echo "================================================================"
TOTAL=$((PASS + FAIL))
if [[ $FAIL -eq 0 ]]; then
  green "  ALL $TOTAL TESTS PASSED"
else
  red   "  $FAIL/$TOTAL TESTS FAILED"
fi
echo "================================================================"
[[ $FAIL -eq 0 ]]
