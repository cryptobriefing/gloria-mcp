#!/usr/bin/env bash
#
# health-check.sh
#
# Asserts LIVENESS, not existence. This is the step the estate keeps not having:
# sibling services validate green while dead, because the deploy asserted that a
# process manager accepted a restart command rather than that the service works.
#
# FOUR ASSERTIONS, and the specific failure each one catches:
#
#   1. systemctl is-active == active
#      Catches: the unit failed to start at all (bad ExecStart, missing venv,
#      missing EnvironmentFile).
#
#   2. A REAL MCP `initialize` handshake over the streamable-http transport
#      returns HTTP 200 with a JSON-RPC result carrying serverInfo.
#      Catches: an ImportError or SyntaxError in synced source (the process
#      exits, the port closes, curl gets connection refused); a broken
#      dependency after a requirements change; a change to
#      TransportSecuritySettings that rejects the request; FastMCP failing to
#      register tools. A plain "is the port open" check would miss most of that,
#      and a plain GET / returns 404 by design on this server so it proves
#      nothing.
#
#   3. NRestarts did not increase during the health window.
#      Catches: the crash loop. The unit is Restart=on-failure/RestartSec=5, so
#      a service that starts, serves one request and dies is `active` again five
#      seconds later and looks perfectly healthy to a single point-in-time
#      check. systemd resets NRestarts on an explicit `systemctl restart`, so
#      after a deploy that restarted, the baseline is 0; after a deploy that
#      skipped the restart, the baseline is whatever it was. Comparing before to
#      after is correct in both cases.
#
#   4. systemctl is-active == active AFTER the settle window.
#      Catches: a delayed death that started after assertion 2 passed.
#
# THE HOST HEADER IS LOAD-BEARING. src/gloria_mcp/server.py enables DNS
# rebinding protection with allowed_hosts = ["mcp.itsgloria.ai", "localhost",
# "127.0.0.1"]. curl's default Host for a URL with an explicit port is
# "127.0.0.1:8005", which is NOT in that list: measured on the production host 2026-08-07,
# it returns HTTP 421 Misdirected Request. Sending `Host: localhost` returns
# 200. If you change allowed_hosts in server.py, change MCP_HOST_HEADER here in
# the same commit or every deploy fails.
#
# Run it by hand on the box any time:
#   cd "$APP_DIRECTORY" && ./scripts/health-check.sh

set -euo pipefail

UNIT="${APP_NAME:-gloria-mcp.service}"
PORT="${MCP_PORT:-8005}"
HOST_HEADER="${MCP_HOST_HEADER:-localhost}"
MCP_PATH="${MCP_PATH:-/mcp}"
ATTEMPTS="${HEALTH_ATTEMPTS:-6}"
SLEEP_BETWEEN="${HEALTH_SLEEP:-5}"
SETTLE="${HEALTH_SETTLE:-12}"

BODY_FILE="$(mktemp -t gloria-mcp-health.XXXXXX)"
trap 'rm -f "$BODY_FILE"' EXIT

show_unit_context() {
  systemctl status "$UNIT" --no-pager -l 2>&1 | tail -30 || true
  echo "--- last 40 journal lines ---"
  journalctl -u "$UNIT" -n 40 --no-pager 2>&1 | tail -40 || true
}

# --- 1. the unit is active ----------------------------------------------------

STATE="$(systemctl is-active "$UNIT" 2>&1 || true)"
if [ "$STATE" != "active" ]; then
  echo "ERROR: $UNIT is '$STATE' after the deploy, expected 'active'."
  show_unit_context
  exit 1
fi
echo "OK: $UNIT is active."

NR_BEFORE="$(systemctl show "$UNIT" -p NRestarts --value 2>/dev/null || echo 0)"
[ -n "$NR_BEFORE" ] || NR_BEFORE=0
echo "Baseline NRestarts=$NR_BEFORE"

# --- 2. a real MCP initialize handshake ---------------------------------------

REQUEST='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"deploy-health-check","version":"1"}}}'

CODE=000
for ATTEMPT in $(seq 1 "$ATTEMPTS"); do
  # `|| CODE=000` rather than `|| echo 000` inside the substitution: curl
  # already prints 000 on a transport failure, so appending another 000 would
  # produce the nonsense status "000000" in the log.
  CODE="$(curl -s -o "$BODY_FILE" -w '%{http_code}' --max-time 20 \
            -X POST \
            -H "Host: $HOST_HEADER" \
            -H 'Content-Type: application/json' \
            -H 'Accept: application/json, text/event-stream' \
            --data "$REQUEST" \
            "http://127.0.0.1:${PORT}${MCP_PATH}")" || CODE=000
  [ -n "$CODE" ] || CODE=000
  [ "$CODE" = "200" ] && break
  echo "  attempt $ATTEMPT: MCP initialize returned $CODE, retrying in ${SLEEP_BETWEEN}s"
  sleep "$SLEEP_BETWEEN"
done

if [ "$CODE" != "200" ]; then
  echo "ERROR: MCP initialize on http://127.0.0.1:${PORT}${MCP_PATH} returned HTTP $CODE after $ATTEMPTS attempts, expected 200."
  case "$CODE" in
    000) echo "       000 means nothing is listening on port $PORT: the process is not running." ;;
    421) echo "       421 means the Host header '$HOST_HEADER' is not in allowed_hosts in src/gloria_mcp/server.py." ;;
    406) echo "       406 means the Accept header was rejected. The transport requires 'application/json, text/event-stream'." ;;
    *)   echo "       See the body and the unit context below." ;;
  esac
  head -c 600 "$BODY_FILE" || true
  echo
  show_unit_context
  exit 1
fi

# The transport answers as SSE (text/event-stream) with the JSON-RPC result on a
# `data:` line, so parse by content rather than by assuming a JSON body.
if ! grep -q '"serverInfo"' "$BODY_FILE"; then
  echo "ERROR: MCP initialize returned 200 but the body carried no serverInfo. The transport answered; the MCP layer did not."
  head -c 600 "$BODY_FILE" || true
  echo
  show_unit_context
  exit 1
fi
if ! grep -q '"protocolVersion"' "$BODY_FILE"; then
  echo "ERROR: MCP initialize returned 200 and serverInfo but no protocolVersion. Malformed handshake."
  head -c 600 "$BODY_FILE" || true
  echo
  exit 1
fi
echo "OK: MCP initialize handshake succeeded on port $PORT."
echo "    $(grep -o '"serverInfo":{[^}]*}' "$BODY_FILE" | head -1)"

# --- 3 and 4. settle, then prove it did not crash-loop -------------------------

echo "Settling ${SETTLE}s to catch a crash loop (unit is Restart=on-failure, RestartSec=5)."
sleep "$SETTLE"

NR_AFTER="$(systemctl show "$UNIT" -p NRestarts --value 2>/dev/null || echo 0)"
[ -n "$NR_AFTER" ] || NR_AFTER=0
if [ "$NR_AFTER" -gt "$NR_BEFORE" ]; then
  echo "ERROR: $UNIT auto-restarted during the health window (NRestarts $NR_BEFORE -> $NR_AFTER). That is a crash loop, not a healthy service."
  show_unit_context
  exit 1
fi

STATE="$(systemctl is-active "$UNIT" 2>&1 || true)"
if [ "$STATE" != "active" ]; then
  echo "ERROR: $UNIT is '$STATE' after the settle window, expected 'active'."
  show_unit_context
  exit 1
fi

echo "OK: $UNIT still active, NRestarts unchanged at $NR_AFTER."
echo "HEALTH CHECK PASSED"
