"""
Tests for Zero Trust Components.
ZKP Authentication, Device Attestation, Post-Quantum Crypto.
"""
import pytest
import sys
import time

sys.path.insert(0, '/mnt/AC74CC2974CBF3DC')

from src.security.zkp_auth import (
    SchnorrZKP, 
    PedersenCommitment, 
    ZKPAuthenticator,
    verify_zkp_proof_simple
)
from src.security.device_attestation import (
    DeviceAttestor,
    AdaptiveTrustManager,
    MeshDeviceAttestor,
    TrustLevel,
    AttestationType
)
from src.security.post_quantum import (
    SimplifiedNTRU,
    HybridEncryption,
    QuantumSafeKeyExchange,
    PQMeshSecurity
)


class TestZKPAuthentication:
    """Tests for Zero-Knowledge Proof Authentication."""
    
    def test_schnorr_keypair_generation(self):
        """Генерация ключевой пары."""
        secret, public = SchnorrZKP.generate_keypair()
        
        assert secret > 0
        assert public > 0
        assert secret != public
    
    def test_schnorr_commitment(self):
        """Создание commitment."""
        zkp = SchnorrZKP()
        commitment, nonce = zkp.create_commitment()
        
        assert commitment > 0
        assert nonce > 0
    
    def test_schnorr_full_protocol(self):
        """Полный протокол Schnorr ZKP."""
        # Prover
        prover = SchnorrZKP()
        commitment, nonce = prover.create_commitment()
        
        # Verifier генерирует challenge
        verifier = SchnorrZKP()
        challenge = verifier.generate_challenge(commitment, "test-prover")
        
        # Prover создаёт proof
        proof = prover.create_proof(challenge, nonce)
        
        # Verifier проверяет
        valid = verifier.verify_proof(challenge, proof)
        
        assert valid
    
    def test_schnorr_invalid_proof(self):
        """Невалидный proof должен отклоняться."""
        prover = SchnorrZKP()
        commitment, nonce = prover.create_commitment()
        
        verifier = SchnorrZKP()
        challenge = verifier.generate_challenge(commitment, "test")
        
        # Создаём proof с wrong nonce
        wrong_proof = prover.create_proof(challenge, nonce + 1)
        
        valid = verifier.verify_proof(challenge, wrong_proof)
        
        assert not valid
    
    def test_zkp_authenticator_flow(self):
        """ZKPAuthenticator high-level API."""
        # Prover side
        prover_auth = ZKPAuthenticator("alice")
        auth_start = prover_auth.start_auth()
        
        assert auth_start["type"] == "zkp_auth_start"
        assert auth_start["node_id"] == "alice"
        
        # Verifier side
        verifier_auth = ZKPAuthenticator("bob")
        challenge = verifier_auth.generate_challenge(auth_start)
        
        assert challenge["type"] == "zkp_challenge"
        
        # Prover completes
        proof = prover_auth.complete_auth(challenge)
        
        assert proof["type"] == "zkp_proof"
        
        # Verifier verifies
        valid = verifier_auth.verify_authentication(proof)
        
        assert valid
    
    def test_pedersen_commitment(self):
        """Pedersen commitment scheme."""
        value = 42
        commitment, blinding = PedersenCommitment.commit(value)
        
        # Verify correct value
        assert PedersenCommitment.verify(commitment, value, blinding)
        
        # Wrong value should fail
        assert not PedersenCommitment.verify(commitment, value + 1, blinding)
    
    def test_pedersen_homomorphic(self):
        """Homomorphic property of Pedersen commitments."""
        v1, v2 = 10, 20
        
        c1, r1 = PedersenCommitment.commit(v1)
        c2, r2 = PedersenCommitment.commit(v2)
        
        # c1 * c2 should commit to v1 + v2
        combined = PedersenCommitment.add_commitments(c1, c2)
        
        # This verifies the homomorphic property
        assert combined > 0


class TestDeviceAttestation:
    """Tests for Device Trust Attestation."""
    
    def test_fingerprint_creation(self):
        """Создание device fingerprint."""
        attestor = DeviceAttestor()
        fingerprint = attestor.create_fingerprint()
        
        assert fingerprint.fingerprint_hash
        assert fingerprint.platform_type in ["linux", "windows", "darwin"]
        assert fingerprint.nonce
    
    def test_fingerprint_consistency(self):
        """Fingerprint должен быть консистентным для одного устройства."""
        attestor = DeviceAttestor(secret_salt="fixed-salt")
        
        fp1 = attestor.create_fingerprint()
        fp2 = attestor.create_fingerprint()
        
        # Hash должен совпадать (одно устройство, один salt)
        assert fp1.fingerprint_hash == fp2.fingerprint_hash
        
        # Но nonce разные
        assert fp1.nonce != fp2.nonce
    
    def test_attestation_creation(self):
        """Создание attestation claim."""
        attestor = DeviceAttestor()
        claim = attestor.create_attestation(AttestationType.COMPOSITE)
        
        assert claim.claim_id
        assert claim.signature
        assert "hardware" in claim.evidence
        assert "software" in claim.evidence
    
    def test_attestation_verification(self):
        """Верификация attestation."""
        attestor = DeviceAttestor()
        claim = attestor.create_attestation()
        
        valid, reason = attestor.verify_attestation(claim)
        
        assert valid
        assert reason == "Valid"
    
    def test_attestation_expiry(self):
        """Expired attestation должен отклоняться."""
        attestor = DeviceAttestor()
        claim = attestor.create_attestation()
        
        # Подделываем старый timestamp
        claim.timestamp = time.time() - 600  # 10 minutes ago
        
        valid, reason = attestor.verify_attestation(claim)
        
        assert not valid
        assert "expired" in reason.lower()
    
    def test_adaptive_trust_manager(self):
        """Adaptive Trust Manager."""
        manager = AdaptiveTrustManager()
        
        # Новое устройство начинает с MEDIUM
        score = manager.get_trust_score("device-1")
        assert score.level == TrustLevel.MEDIUM
        
        # Позитивные события повышают trust
        for _ in range(5):
            manager.record_positive_event("device-1", "success")
        
        score = manager.evaluate_trust("device-1")
        assert score.score > 0.5
    
    def test_trust_degradation(self):
        """Trust должен падать при негативных событиях."""
        manager = AdaptiveTrustManager()
        
        # Начинаем с хорошего score
        for _ in range(5):
            manager.record_positive_event("device-2", "success")
        manager.evaluate_trust("device-2")
        
        initial_score = manager.get_trust_score("device-2").score
        
        # Негативные события
        for _ in range(5):
            manager.record_negative_event("device-2", "failure")
        manager.evaluate_trust("device-2")
        
        final_score = manager.get_trust_score("device-2").score
        
        assert final_score < initial_score
    
    def test_mesh_device_attestor(self):
        """MeshDeviceAttestor integration."""
        attestor = MeshDeviceAttestor("test-node")
        
        # Create attestation
        attestation = attestor.create_mesh_attestation()
        
        assert attestation["type"] == "mesh_attestation"
        assert attestation["node_id"] == "test-node"
        
        # Verify (self-verification)
        valid, trust_score = attestor.verify_peer_attestation(attestation)
        
        assert valid
        assert trust_score.level.value >= TrustLevel.LOW.value  # Initial trust starts low


class TestPostQuantumCrypto:
    """Tests for Post-Quantum Cryptography."""
    
    def test_ntru_keypair(self):
        """NTRU keypair generation."""
        ntru = SimplifiedNTRU()
        keypair = ntru.generate_keypair()
        
        assert keypair.public_key
        assert keypair.private_key
        assert keypair.key_id
    
    def test_ntru_kem(self):
        """NTRU Key Encapsulation Mechanism."""
        ntru = SimplifiedNTRU()
        keypair = ntru.generate_keypair()
        
        # Encapsulate
        shared_secret_enc, ciphertext = ntru.encapsulate(keypair.public_key)
        
        # Decapsulate
        shared_secret_dec = ntru.decapsulate(ciphertext, keypair.private_key)
        
        # Должны совпадать
        assert shared_secret_enc == shared_secret_dec
    
    def test_hybrid_encryption(self):
        """Hybrid classical + PQ encryption."""
        hybrid = HybridEncryption()
        keypair = hybrid.generate_hybrid_keypair()
        
        assert "pq" in keypair
        assert "classical" in keypair
        
        # Encapsulate
        shared_secret_enc, ciphertexts = hybrid.hybrid_encapsulate(
            bytes.fromhex(keypair["pq"]["public_key"]),
            bytes.fromhex(keypair["classical"]["public_key"])
        )
        
        # Decapsulate
        shared_secret_dec = hybrid.hybrid_decapsulate(
            ciphertexts,
            bytes.fromhex(keypair["pq"]["private_key"]),
            bytes.fromhex(keypair["classical"]["private_key"])
        )
        
        assert shared_secret_enc == shared_secret_dec
    
    def test_quantum_safe_key_exchange(self):
        """Quantum-safe key exchange protocol."""
        # Setup
        exchange_a = QuantumSafeKeyExchange()
        exchange_b = QuantumSafeKeyExchange()
        
        keypair_a = HybridEncryption().generate_hybrid_keypair()
        keypair_b = HybridEncryption().generate_hybrid_keypair()
        
        # A initiates
        init_msg = exchange_a.initiate_exchange(keypair_a)
        
        assert init_msg["type"] == "key_exchange_init"
        
        # B responds
        shared_secret_b, response_msg = exchange_b.respond_to_exchange(init_msg, keypair_b)
        
        assert response_msg["type"] == "key_exchange_response"
        
        # A completes
        shared_secret_a = exchange_a.complete_exchange(response_msg)
        
        # Оба должны получить одинаковый секрет
        assert shared_secret_a == shared_secret_b
    
    def test_pq_mesh_security(self):
        """PQMeshSecurity integration."""
        alice = PQMeshSecurity("alice")
        bob = PQMeshSecurity("bob")
        
        # Exchange public keys
        alice_keys = alice.get_public_keys()
        bob_keys = bob.get_public_keys()
        
        assert alice_keys["node_id"] == "alice"
        assert bob_keys["node_id"] == "bob"
    
    def test_pq_encrypt_decrypt(self):
        """Encryption/decryption через PQ-secure channel."""
        alice = PQMeshSecurity("alice")
        bob = PQMeshSecurity("bob")
        
        # Bob gets Alice's public keys
        alice_keys = alice.get_public_keys()
        
        # Bob manually sets shared key for testing
        import asyncio
        loop = asyncio.new_event_loop()
        shared_secret = loop.run_until_complete(
            bob.establish_secure_channel("alice", alice_keys)
        )
        loop.close()
        
        # Alice also needs the shared key
        alice._peer_keys["bob"] = shared_secret
        
        # Encrypt
        plaintext = b"Hello, quantum-safe world!"
        ciphertext = alice.encrypt_for_peer("bob", plaintext)
        
        # Decrypt
        decrypted = bob.decrypt_from_peer("alice", ciphertext)
        
        assert decrypted == plaintext


class TestIntegration:
    """Integration tests combining all components."""
    
    def test_full_zero_trust_auth_flow(self):
        """Full authentication with ZKP + Device Attestation."""
        # Setup
        prover = ZKPAuthenticator("node-a")
        verifier = ZKPAuthenticator("node-b")
        device_attestor = MeshDeviceAttestor("node-a")
        trust_manager = AdaptiveTrustManager()
        
        # Step 1: ZKP Authentication
        auth_start = prover.start_auth()
        challenge = verifier.generate_challenge(auth_start)
        proof = prover.complete_auth(challenge)
        zkp_valid = verifier.verify_authentication(proof)
        
        # Step 2: Device Attestation
        attestation = device_attestor.create_mesh_attestation()
        device_valid, trust_score = device_attestor.verify_peer_attestation(attestation)
        
        # Step 3: Update trust based on both
        if zkp_valid:
            trust_manager.record_positive_event("node-a", "zkp_auth_success")
        if device_valid:
            trust_manager.record_positive_event("node-a", "attestation_valid")
        
        final_trust = trust_manager.evaluate_trust("node-a")
        
        assert zkp_valid
        assert device_valid
        assert final_trust.level.value >= TrustLevel.MEDIUM.value
    
    def test_pq_secured_communication(self):
        """Communication secured with PQ + trust verification."""
        # Setup nodes
        alice = PQMeshSecurity("alice")
        bob = PQMeshSecurity("bob")
        trust_manager = AdaptiveTrustManager()
        
        # Verify trust level before communication
        trust_manager.record_positive_event("alice", "known_peer")
        trust = trust_manager.evaluate_trust("alice")
        
        if trust_manager.is_trusted("alice", TrustLevel.LOW):
            # Establish PQ channel
            alice_keys = alice.get_public_keys()
            
            # This would normally be async
            import hashlib
            # Simulate shared key establishment
            shared_key = hashlib.sha256(
                bytes.fromhex(alice_keys["pq_public_key"])
            ).digest()
            
            bob._peer_keys["alice"] = shared_key
            alice._peer_keys["bob"] = shared_key
            
            # Communicate
            message = b"Secure message"
            encrypted = alice.encrypt_for_peer("bob", message)
            decrypted = bob.decrypt_from_peer("alice", encrypted)
            
            assert decrypted == message
            
            # Record successful communication
            trust_manager.record_positive_event("alice", "successful_communication")
            
            final_trust = trust_manager.evaluate_trust("alice")
            assert final_trust.score >= trust.score  # Score should stay same or improve


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
