#!/bin/sh
# Run the brain pgTAP suite. Default target: the local Docker brain database.
# CI sets PSQL to a psql command for its service container.
set -eu
cd "$(dirname "$0")/.."
PSQL=${PSQL:-"docker exec -i fibonacci-local-brain-db-1 psql -U supabase_admin -d postgres"}
out=$($PSQL -X -q -At -v ON_ERROR_STOP=1 < tests/brain_rls.test.sql 2>&1) || { echo "$out"; exit 1; }
echo "$out" | grep -E "^(ok|not ok|#)" || true
passed=$(echo "$out" | grep -c "^ok " || true)
failed=$(echo "$out" | grep -c "^not ok" || true)
planned=$(echo "$out" | sed -n 's/^1\.\.\([0-9]*\)$/\1/p' | head -1)
echo "brain db tests: $passed passed, $failed failed, $planned planned"
[ "$failed" -eq 0 ] && [ "$passed" = "$planned" ]
