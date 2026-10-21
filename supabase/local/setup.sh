#!/bin/sh
# Create .env.brain (git-ignored) with local-only secrets for the brain database stack.
# Safe to re-run: existing values are kept.
set -eu
cd "$(dirname "$0")/../.."
FILE=.env.brain
if [ -f "$FILE" ]; then echo "$FILE already exists; keeping it."; exit 0; fi
python3 - "$FILE" <<'PY'
import base64, hashlib, hmac, json, secrets, sys, time
def b64(data): return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
password = secrets.token_urlsafe(24)
jwt_secret = secrets.token_urlsafe(48)
def jwt(claims):
    head = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = b64(json.dumps(claims).encode())
    sig = hmac.new(jwt_secret.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest()
    return f"{head}.{body}.{b64(sig)}"
now = int(time.time())
service = jwt({"role": "service_role", "iss": "fibonacci-local", "iat": now, "exp": now + 10 * 365 * 86400})
lines = [
    "# Local-only secrets for the Fibonacci Brain database stack. Never commit.",
    f"POSTGRES_PASSWORD={password}",
    f"PGRST_DB_URI=postgres://authenticator:{password}@brain-db:5432/postgres",
    "PGRST_DB_SCHEMAS=public",
    "PGRST_DB_ANON_ROLE=anon",
    "PGRST_DB_EXTRA_SEARCH_PATH=public,extensions",
    f"PGRST_JWT_SECRET={jwt_secret}",
    "BRAIN_STORE=local",
    "BRAIN_LOCAL_REST_URL=http://brain-rest:3000",
    f"BRAIN_LOCAL_SERVICE_KEY={service}",
    f"BRAIN_MEDIA_SECRET={secrets.token_urlsafe(32)}",
    f"BRAIN_DEMO_TOKEN={secrets.token_urlsafe(32)}",
]
open(sys.argv[1], "w").write("\n".join(lines) + "\n")
PY
chmod 600 "$FILE"
echo "Created $FILE"
