#!/bin/sh
# Install nginx from the official nginx.org apt repository, pinned to the given version.
#
# Used by two places in the Dockerfile so they cannot drift:
#   * CI-only  `nginx-probe` stage  -> proves a candidate version installs
#   * production stage              -> installs the locked version
#
# Usage: nginx-apt-install.sh <nginx-version>      e.g.  nginx-apt-install.sh 1.30.6
# The version is matched as `<version>-*` so the Debian revision (e.g. -1~bookworm)
# does not have to be tracked by hand.
set -eu

V="${1:?usage: nginx-apt-install.sh <nginx-version>}"
CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"
echo "== nginx-apt-install: codename=${CODENAME} version=${V} =="

apt-get update
apt-get install -y --no-install-recommends curl gnupg ca-certificates supervisor

curl -fsSL https://nginx.org/keys/nginx_signing.key \
  | gpg --dearmor -o /usr/share/keyrings/nginx-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] http://nginx.org/packages/debian ${CODENAME} nginx" \
  > /etc/apt/sources.list.d/nginx.list

apt-get update
apt-get install -y --no-install-recommends "nginx=${V}-*"

apt-get remove -y curl gnupg
apt-get autoremove -y
rm -rf /var/lib/apt/lists/*

nginx -v
