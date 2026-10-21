#!/bin/sh
# Re-apply brain.sql (idempotent) to the running local brain database and reload PostgREST.
set -eu
cd "$(dirname "$0")/.."
DB=${BRAIN_DB_CONTAINER:-talespark-local-brain-db-1}
for f in brain.sql local/10-local-auth.sql; do
  docker exec -i "$DB" psql -v ON_ERROR_STOP=1 -q -U supabase_admin -d postgres < "$f"
done
docker exec -i "$DB" psql -q -U supabase_admin -d postgres -c "notify pgrst, 'reload schema'"
echo "brain.sql applied to $DB"
