# Pip-Audit Security Report

**Scan Date:** 2025-12-20

This report summarizes the findings from the `pip-audit` scan on the project's dependencies.

## Summary

**15 known vulnerabilities found in 10 packages.**

The local dependency `x0tta6bl4` was not audited as it is not on PyPI.

---

## Vulnerability Details

| Package          | Installed Version | Vulnerability ID  | Fix Versions |
|------------------|-------------------|-------------------|--------------|
| brotli           | 1.1.0             | CVE-2025-6176     | 1.2.0        |
| ecdsa            | 0.19.1            | CVE-2024-23342    | _N/A_        |
| filelock         | 3.20.0            | CVE-2025-68146    | 3.20.1       |
| fonttools        | 4.60.1            | CVE-2025-66034    | 4.60.2       |
| python-jose      | 3.3.0             | PYSEC-2024-232    | 3.4.0        |
| python-jose      | 3.3.0             | PYSEC-2024-233    | 3.4.0        |
| python-multipart | 0.0.6             | CVE-2024-24762    | 0.0.7        |
| python-multipart | 0.0.6             | CVE-2024-53981    | 0.0.18       |
| scapy            | 2.6.1             | GHSA-cq46-m9x9-j8w2 | _N/A_        |
| starlette        | 0.48.0            | CVE-2025-62727    | 0.49.1       |
| urllib3          | 2.3.0             | CVE-2025-50182    | 2.5.0        |
| urllib3          | 2.3.0             | CVE-2025-50181    | 2.5.0        |
| urllib3          | 2.3.0             | CVE-2025-66418    | 2.6.0        |
| urllib3          | 2.3.0             | CVE-2025-66471    | 2.6.0        |
| werkzeug         | 3.1.3             | CVE-2025-66221    | 3.1.4        |

---

## Recommendations

The next step should be to update these dependencies to the "Fix Versions" listed above. This can be done by modifying the `pyproject.toml` file and then running `pip install -e ".[all]"` again.

**Priority:** Updating these dependencies should be considered a high priority to mitigate security risks.
