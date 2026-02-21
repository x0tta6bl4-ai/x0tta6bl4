# Proxy TLS Materials

`cert.pem` and `key.pem` are intentionally not stored in Git.

Generate local development TLS files:

```bash
bash scripts/generate_proxy_tls.sh
```

Custom output directory and certificate lifetime:

```bash
bash scripts/generate_proxy_tls.sh deploy/proxy 365
```

The default `deploy/proxy/config.yaml` expects:

- `deploy/proxy/cert.pem`
- `deploy/proxy/key.pem`
