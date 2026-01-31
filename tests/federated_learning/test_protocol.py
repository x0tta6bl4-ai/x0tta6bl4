"""
Тесты для протокола Federated Learning.

Покрывает:
- ModelWeights сериализация/десериализация
- ModelUpdate создание и валидация
- GlobalModel версионирование
- SignedMessage криптография
- FLMessage фабричные методы
"""
import pytest
import hashlib
import time
from unittest.mock import patch, MagicMock

from src.federated_learning.protocol import (
    ModelWeights,
    ModelUpdate,
    GlobalModel,
    AggregationResult,
    FLMessage,
    FLMessageType,
    SignedMessage,
    generate_keypair,
    PROTOCOL_VERSION,
)


class TestModelWeights:
    """Тесты для ModelWeights."""

    def test_create_empty_weights(self):
        """Создание пустых весов."""
        weights = ModelWeights()
        assert weights.layer_weights == {}
        assert weights.layer_biases == {}

    def test_create_with_data(self, simple_weights):
        """Создание весов с данными."""
        assert "layer1" in simple_weights.layer_weights
        assert "layer2" in simple_weights.layer_weights
        assert len(simple_weights.layer_weights["layer1"]) == 4

    def test_to_flat_vector(self, simple_weights):
        """Преобразование в плоский вектор."""
        flat = simple_weights.to_flat_vector()

        # layer1 weights (4) + layer1 biases (2) + layer2 weights (2) + layer2 biases (1) = 9
        expected_length = 4 + 2 + 2 + 1
        assert len(flat) == expected_length

    def test_flat_vector_preserves_values(self, simple_weights):
        """Плоский вектор сохраняет значения."""
        flat = simple_weights.to_flat_vector()

        # Первые элементы должны быть из layer1 weights
        assert flat[0] == 1.0
        assert flat[1] == 2.0

    def test_from_flat_vector_reconstruction(self, simple_weights):
        """Реконструкция из плоского вектора."""
        flat = simple_weights.to_flat_vector()

        # Определяем структуру слоёв
        layer_shapes = {
            "layer1": (4, 2),  # weights size, biases size
            "layer2": (2, 1)
        }

        reconstructed = ModelWeights.from_flat_vector(flat, layer_shapes)

        assert reconstructed.layer_weights["layer1"] == simple_weights.layer_weights["layer1"]
        assert reconstructed.layer_biases["layer1"] == simple_weights.layer_biases["layer1"]

    def test_compute_hash(self, simple_weights):
        """Вычисление хеша весов."""
        hash1 = simple_weights.compute_hash()

        # Хеш должен быть SHA256 hex (64 символа)
        assert len(hash1) == 64
        assert all(c in '0123456789abcdef' for c in hash1)

        # Тот же хеш при повторном вызове
        hash2 = simple_weights.compute_hash()
        assert hash1 == hash2

    def test_different_weights_different_hash(self, simple_weights, random_weights_factory):
        """Разные веса - разные хеши."""
        other_weights = random_weights_factory(seed=123)

        hash1 = simple_weights.compute_hash()
        hash2 = other_weights.compute_hash()

        assert hash1 != hash2


class TestModelUpdate:
    """Тесты для ModelUpdate."""

    def test_create_update(self, model_update_factory):
        """Создание обновления модели."""
        update = model_update_factory(node_id="test-node", round_number=5)

        assert update.node_id == "test-node"
        assert update.round_number == 5
        assert update.weights is not None

    def test_update_default_values(self, simple_weights):
        """Значения по умолчанию."""
        update = ModelUpdate(
            node_id="node-1",
            round_number=1,
            weights=simple_weights
        )

        assert update.num_samples == 0
        assert update.training_loss == 0.0
        assert update.noise_scale == 0.0
        assert update.clip_norm == 1.0

    def test_update_to_dict(self, model_update_factory):
        """Сериализация в словарь."""
        update = model_update_factory()
        data = update.to_dict()

        assert data["node_id"] == update.node_id
        assert data["round_number"] == update.round_number
        assert "weights" in data
        assert data["num_samples"] == update.num_samples

    def test_update_from_dict(self, model_update_factory):
        """Десериализация из словаря."""
        original = model_update_factory(node_id="original-node")
        data = original.to_dict()

        restored = ModelUpdate.from_dict(data)

        assert restored.node_id == original.node_id
        assert restored.round_number == original.round_number
        assert restored.num_samples == original.num_samples

    def test_update_timestamp_auto(self, simple_weights):
        """Timestamp устанавливается автоматически."""
        before = time.time()
        update = ModelUpdate(
            node_id="node-1",
            round_number=1,
            weights=simple_weights
        )
        after = time.time()

        assert before <= update.timestamp <= after


class TestGlobalModel:
    """Тесты для GlobalModel."""

    def test_create_global_model(self, simple_weights):
        """Создание глобальной модели."""
        model = GlobalModel(
            version=1,
            round_number=5,
            weights=simple_weights,
            num_contributors=10,
            aggregation_method="krum"
        )

        assert model.version == 1
        assert model.round_number == 5
        assert model.num_contributors == 10
        assert model.aggregation_method == "krum"

    def test_auto_hash_computation(self, simple_weights):
        """Автоматическое вычисление хеша."""
        model = GlobalModel(
            version=1,
            round_number=1,
            weights=simple_weights
        )

        # Хеш должен быть вычислен автоматически
        assert model.weights_hash != ""
        assert model.weights_hash == simple_weights.compute_hash()

    def test_global_model_to_dict(self, initial_global_model):
        """Сериализация в словарь."""
        data = initial_global_model.to_dict()

        assert data["version"] == 0
        assert data["round_number"] == 0
        assert "weights" in data
        assert "weights_hash" in data

    def test_global_model_from_dict(self, initial_global_model):
        """Десериализация из словаря."""
        data = initial_global_model.to_dict()
        restored = GlobalModel.from_dict(data)

        assert restored.version == initial_global_model.version
        assert restored.weights_hash == initial_global_model.weights_hash

    def test_chain_integrity(self, simple_weights):
        """Цепочка хешей для целостности."""
        model1 = GlobalModel(
            version=1,
            round_number=1,
            weights=simple_weights
        )

        model2 = GlobalModel(
            version=2,
            round_number=2,
            weights=simple_weights,
            previous_hash=model1.weights_hash
        )

        assert model2.previous_hash == model1.weights_hash


class TestAggregationResult:
    """Тесты для AggregationResult."""

    def test_successful_result(self, initial_global_model):
        """Успешный результат агрегации."""
        result = AggregationResult(
            success=True,
            global_model=initial_global_model,
            updates_received=5,
            updates_accepted=5
        )

        assert result.success is True
        assert result.updates_received == 5
        assert result.error_message == ""

    def test_failed_result(self):
        """Неуспешный результат агрегации."""
        result = AggregationResult(
            success=False,
            error_message="Not enough participants"
        )

        assert result.success is False
        assert result.global_model is None
        assert "Not enough" in result.error_message

    def test_byzantine_detection(self, initial_global_model):
        """Результат с обнаруженными Byzantine нодами."""
        result = AggregationResult(
            success=True,
            global_model=initial_global_model,
            updates_received=5,
            updates_accepted=4,
            updates_rejected=1,
            suspected_byzantine=["malicious-node"]
        )

        assert len(result.suspected_byzantine) == 1
        assert result.updates_rejected == 1

    def test_to_dict(self, initial_global_model):
        """Сериализация результата."""
        result = AggregationResult(
            success=True,
            global_model=initial_global_model,
            aggregation_time_seconds=1.5
        )

        data = result.to_dict()
        assert data["success"] is True
        assert data["aggregation_time_seconds"] == 1.5
        assert data["global_model"] is not None


class TestFLMessage:
    """Тесты для FLMessage."""

    def test_round_start_message(self, initial_global_model):
        """Создание сообщения начала раунда."""
        msg = FLMessage.round_start(round_number=5, global_model=initial_global_model)

        assert msg.msg_type == FLMessageType.ROUND_START
        assert msg.content["round_number"] == 5
        assert "global_model" in msg.content

    def test_local_update_message(self, model_update_factory):
        """Создание сообщения локального обновления."""
        update = model_update_factory(node_id="worker-1")
        msg = FLMessage.local_update(update)

        assert msg.msg_type == FLMessageType.LOCAL_UPDATE
        assert msg.sender == "worker-1"
        assert "update" in msg.content

    def test_global_update_message(self, initial_global_model):
        """Создание сообщения глобального обновления."""
        msg = FLMessage.global_update(initial_global_model)

        assert msg.msg_type == FLMessageType.GLOBAL_UPDATE
        assert "global_model" in msg.content

    def test_heartbeat_message(self):
        """Создание heartbeat сообщения."""
        status = {"training_loss": 0.5, "memory_usage": 0.7}
        msg = FLMessage.heartbeat("node-1", status)

        assert msg.msg_type == FLMessageType.HEARTBEAT
        assert msg.sender == "node-1"
        assert msg.content["status"] == status

    def test_error_message(self):
        """Создание сообщения об ошибке."""
        msg = FLMessage.error(
            error_code="INVALID_UPDATE",
            message="Update validation failed",
            details={"reason": "gradient too large"}
        )

        assert msg.msg_type == FLMessageType.ERROR
        assert msg.content["error_code"] == "INVALID_UPDATE"


class TestSignedMessage:
    """Тесты для SignedMessage."""

    def test_generate_keypair(self):
        """Генерация ключевой пары."""
        private_key, public_key = generate_keypair()

        # Ed25519 ключи: 32 байта каждый
        assert len(private_key) == 32
        assert len(public_key) == 32

    def test_sign_and_verify(self):
        """Подпись и верификация сообщения."""
        private_key, public_key = generate_keypair()

        msg = SignedMessage(
            message_id="msg-001",
            sender_id="node-1",
            message_type=FLMessageType.LOCAL_UPDATE,
            payload={"data": "test"}
        )

        # Подписываем
        msg.sign(private_key)

        # Проверяем
        assert msg.verify() is True

    def test_verify_fails_with_wrong_key(self):
        """Верификация не проходит с неправильным ключом."""
        private_key1, _ = generate_keypair()
        _, public_key2 = generate_keypair()

        msg = SignedMessage(
            message_id="msg-002",
            sender_id="node-2",
            message_type=FLMessageType.HEARTBEAT,
            payload={}
        )

        msg.sign(private_key1)

        # Проверяем с другим публичным ключом
        assert msg.verify(public_key2) is False

    def test_verify_fails_if_tampered(self):
        """Верификация не проходит при изменении данных."""
        private_key, _ = generate_keypair()

        msg = SignedMessage(
            message_id="msg-003",
            sender_id="node-3",
            message_type=FLMessageType.VOTE,
            payload={"vote": "yes"}
        )

        msg.sign(private_key)

        # Меняем payload после подписи
        msg.payload["vote"] = "no"

        assert msg.verify() is False

    def test_serialization_roundtrip(self):
        """Сериализация и десериализация."""
        import src.federated_learning.protocol as protocol_module

        # Используем JSON fallback вместо замоканного msgpack
        original_has_msgpack = getattr(protocol_module, 'HAS_MSGPACK', False)
        protocol_module.HAS_MSGPACK = False

        try:
            private_key, _ = generate_keypair()

            original = SignedMessage(
                message_id="msg-004",
                sender_id="node-4",
                message_type=FLMessageType.COMMIT,
                payload={"commit_hash": "abc123"}
            )
            original.sign(private_key)

            # Сериализуем
            data = original.to_bytes()

            # Десериализуем
            restored = SignedMessage.from_bytes(data)

            assert restored.message_id == original.message_id
            assert restored.sender_id == original.sender_id
            assert restored.payload == original.payload
            assert restored.verify() is True
        finally:
            # Восстанавливаем оригинальное значение
            protocol_module.HAS_MSGPACK = original_has_msgpack

    def test_protocol_version_included(self):
        """Версия протокола включена в сообщение."""
        msg = SignedMessage(
            message_id="msg-005",
            sender_id="node-5",
            message_type=FLMessageType.STATUS_REQUEST,
            payload={}
        )

        assert msg.protocol_version == PROTOCOL_VERSION


class TestFLMessageType:
    """Тесты для типов сообщений."""

    def test_all_message_types_defined(self):
        """Все типы сообщений определены."""
        types = [t.value for t in FLMessageType]

        assert "round_start" in types
        assert "local_update" in types
        assert "global_update" in types
        assert "heartbeat" in types
        assert "error" in types
        assert "prepare" in types
        assert "commit" in types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
