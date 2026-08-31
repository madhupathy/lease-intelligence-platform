#!/bin/sh
set -eu

PORT="${PORT:-8081}"
MAX_ATTEMPTS="${DB_VALIDATE_MAX_ATTEMPTS:-5}"
DELAY_SEC="${DB_VALIDATE_RETRY_DELAY_SEC:-30}"

attempt=1
while [ "${attempt}" -le "${MAX_ATTEMPTS}" ]; do
  echo "Starting risk-engine (attempt ${attempt}/${MAX_ATTEMPTS}) on port ${PORT}..."
  set +e
  java -jar app.jar
  exit_code=$?
  set -e

  if [ "${exit_code}" -eq 0 ]; then
    exit 0
  fi

  if [ "${attempt}" -eq "${MAX_ATTEMPTS}" ]; then
    echo "risk-engine failed after ${MAX_ATTEMPTS} attempts (last exit=${exit_code})"
    exit "${exit_code}"
  fi

  echo "Startup failed (likely schema validate before migrations); retrying in ${DELAY_SEC}s..."
  sleep "${DELAY_SEC}"
  attempt=$((attempt + 1))
done

exit 1
