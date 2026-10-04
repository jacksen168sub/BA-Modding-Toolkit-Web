#!/bin/sh
# Renders the pristine frontend template into the nginx web root at every container start,
# injecting operator-supplied HTML into the page. Re-rendering from the template keeps this
# idempotent: change the injection, restart the container, and the new content takes effect.
# With nothing configured this is a plain copy.
set -e

TEMPLATE_DIR=/opt/frontend-template
WEB_ROOT=/var/www/html

if [ -d "$TEMPLATE_DIR" ]; then
    mkdir -p "$WEB_ROOT"
    cp -a "$TEMPLATE_DIR"/. "$WEB_ROOT"/

    python - "$WEB_ROOT/index.html" <<'PY'
import os
import sys
from pathlib import Path

index = Path(sys.argv[1])
if not index.is_file():
    sys.exit(0)


def load(name: str) -> str:
    """Read the injection for `name` (head/body).

    A file wins over an env var, because multi-line HTML is painful to escape in a shell
    or compose file. File defaults to /app/data/inject-<name>.html (override with
    INJECT_<NAME>_FILE); the env-var fallback is INJECT_<NAME>_HTML.
    """
    path = Path(os.environ.get(f"INJECT_{name.upper()}_FILE", f"/app/data/inject-{name}.html"))
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return os.environ.get(f"INJECT_{name.upper()}_HTML", "")


html = index.read_text(encoding="utf-8")
for name, marker in (("head", "<!-- INJECT_HEAD -->"), ("body", "<!-- INJECT_BODY -->")):
    payload = load(name)
    if payload:
        html = html.replace(marker, payload)
index.write_text(html, encoding="utf-8")
PY
fi

exec "$@"
