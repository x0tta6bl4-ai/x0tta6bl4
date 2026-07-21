#!/usr/bin/env python3
"""Test JWT-SVID issuance from SPIRE agent.

Verifies that:
1. SPIRE agent is reachable via socket
2. JWT-SVID can be fetched
3. JWT has correct issuer (https://spire.x0tta6bl4.mesh)
4. JWT has valid SPIFFE ID in subject
"""

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

SPIRE_AGENT_BIN = os.getenv("X0_SPIRE_AGENT_BIN", "/opt/spire/bin/spire-agent")
SPIRE_SOCKET = os.getenv("X0_SPIRE_SOCKET", "/opt/spire/sockets/agent.sock")
TRUST_DOMAIN = os.getenv("X0_TRUST_DOMAIN", "x0tta6bl4.mesh")
EXPECTED_ISSUER = f"https://spire.{TRUST_DOMAIN}"


def fetch_jwt_svid(audience: str = None) -> tuple[bool, str, dict | None]:
    """Fetch JWT-SVID from SPIRE agent and parse it."""
    if audience is None:
        audience = TRUST_DOMAIN

    if not Path(SPIRE_SOCKET).exists():
        return False, f"Socket not found: {SPIRE_SOCKET}", None

    try:
        result = subprocess.run(
            [
                SPIRE_AGENT_BIN, "api", "fetch",
                "-socketPath", SPIRE_SOCKET,
                "-jwt",
                "-audience", audience,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        return False, f"SPIRE agent binary not found: {SPIRE_AGENT_BIN}", None
    except subprocess.TimeoutExpired:
        return False, "SPIRE agent fetch timed out", None

    if result.returncode != 0:
        stderr = result.stderr.strip()[:200] if result.stderr else "no stderr"
        return False, f"spire-agent error (rc={result.returncode}): {stderr}", None

    output = result.stdout.strip()
    if not output:
        return False, "Empty response from spire-agent", None

    # Try to extract JWT token from output
    # spire-agent outputs: svid:<token> or just the token
    token = None
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("svid:"):
            token = line[5:]
            break
        if "." in line and len(line) > 50:
            token = line
            break

    if not token:
        return False, f"No JWT token found in response", None

    # Parse JWT (header.payload.signature)
    parts = token.split(".")
    if len(parts) != 3:
        return False, f"Invalid JWT format (parts={len(parts)})", None

    try:
        # Decode payload
        payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes)
    except Exception as e:
        return False, f"JWT decode error: {e}", None

    return True, "OK", payload


def validate_jwt(payload: dict) -> tuple[bool, list[str]]:
    """Validate JWT-SVID payload."""
    errors = []

    # Check issuer
    iss = payload.get("iss", "")
    if iss != EXPECTED_ISSUER:
        errors.append(f"iss mismatch: got '{iss}', expected '{EXPECTED_ISSUER}'")

    # Check subject (SPIFFE ID)
    sub = payload.get("sub", "")
    if not sub.startswith(f"spiffe://{TRUST_DOMAIN}/"):
        errors.append(f"sub is not a SPIFFE ID: '{sub}'")

    # Check audience
    aud = payload.get("aud", [])
    if isinstance(aud, str):
        aud = [aud]
    if not aud:
        errors.append("aud is empty")

    # Check expiry
    exp = payload.get("exp", 0)
    if exp:
        import time
        if exp < time.time():
            errors.append(f"JWT expired (exp={exp})")

    return len(errors) == 0, errors


def main():
    print(f"Testing JWT-SVID from SPIRE agent")
    print(f"  Socket: {SPIRE_SOCKET}")
    print(f"  Expected issuer: {EXPECTED_ISSUER}")
    print()

    ok, msg, payload = fetch_jwt_svid()
    if not ok:
        print(f"❌ Fetch failed: {msg}")
        sys.exit(1)

    print(f"✅ JWT-SVID fetched: {msg}")
    print()

    if payload:
        print("JWT payload:")
        for key in ["iss", "sub", "aud", "exp", "iat"]:
            if key in payload:
                print(f"  {key}: {payload[key]}")
        print()

        valid, errors = validate_jwt(payload)
        if valid:
            print("✅ JWT-SVID validation passed")
        else:
            print("❌ JWT-SVID validation failed:")
            for err in errors:
                print(f"  - {err}")
            sys.exit(1)

    print("All checks passed")
    sys.exit(0)


if __name__ == "__main__":
    main()
