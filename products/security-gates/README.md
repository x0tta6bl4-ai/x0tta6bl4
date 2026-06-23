# Security Gates

Security Gates is a client-repo template package for Snyk and Trivy scanning.
It includes CI snippets plus a local scanner that writes JSON and HTML evidence
under `scan-results/`.

## Local Use

```bash
bash templates/security/security-scan.sh --trivy --severity HIGH --image demo-image:latest
```

## Release Check

```bash
python3 scripts/agents/verify_security_gates_release.py --json
```

The release decision covers template install readiness only. It does not prove
that this repository or a client repository has zero vulnerabilities.
