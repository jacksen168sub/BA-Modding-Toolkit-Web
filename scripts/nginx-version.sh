#!/bin/sh
# Print the nginx version locked in the Dockerfile.
#
# Single read path for every workflow: if the lock moves (Dockerfile ENV vs a
# separate file), only this script changes.
#
# Usage:
#   sh scripts/nginx-version.sh              # working tree
#   sh scripts/nginx-version.sh HEAD^        # any git ref, e.g. for "previous version"
#
# Prints an empty line and exits 0 when the version line cannot be found, so the
# caller (check_nginx_cves.py) can report it as a data error instead of dying
# inside `set -e` with no message.
set -eu

if [ $# -ge 1 ] && [ -n "$1" ]; then
  SRC="$(git show "$1:Dockerfile")"
else
  SRC="$(cat Dockerfile)"
fi

# Two patterns on purpose:
#   ENV NGINX_VERSION=1.30.6   current form
#   nginx=1.30.6-*             pre-migration form, needed when reading an older
#                              ref (e.g. the commit before the first auto-bump)
printf '%s\n' "$SRC" | grep -oP '(ENV NGINX_VERSION=|nginx=)\K[0-9.]+' | head -1 || true
