#!/usr/bin/env bash
set -euo pipefail

missing=0
for var in VOSK_KEYSTORE_PATH VOSK_KEYSTORE_PASSWORD VOSK_KEY_ALIAS VOSK_KEY_PASSWORD; do
  if [[ -z "${!var:-}" ]]; then
    echo "Missing required environment variable: ${var}" >&2
    missing=1
  fi
done

if [[ "${missing}" -ne 0 ]]; then
  exit 2
fi

if [[ ! -f "${VOSK_KEYSTORE_PATH}" ]]; then
  echo "Keystore not found: ${VOSK_KEYSTORE_PATH}" >&2
  exit 2
fi

export P4A_RELEASE_KEYSTORE="${VOSK_KEYSTORE_PATH}"
export P4A_RELEASE_KEYSTORE_PASSWD="${VOSK_KEYSTORE_PASSWORD}"
export P4A_RELEASE_KEYALIAS="${VOSK_KEY_ALIAS}"
export P4A_RELEASE_KEYALIAS_PASSWD="${VOSK_KEY_PASSWORD}"

buildozer android release

