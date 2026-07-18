#!/usr/bin/env bash
# Demonstrate that conversation state is durable in CockroachDB, not process memory.
#
# Sends a chat turn carrying a unique marker, restarts the backend container
# (wiping all in-process state), then re-reads the session's history. The marker
# is still there because LangGraph's checkpoints live in CockroachDB (via
# AsyncCockroachDBSaver), keyed by session id -- an in-memory MemorySaver would
# return an empty history after the restart.
#
# Usage:  BASE_URL=http://localhost:8000 ./scripts/demo_restart_durability.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
MARK="Falconry-$(python3 -c 'import uuid;print(uuid.uuid4().hex[:8])')"

SID=$(curl -s -X POST "$BASE_URL/api/sessions" -H 'content-type: application/json' -d '{}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo "session=$SID  marker=$MARK"

curl -s -X POST "$BASE_URL/api/sessions/$SID/messages" -H 'content-type: application/json' \
  -d "{\"content\":\"Please remember my project codename is $MARK.\"}" >/dev/null

check () {
  curl -s "$BASE_URL/api/sessions/$SID/messages" | python3 -c \
    "import sys,json; m=json.load(sys.stdin); print(f'  messages={len(m)}  marker_present='+str(any('$MARK' in (x.get('content') or '') for x in m)))"
}

echo "BEFORE restart:"; check
echo "restarting backend (all process memory wiped)..."
docker compose restart backend >/dev/null 2>&1
until curl -sf "$BASE_URL/api/readyz" >/dev/null 2>&1; do sleep 2; done
echo "AFTER restart (history reloaded from CockroachDB):"; check
