#!/bin/bash
# SPIRE CA Bootstrap Script
# Generates Root CA and Server CA for SPIRE deployment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CA_DIR="${SCRIPT_DIR}/../infra/security/ca"
TRUST_DOMAIN="${TRUST_DOMAIN:-x0tta6bl4.mesh}"

echo "=========================================="
echo "SPIRE CA Bootstrap"
echo "=========================================="
echo "Trust Domain: ${TRUST_DOMAIN}"
echo "CA Directory: ${CA_DIR}"
echo ""

# Create CA directory
mkdir -p "${CA_DIR}"

# Generate Root CA private key
echo "Generating Root CA private key..."
openssl genrsa -out "${CA_DIR}/root-ca.key" 4096

# Generate Root CA certificate
echo "Generating Root CA certificate..."
openssl req -new -x509 -days 3650 \
    -key "${CA_DIR}/root-ca.key" \
    -out "${CA_DIR}/root-ca.crt" \
    -subj "/C=US/O=x0tta6bl4/CN=${TRUST_DOMAIN} Root CA" \
    -extensions v3_ca \
    -config <(cat <<EOF
[req]
distinguished_name = req_distinguished_name
[req_distinguished_name]
[v3_ca]
basicConstraints = critical,CA:TRUE
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
EOF
)

# Generate Server CA private key
echo "Generating Server CA private key..."
openssl genrsa -out "${CA_DIR}/server-ca.key" 2048

# Generate Server CA certificate signing request
echo "Generating Server CA CSR..."
openssl req -new \
    -key "${CA_DIR}/server-ca.key" \
    -out "${CA_DIR}/server-ca.csr" \
    -subj "/C=US/O=x0tta6bl4/CN=${TRUST_DOMAIN} Server CA"

# Sign Server CA certificate with Root CA
echo "Signing Server CA certificate..."
openssl x509 -req -days 365 \
    -in "${CA_DIR}/server-ca.csr" \
    -CA "${CA_DIR}/root-ca.crt" \
    -CAkey "${CA_DIR}/root-ca.key" \
    -CAcreateserial \
    -out "${CA_DIR}/server-ca.crt" \
    -extensions v3_intermediate_ca \
    -extfile <(cat <<EOF
[v3_intermediate_ca]
basicConstraints = critical,CA:TRUE,pathlen:0
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer
EOF
)

# Create trust bundle (Root CA + Server CA)
echo "Creating trust bundle..."
cat "${CA_DIR}/root-ca.crt" "${CA_DIR}/server-ca.crt" > "${CA_DIR}/trust-bundle.pem"

# Set permissions
chmod 600 "${CA_DIR}/root-ca.key" "${CA_DIR}/server-ca.key"
chmod 644 "${CA_DIR}/root-ca.crt" "${CA_DIR}/server-ca.crt" "${CA_DIR}/server-ca.crt" "${CA_DIR}/trust-bundle.pem"

echo ""
echo "=========================================="
echo "CA Bootstrap Complete"
echo "=========================================="
echo "Root CA: ${CA_DIR}/root-ca.crt"
echo "Server CA: ${CA_DIR}/server-ca.crt"
echo "Trust Bundle: ${CA_DIR}/trust-bundle.pem"
echo ""
echo "⚠️  SECURITY WARNING:"
echo "   - Keep Root CA private key secure (${CA_DIR}/root-ca.key)"
echo "   - Do NOT commit private keys to git"
echo "   - Use KMS/Vault for production deployments"
echo ""

