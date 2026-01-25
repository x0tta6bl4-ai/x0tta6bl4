# External Secrets Operator Configuration

## Overview
This document describes how to configure External Secrets Operator (ESO) for x0tta6bl4.

## Installation

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm repo update
helm install external-secrets external-secrets/external-secrets -n external-secrets --create-namespace
```

## SecretStore

Create a SecretStore for AWS Secrets Manager:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets-manager
  namespace: x0tta6bl4-production
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: eso-sa
```

## ExternalSecret

Create ExternalSecrets for application secrets:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: x0tta6bl4-secrets
  namespace: x0tta6bl4-production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: x0tta6bl4-secrets
    creationPolicy: Owner
  data:
  - secretKey: FLASK_SECRET_KEY
    remoteRef:
      key: x0tta6bl4/production
      property: FLASK_SECRET_KEY
  - secretKey: ADMIN_TOKEN
    remoteRef:
      key: x0tta6bl4/production
      property: ADMIN_TOKEN
  - secretKey: STRIPE_SECRET_KEY
    remoteRef:
      key: x0tta6bl4/production
      property: STRIPE_SECRET_KEY
```

## AWS IAM Role

Create IAM role for ESO:

```hcl
resource "aws_iam_role" "external_secrets" {
  name = "external-secrets-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRoleWithWebIdentity"
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.eks.arn
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "external_secrets_secrets" {
  role       = aws_iam_role.external_secrets.name
  policy_arn = "arn:aws:iam::aws:policy/SecretsManagerReadWrite"
}
```

## Service Account

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: eso-sa
  namespace: x0tta6bl4-production
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT_ID:role/external-secrets-role
```
