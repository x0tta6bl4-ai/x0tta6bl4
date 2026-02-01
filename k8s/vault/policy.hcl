# Vault Policy for proxy-api role
# This policy defines the permissions for the proxy-api application

# Allow reading proxy secrets
path "secret/data/proxy/*" {
  capabilities = ["read", "list"]
}

# Allow reading database credentials
path "secret/data/proxy/database/*" {
  capabilities = ["read"]
}

# Allow reading API keys
path "secret/data/proxy/api-keys/*" {
  capabilities = ["read"]
}

# Allow reading certificates
path "secret/data/proxy/certificates/*" {
  capabilities = ["read"]
}

# Allow reading tokens
path "secret/data/proxy/tokens/*" {
  capabilities = ["read"]
}

# Allow reading encryption keys
path "secret/data/proxy/encryption/*" {
  capabilities = ["read"]
}

# Allow checking Vault health
path "sys/health" {
  capabilities = ["read"]
}

# Allow checking seal status
path "sys/seal-status" {
  capabilities = ["read"]
}

# Deny access to all other paths
path "*" {
  capabilities = ["deny"]
}