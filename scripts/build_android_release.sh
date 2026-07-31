#!/usr/bin/env bash
set -euo pipefail

SIGNING_ENV="${VOSK_SIGNING_ENV:-/home/openclaw/.openclaw/secrets/vosk-release/signing.env}"
EXPECTED_VERSION_NAME="0.1.0"
EXPECTED_VERSION_CODE="1"
EXPECTED_PACKAGE_NAME="org.vangelagency.strigmobile"

if [[ -f "${SIGNING_ENV}" ]]; then
  set +x
  # shellcheck disable=SC1090
  source "${SIGNING_ENV}"
fi

java_version="$(java -version 2>&1 | awk -F[\".] '/version/ {print $2; exit}')"
if [[ "${java_version}" != "17" ]]; then
  echo "JDK 17 is required for release build; detected major version: ${java_version:-unknown}" >&2
  exit 2
fi

actual_version_name="$(python3 - <<'PY'
from app_version import APP_VERSION_NAME
print(APP_VERSION_NAME)
PY
)"
actual_version_code="$(python3 - <<'PY'
from app_version import APP_VERSION_CODE
print(APP_VERSION_CODE)
PY
)"
spec_version_name="$(awk -F= '/^version[[:space:]]*=/{gsub(/[[:space:]]/, "", $2); print $2}' buildozer.spec)"
spec_version_code="$(awk -F= '/^android.numeric_version[[:space:]]*=/{gsub(/[[:space:]]/, "", $2); print $2}' buildozer.spec)"
spec_package_name="$(awk -F= '/^package.name[[:space:]]*=/{gsub(/[[:space:]]/, "", $2); print $2}' buildozer.spec)"
spec_package_domain="$(awk -F= '/^package.domain[[:space:]]*=/{gsub(/[[:space:]]/, "", $2); print $2}' buildozer.spec)"
actual_package_name="${spec_package_domain}.${spec_package_name}"

if [[ "${actual_version_name}" != "${EXPECTED_VERSION_NAME}" || "${spec_version_name}" != "${EXPECTED_VERSION_NAME}" ]]; then
  echo "Unexpected version_name: app=${actual_version_name}, buildozer=${spec_version_name}" >&2
  exit 2
fi

if [[ "${actual_version_code}" != "${EXPECTED_VERSION_CODE}" || "${spec_version_code}" != "${EXPECTED_VERSION_CODE}" ]]; then
  echo "Unexpected version_code: app=${actual_version_code}, buildozer=${spec_version_code}" >&2
  exit 2
fi

if [[ "${actual_package_name}" != "${EXPECTED_PACKAGE_NAME}" ]]; then
  echo "Unexpected package name: ${actual_package_name}" >&2
  exit 2
fi

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

apk_path="$(find bin -maxdepth 1 -type f -name '*.apk' -printf '%T@ %p\n' | sort -nr | awk 'NR==1 {print $2}')"
if [[ -z "${apk_path}" || ! -f "${apk_path}" ]]; then
  echo "Release APK was not found in bin/" >&2
  exit 2
fi

aapt_bin="$(find .buildozer/android/platform/android-sdk -type f -name aapt 2>/dev/null | head -1 || true)"
if [[ -n "${aapt_bin}" ]]; then
  apk_package="$("${aapt_bin}" dump badging "${apk_path}" | awk -F"'" '/^package:/{print $2; exit}')"
  if [[ "${apk_package}" != "${EXPECTED_PACKAGE_NAME}" ]]; then
    echo "Built APK package mismatch: ${apk_package}" >&2
    exit 2
  fi
else
  echo "Warning: aapt not found; package name could not be checked from APK" >&2
fi

apksigner_bin="$(find .buildozer/android/platform/android-sdk -type f -name apksigner 2>/dev/null | head -1 || true)"
if [[ -n "${apksigner_bin}" ]]; then
  "${apksigner_bin}" verify --print-certs "${apk_path}" >/tmp/vosk-apksigner-check.txt
  grep -q "Signer #1 certificate" /tmp/vosk-apksigner-check.txt || {
    echo "APK signature verification did not report signer certificate" >&2
    rm -f /tmp/vosk-apksigner-check.txt
    exit 2
  }
  rm -f /tmp/vosk-apksigner-check.txt
else
  jarsigner -verify "${apk_path}" >/dev/null
fi

sha256sum "${apk_path}"

unset P4A_RELEASE_KEYSTORE P4A_RELEASE_KEYSTORE_PASSWD P4A_RELEASE_KEYALIAS P4A_RELEASE_KEYALIAS_PASSWD
unset VOSK_KEYSTORE_PATH VOSK_KEYSTORE_PASSWORD VOSK_KEY_ALIAS VOSK_KEY_PASSWORD
