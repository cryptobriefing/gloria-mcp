#!/usr/bin/env bash
#
# check-env.sh
#
# Reads .env.example (the declared configuration schema) and asserts that every
# key it declares is present in the host .env. Hard-fails naming the missing
# keys.
#
# THREE PROPERTIES THAT MATTER, and the reason each is here:
#
#   1. It NEVER creates, deletes or overwrites .env. The host .env is the source
#      of truth and this script is a read-only consumer of it. On 2026-05-20 a
#      sibling repo's deploy carried a hardcoded `rm .env` followed by an `echo`
#      list, and it silently truncated a host env to a stale 15-key subset on
#      every run. Nothing in this repo's pipeline may write .env.
#   2. It runs BEFORE the restart, so the service is never restarted into an env
#      it cannot run on.
#   3. It names the missing keys, so the fix is obvious without reading the
#      workflow.
#
# KNOWN LIMITATION, stated so nobody is surprised: this tests presence, not
# non-emptiness. A key set to an empty string passes. That is deliberate;
# empty is a legitimate value for some flags. If a key must be non-empty, assert
# it in the service's own startup validation, not here.
#
# Run it by hand on the box after any manual intervention:
#   cd "$APP_DIRECTORY" && ./scripts/check-env.sh
#
# APP_DIRECTORY defaults to the current directory. THIS REPOSITORY IS PUBLIC,
# so the real runtime path is not committed here: it comes from the
# APP_DIRECTORY GitHub Actions variable, whose value lives in repo settings.

set -euo pipefail

APP_DIRECTORY="${APP_DIRECTORY:-$(pwd)}"
cd "$APP_DIRECTORY"

if [ ! -f .env.example ]; then
  echo "ERROR: .env.example not found in $APP_DIRECTORY. It is the declared schema and it is required."
  exit 1
fi

if [ ! -f .env ]; then
  echo "ERROR: $APP_DIRECTORY/.env does not exist."
  echo "This script does NOT create it. The host .env is the source of truth and only a human puts values in it."
  exit 1
fi

MISSING=""
for KEY in $(grep -oE '^[A-Za-z_][A-Za-z0-9_]*' .env.example | sort -u); do
  grep -qE "^${KEY}=" .env || MISSING="$MISSING $KEY"
done

if [ -n "$MISSING" ]; then
  echo "ERROR: host .env is missing key(s) declared in .env.example:$MISSING"
  echo "Deploy aborted. Add the missing key(s) to $APP_DIRECTORY/.env on the host."
  exit 1
fi

echo "OK: .env validation passed ($(grep -cE '^[A-Za-z_][A-Za-z0-9_]*=' .env) keys present)."
