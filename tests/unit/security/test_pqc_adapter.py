import pytest
import oqs
from src.security.pqc.pqc_adapter import PQCAdapter


@pytest.fixture
def adapter():
    """Фикстура для создания экземпляра PQCAdapter."""
    return PQCAdapter()

@pytest.fixture
def kyber_keypair():
    """Фикстура для генерации пары ключей Kyber."""
    with oqs.KeyEncapsulation("Kyber768") as kem:
        public_key = kem.generate_keypair()
        private_key = kem.export_secret_key()
        return public_key, private_key

@pytest.fixture
def dilithium_keypair():
    """Фикстура для генерации пары ключей Dilithium."""
    with oqs.Signature("ML-DSA-87") as sig:
        public_key = sig.generate_keypair()
        private_key = sig.export_secret_key()
        return public_key, private_key

class TestPQCAdapter:
    # --- Тесты для __init__ ---

    def test_init_default_algorithms(self, adapter):
        """Проверяет инициализацию с алгоритмами по умолчанию."""
        assert adapter.kem_alg == "Kyber768"
        assert adapter.sig_alg == "ML-DSA-87"

    def test_init_specified_algorithms(self):
        """Проверяет инициализацию с указанными алгоритмами."""
        adapter = PQCAdapter(kem_alg="Kyber512", sig_alg="ML-DSA-65")
        assert adapter.kem_alg == "Kyber512"
        assert adapter.sig_alg == "ML-DSA-65"

    def test_init_unsupported_kem_algorithm_raises_error(self):
        """Проверяет, что неподдерживаемый KEM-алгоритм вызывает RuntimeError."""
        with pytest.raises(RuntimeError, match="KEM-алгоритм UnsupportedKEM не поддерживается библиотекой OQS."):
            PQCAdapter(kem_alg="UnsupportedKEM")

    def test_init_unsupported_sig_algorithm_raises_error(self):
        """Проверяет, что неподдерживаемый алгоритм подписи вызывает RuntimeError."""
        with pytest.raises(RuntimeError, match="Алгоритм подписи UnsupportedSIG не поддерживается библиотекой OQS."):
            PQCAdapter(sig_alg="UnsupportedSIG")

    # --- Тесты для KEM (Kyber) ---

    def test_kem_generate_keypair(self, adapter):
        """Проверяет генерацию пары ключей Kyber."""
        public_key, private_key = adapter.kem_generate_keypair()
        assert isinstance(public_key, bytes)
        assert isinstance(private_key, bytes)
        assert len(public_key) > 0
        assert len(private_key) > 0

    def test_kem_encapsulate_decapsulate_end_to_end(self, adapter):
        """Проверяет инкапсуляцию и декапсуляцию Kyber в сквозном тесте."""
        public_key, private_key = adapter.kem_generate_keypair()
        ciphertext, shared_secret_sender = adapter.kem_encapsulate(public_key)
        shared_secret_receiver = adapter.kem_decapsulate(private_key, ciphertext)

        assert isinstance(ciphertext, bytes)
        assert isinstance(shared_secret_sender, bytes)
        assert isinstance(shared_secret_receiver, bytes)
        assert shared_secret_sender == shared_secret_receiver

    def test_kem_decapsulate_invalid_ciphertext_or_key(self, adapter, kyber_keypair):
        """Проверяет декапсуляцию с неверным шифротекстом или ключом."""
        public_key, private_key = kyber_keypair
        ciphertext, shared_secret_sender = adapter.kem_encapsulate(public_key)

        # Тест с измененным шифротекстом
        modified_ciphertext = ciphertext[:-1] + b'\x00' # Немного изменяем шифротекст
        shared_secret_receiver_modified = adapter.kem_decapsulate(private_key, modified_ciphertext)
        assert shared_secret_sender != shared_secret_receiver_modified

        # Тест с неверным приватным ключом (тот же шифротекст, но другой приватный ключ)
        _, wrong_private_key = adapter.kem_generate_keypair()
        shared_secret_receiver_wrong_key = adapter.kem_decapsulate(wrong_private_key, ciphertext)
        assert shared_secret_sender != shared_secret_receiver_wrong_key


    # --- Тесты для подписи (Dilithium) ---

    def test_sig_generate_keypair(self, adapter):
        """Проверяет генерацию пары ключей Dilithium."""
        public_key, private_key = adapter.sig_generate_keypair()
        assert isinstance(public_key, bytes)
        assert isinstance(private_key, bytes)
        assert len(public_key) > 0
        assert len(private_key) > 0

    def test_sig_sign_and_verify_valid_signature(self, adapter):
        """Проверяет подпись и верификацию действительной подписи Dilithium."""
        public_key, private_key = adapter.sig_generate_keypair()
        message = b"This is a test message."
        signature = adapter.sig_sign(private_key, message)

        assert isinstance(signature, bytes)
        assert len(signature) > 0
        assert adapter.sig_verify(public_key, message, signature) is True

    def test_sig_verify_invalid_message(self, adapter, dilithium_keypair):
        """Проверяет, что неверное сообщение не проходит верификацию."""
        public_key, private_key = dilithium_keypair
        original_message = b"This is the original message."
        modified_message = b"This is a tampered message."
        signature = adapter.sig_sign(private_key, original_message)

        assert adapter.sig_verify(public_key, modified_message, signature) is False

    def test_sig_verify_invalid_signature(self, adapter, dilithium_keypair):
        """Проверяет, что неверная подпись не проходит верификацию."""
        public_key, _ = dilithium_keypair
        message = b"Another test message."
        invalid_signature = b"malicious_signature" # Произвольная неверная подпись

        assert adapter.sig_verify(public_key, message, invalid_signature) is False

    def test_sig_verify_incorrect_public_key(self, adapter):
        """Проверяет, что неверный публичный ключ не проходит верификацию."""
        _, private_key = adapter.sig_generate_keypair()
        wrong_public_key, _ = adapter.sig_generate_keypair() # Генерируем другую пару ключей
        message = b"Message for verification with wrong key."
        signature = adapter.sig_sign(private_key, message)

        assert adapter.sig_verify(wrong_public_key, message, signature) is False

    def test_sig_verify_mechanism_not_supported_error_handling(self, adapter):
        """Проверяет обработку oqs.MechanismNotSupportedError в sig_verify."""
        # Для этого теста мы имитируем ситуацию, когда OQS не поддерживает механизм,
        # хотя в текущей реализации adapter.sig_verify это уже отлавливается.
        # Это, скорее, проверка на то, что `try-except` блок в adapter.sig_verify работает.
        public_key = b"dummy_pk"
        message = b"dummy_msg"
        signature = b"dummy_sig"

        # Создаем фиктивный объект Signature, который будет вызывать MechanismNotSupportedError
        class MockSignature:
            def __init__(self, alg, secret_key=None):
                pass
            def verify(self, msg, sig, pk):
                raise oqs.MechanismNotSupportedError("Mocked error")
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        # Временно заменяем oqs.Signature на MockSignature
        original_oqs_signature = oqs.Signature
        oqs.Signature = MockSignature
        try:
            assert adapter.sig_verify(public_key, message, signature) is False
        finally:
            oqs.Signature = original_oqs_signature # Восстанавливаем оригинальный oqs.Signature

