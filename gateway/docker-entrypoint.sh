#!/bin/sh
set -eu

: "${PORT:=8080}"
: "${EXTRACTION_UPSTREAM:=extraction:8000}"
: "${RISK_ENGINE_UPSTREAM:=risk-engine:8081}"

export PORT EXTRACTION_UPSTREAM RISK_ENGINE_UPSTREAM

envsubst '${PORT} ${EXTRACTION_UPSTREAM} ${RISK_ENGINE_UPSTREAM}' \
  < /etc/nginx/nginx.conf.template \
  > /etc/nginx/nginx.conf

exec nginx -g 'daemon off;'
