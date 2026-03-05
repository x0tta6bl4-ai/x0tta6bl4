import pytest
import logging
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from src.security.pqc.kem import PQCKeyExchange
from src.security.pqc.dsa import PQCDigitalSignature
from src.security.spiffe.production_integration import SPIREConfig, ProductionSPIREIntegration

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_self_signed_cert():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"x0tta6bl4-test-node"),
    ])
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow() - timedelta(days=1)
    ).not_valid_after(
        datetime.utcnow() + timedelta(days=10)
    ).sign(key, hashes.SHA256())

    return cert.public_bytes(serialization.Encoding.PEM), key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

class MockWorkloadAPI:
    async def fetch_x509_svid(self):
        cert, key = generate_self_signed_cert()
        class MockSVID:
            def __init__(self, c, k):
                self.cert = c
                self.private_key = k
        return MockSVID(cert, key)

@pytest.mark.asyncio
async def test_maas_pqc_microsegmentation_e2e(real_oqs):
    """
    E2E тест микросегментации MaaS с использованием PQC (Kyber768/Dilithium3).
    """
    logger.info("🚀 Запуск E2E теста MaaS PQC Micro-segmentation")

    # 1. SPIRE Identity
    config = SPIREConfig(trust_domain="x0tta6bl4.mesh")
    config.health_check_interval = 999999 
    
    spire_a = ProductionSPIREIntegration(config)
    spire_b = ProductionSPIREIntegration(config)
    mock_api = MockWorkloadAPI()
    
    await spire_a.initialize(workload_api_client=mock_api)
    await spire_b.initialize(workload_api_client=mock_api)

    # 2. PQC Initialization (Direct use of Kyber768/Dilithium3 as verified)
    kem_exchange = PQCKeyExchange(algorithm="Kyber768")
    dsa_signature = PQCDigitalSignature(algorithm="Dilithium3")

    if not kem_exchange.enabled or not dsa_signature.enabled:
        pytest.fail("PQC (liboqs) должен быть доступен, но он отключен в адаптере.")

    logger.info(f"🔑 Используем алгоритмы: {kem_exchange.algorithm} & {dsa_signature.algorithm}")

    # 3. KEM Handshake
    node_b_kem_keys = kem_exchange.generate_keypair()
    ciphertext, shared_secret_a = kem_exchange.encapsulate(node_b_kem_keys.public_key)
    shared_secret_b = kem_exchange.decapsulate(node_b_kem_keys.secret_key, ciphertext)

    assert shared_secret_a == shared_secret_b
    logger.info("🔐 PQC Shared Secret успешно согласован.")

    # 4. Message Signing (DSA)
    node_a_dsa_keys = dsa_signature.generate_keypair()
    message = b"MaaS-Command: Micro-segmentation-Update: Allow Node C"
    sig_obj = dsa_signature.sign(message, node_a_dsa_keys.secret_key)
    
    is_valid = dsa_signature.verify(message, sig_obj.signature_bytes, node_a_dsa_keys.public_key)
    assert is_valid is True
    logger.info("✅ Подпись Dilithium3 валидна.")

    # 5. Cleanup
    await spire_a.shutdown()
    await spire_b.shutdown()
    logger.info("🏁 E2E тест MaaS PQC завершен успешно.")
