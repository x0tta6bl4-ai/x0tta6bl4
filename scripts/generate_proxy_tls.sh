#!/usr/bin/env bash
set -euo pipefail

# Generate local self-signed TLS materials for deploy/proxy config.
OUT_DIR="${1:-deploy/proxy}"
DAYS="${2:-365}"
CERT_PATH="${OUT_DIR}/cert.pem"
KEY_PATH="${OUT_DIR}/key.pem"
SUBJECT="/C=US/ST=Local/L=Local/O=x0tta6bl4/OU=dev/CN=localhost"

if ! command -v openssl >/dev/null 2>&1; then
  echo "error: openssl is required" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"

if openssl req -x509 -newkey rsa:4096 -sha256 -nodes \
  -keyout "${KEY_PATH}" \
  -out "${CERT_PATH}" \
  -days "${DAYS}" \
  -subj "${SUBJECT}" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" >/dev/null 2>&1; then
  :
else
  echo "warning: OpenSSL without -addext support, generating cert without SAN" >&2
  openssl req -x509 -newkey rsa:4096 -sha256 -nodes \
    -keyout "${KEY_PATH}" \
    -out "${CERT_PATH}" \
    -days "${DAYS}" \
    -subj "${SUBJECT}" >/dev/null
fi

chmod 600 "${KEY_PATH}"
chmod 644 "${CERT_PATH}"

echo "generated:"
echo "  ${CERT_PATH}"
echo "  ${KEY_PATH}"
