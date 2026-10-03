#!/usr/bin/env bash
set -euo pipefail
: "${PUBLIC_HOSTNAME:?Set PUBLIC_HOSTNAME to your hostname}"
curl --fail --silent --show-error http://127.0.0.1:8080/ >/dev/null
curl --fail --silent --show-error "https://${PUBLIC_HOSTNAME}/" >/dev/null
printf 'Local origin and public website returned successful HTTP responses.\n'
