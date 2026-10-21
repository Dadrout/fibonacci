#!/bin/sh
# LOCAL DEVELOPMENT ONLY. Runs once when the local brain database volume is created,
# after the supabase/postgres image's own setup (alphabetical order).
set -eu
psql -v ON_ERROR_STOP=1 -U supabase_admin -d postgres <<SQL
alter user authenticator with password '${POSTGRES_PASSWORD}';
SQL
for f in /brain-sql/local/00-storage-stub.sql /brain-sql/schema.sql /brain-sql/brain.sql /brain-sql/local/10-local-auth.sql; do
  psql -v ON_ERROR_STOP=1 -q -U supabase_admin -d postgres -f "$f"
done
