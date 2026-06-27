# Security Gates Production Boundary

This package is ready for client CI installation only after
`scripts/agents/verify_security_gates_release.py` returns
`READY_FOR_CLIENT_REPO_INSTALL`.

## What It Proves

- Required template files exist.
- Required snippets are present.
- The scanner has valid Bash syntax.
- A fake Trivy run can produce JSON and HTML artifacts.
- Unit tests pass.
- Claim-hygiene scan passes for the active claim surface.

## What It Does Not Prove

- A client environment has configured Snyk credentials.
- A client environment has a real container image to scan.
- Any repository has zero vulnerabilities.
- Ghost Access, SPB, NL, or other external runtimes are production-ready.
