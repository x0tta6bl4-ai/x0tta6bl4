#!/usr/bin/env python3
"""
mTLS (mutual TLS) setup for x0tta6bl4 mesh communication
Generates certificates and configures secure communication
"""
import os
import subprocess
import datetime
from pathlib import Path
from typing import Dict, List, Optional
from utils.safe_subprocess import safe_run

class MTLSSetup:
    """mTLS certificate management for service mesh"""

    def __init__(self, certs_dir: str = "infrastructure/mtls/certs"):
        self.certs_dir = Path(certs_dir)
        self.certs_dir.mkdir(parents=True, exist_ok=True)

        # Certificate validity
        self.validity_days = 365
        self.key_size = 4096

        # Certificate subjects
        self.ca_subject = "/C=US/ST=CA/L=San Francisco/O=x0tta6bl4/CN=x0tta6bl4-CA"
        self.services = [
            "api-gateway",
            "quantum-service",
            "monitoring-service",
            "edge-ai-service",
            "payment-service",
            "registry-service"
        ]

    def generate_ca(self) -> bool:
        """Generate Certificate Authority"""
        ca_key = self.certs_dir / "ca.key"
        ca_cert = self.certs_dir / "ca.crt"

        if ca_cert.exists():
            print("CA certificate already exists")
            return True

        try:
            # Generate CA private key
            safe_run([
                "openssl", "genrsa",
                "-out", str(ca_key),
                str(self.key_size)
            ])

            # Generate CA certificate
            safe_run([
                "openssl", "req",
                "-new", "-x509",
                "-key", str(ca_key),
                "-out", str(ca_cert),
                "-days", str(self.validity_days),
                "-subj", self.ca_subject,
                "-extensions", "v3_ca",
                "-config", "/etc/ssl/openssl.cnf"  # Use system config
            ])

            print("✅ CA certificate generated")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to generate CA: {e}")
            return False

    def generate_service_cert(self, service_name: str) -> bool:
        """Generate certificate for specific service"""
        service_key = self.certs_dir / f"{service_name}.key"
        service_csr = self.certs_dir / f"{service_name}.csr"
        service_cert = self.certs_dir / f"{service_name}.crt"

        ca_key = self.certs_dir / "ca.key"
        ca_cert = self.certs_dir / "ca.crt"

        if not ca_cert.exists():
            print("CA certificate not found. Generate CA first.")
            return False

        if service_cert.exists():
            print(f"Certificate for {service_name} already exists")
            return True

        try:
            # Generate service private key
            safe_run([
                "openssl", "genrsa",
                "-out", str(service_key),
                str(self.key_size)
            ])

            # Generate certificate signing request
            service_subject = f"/C=US/ST=CA/L=San Francisco/O=x0tta6bl4/CN={service_name}"
            safe_run([
                "openssl", "req",
                "-new",
                "-key", str(service_key),
                "-out", str(service_csr),
                "-subj", service_subject
            ])

            # Sign certificate with CA
            safe_run([
                "openssl", "x509",
                "-req",
                "-in", str(service_csr),
                "-CA", str(ca_cert),
                "-CAkey", str(ca_key),
                "-CAcreateserial",
                "-out", str(service_cert),
                "-days", str(self.validity_days),
                "-extensions", "usr_cert",
                "-extfile", "/etc/ssl/openssl.cnf"
            ])

            # Clean up CSR
            service_csr.unlink(missing_ok=True)

            print(f"✅ Certificate generated for {service_name}")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to generate certificate for {service_name}: {e}")
            return False

    def generate_all_certs(self) -> bool:
        """Generate certificates for all services"""
        print("🔐 Setting up mTLS certificates...")

        if not self.generate_ca():
            return False

        success_count = 0
        for service in self.services:
            if self.generate_service_cert(service):
                success_count += 1

        print(f"✅ Generated certificates for {success_count}/{len(self.services)} services")
        return success_count == len(self.services)

    def create_kubernetes_secrets(self, namespace: str = "x0tta6bl4") -> bool:
        """Create Kubernetes secrets for certificates"""
        try:
            # Create CA secret
            safe_run([
                "kubectl", "create", "secret", "generic", "ca-certs",
                f"--namespace={namespace}",
                f"--from-file=ca.crt={self.certs_dir / 'ca.crt'}",
                "--dry-run=client", "-o", "yaml"
            ], capture_output=True)

            safe_run([
                "kubectl", "apply", "-f", "-"
            ], input="""apiVersion: v1
kind: Secret
metadata:
  name: ca-certs
  namespace: x0tta6bl4
type: Opaque
data:
  ca.crt: $(base64 -w 0 infrastructure/mtls/certs/ca.crt)
""")

            # Create service certificates
            for service in self.services:
                cert_file = self.certs_dir / f"{service}.crt"
                key_file = self.certs_dir / f"{service}.key"

                if cert_file.exists() and key_file.exists():
                    safe_run([
                        "kubectl", "create", "secret", "tls", f"{service}-tls",
                        f"--namespace={namespace}",
                        f"--cert={cert_file}",
                        f"--key={key_file}",
                        "--dry-run=client", "-o", "yaml"
                    ], capture_output=True)

                    safe_run([
                        "kubectl", "apply", "-f", "-"
                    ])

            print("✅ Kubernetes secrets created")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create Kubernetes secrets: {e}")
            return False

    def create_istio_config(self) -> bool:
        """Create Istio PeerAuthentication and DestinationRule for mTLS"""
        peer_auth = f"""
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: x0tta6bl4
spec:
  mtls:
    mode: STRICT
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: default
  namespace: x0tta6bl4
spec:
  host: "*.x0tta6bl4.svc.cluster.local"
  trafficPolicy:
    tls:
      mode: ISTIO_MUTUAL
"""

        config_file = self.certs_dir / "istio-mtls.yaml"
        with open(config_file, 'w') as f:
            f.write(peer_auth)

        try:
            safe_run([
                "kubectl", "apply", "-f", str(config_file)
            ])

            print("✅ Istio mTLS configuration applied")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to apply Istio config: {e}")
            return False

    def verify_certificates(self) -> Dict[str, bool]:
        """Verify all certificates are valid"""
        results = {}

        ca_cert = self.certs_dir / "ca.crt"
        if not ca_cert.exists():
            results["ca"] = False
            return results

        # Verify CA
        try:
            result = safe_run([
                "openssl", "x509", "-in", str(ca_cert), "-checkend", "0"
            ], capture_output=True)
            results["ca"] = result.returncode == 0
        except subprocess.CalledProcessError:
            results["ca"] = False

        # Verify service certificates
        for service in self.services:
            cert_file = self.certs_dir / f"{service}.crt"
            if cert_file.exists():
                try:
                    result = safe_run([
                        "openssl", "verify",
                        "-CAfile", str(ca_cert),
                        str(cert_file)
                    ], capture_output=True)
                    results[service] = result.returncode == 0
                except subprocess.CalledProcessError:
                    results[service] = False
            else:
                results[service] = False

        return results

    def setup_mesh_mtls(self) -> bool:
        """Complete mTLS setup for service mesh"""
        print("🔐 Setting up mTLS for service mesh...")

        # Generate all certificates
        if not self.generate_all_certs():
            return False

        # Verify certificates
        verification = self.verify_certificates()
        invalid_certs = [k for k, v in verification.items() if not v]

        if invalid_certs:
            print(f"❌ Invalid certificates: {invalid_certs}")
            return False

        print("✅ All certificates verified")

        # Create Kubernetes secrets
        if not self.create_kubernetes_secrets():
            return False

        # Apply Istio configuration
        if not self.create_istio_config():
            return False

        print("✅ mTLS setup complete for service mesh")
        return True

def main():
    """Main setup function"""
    mtls = MTLSSetup()

    if mtls.setup_mesh_mtls():
        print("\n🎉 mTLS configuration successful!")
        print("Services can now communicate securely using mutual TLS.")
    else:
        print("\n❌ mTLS setup failed. Check logs above.")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())