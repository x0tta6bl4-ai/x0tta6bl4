"""
E2E интеграционные тесты для полного pipeline x0tta6bl4.
Проверяет работу всех модулей вместе:
- Obfuscation (FakeTLS, Shadowsocks, XOR)
- Traffic Shaping
- NodeManager
- DAO Governance
- Metrics
"""

import json
import sys
import time

import pytest

sys.path.insert(0, "/mnt/AC74CC2974CBF3DC")

from src.dao.governance import GovernanceEngine, VoteType
from src.network.batman.node_manager import NodeManager
from src.network.obfuscation import (TrafficAnalyzer, TrafficProfile,
                                     TrafficShaper, TransportManager)


class TestFullPipeline:
    """E2E тесты полного pipeline."""

    def test_obfuscation_plus_shaping_roundtrip(self):
        """Данные проходят через obfuscation + shaping и обратно."""
        # Настройка
        transport = TransportManager.create("xor", key="test-key-123")
        shaper = TrafficShaper(TrafficProfile.VIDEO_STREAMING)

        original_data = b"Hello, x0tta6bl4 mesh network! This is a test message."

        # Прямой путь: data -> obfuscate -> shape
        obfuscated = transport.obfuscate(original_data)
        shaped = shaper.shape_packet(obfuscated)

        # Обратный путь: unshape -> deobfuscate
        unshaped = shaper.unshape_packet(shaped)
        recovered = transport.deobfuscate(unshaped)

        assert recovered == original_data, "Данные должны восстановиться полностью"

    def test_faketls_plus_voice_profile(self):
        """FakeTLS + voice_call профиль для VoIP трафика."""
        transport = TransportManager.create("faketls", sni="voice.signal.org")
        shaper = TrafficShaper(TrafficProfile.VOICE_CALL)

        # Симулируем VoIP пакеты
        voice_packets = [b"x" * 160 for _ in range(10)]  # Opus codec ~160 bytes

        for packet in voice_packets:
            # Обфускация
            obfuscated = transport.obfuscate(packet)

            # Шейпинг
            shaped = shaper.shape_packet(obfuscated)

            # Проверяем размер (voice_call паддит до 200 + 2 prefix)
            # Но obfuscated больше из-за TLS overhead
            assert (
                len(shaped) >= 202
            ), f"Размер должен быть минимум 202, got {len(shaped)}"

            # Roundtrip
            unshaped = shaper.unshape_packet(shaped)
            recovered = transport.deobfuscate(unshaped)

            assert recovered == packet

    def test_shadowsocks_plus_file_download(self):
        """Shadowsocks + file_download для максимального throughput."""
        transport = TransportManager.create("shadowsocks", password="secure-pass-456")
        shaper = TrafficShaper(TrafficProfile.FILE_DOWNLOAD)

        # Большой блок данных
        large_data = bytes(range(256)) * 5  # 1280 bytes

        obfuscated = transport.obfuscate(large_data)
        shaped = shaper.shape_packet(obfuscated)

        # file_download паддит до 1460
        assert len(shaped) >= 1460

        # Roundtrip
        unshaped = shaper.unshape_packet(shaped)
        recovered = transport.deobfuscate(unshaped)

        assert recovered == large_data

    def test_node_manager_with_all_features(self):
        """NodeManager с obfuscation + shaping + DAO."""
        transport = TransportManager.create("xor", key="mesh-key")

        nm = NodeManager(
            mesh_id="test-mesh",
            local_node_id="node-alpha",
            obfuscation_transport=transport,
            traffic_profile="gaming",
        )

        # Проверяем инициализацию
        assert nm.traffic_shaper is not None
        assert nm.governance is not None
        assert nm.obfuscation_transport is not None

        # Тест heartbeat
        result = nm.send_heartbeat("node-beta")
        assert result is True

        # Тест topology update
        result = nm.send_topology_update("node-beta", {"links": ["node-gamma"]})
        assert result is True

        # Тест DAO proposal
        proposal_id = nm.propose_network_update(
            title="Добавить новый узел",
            action={"type": "add_node", "node_id": "node-delta"},
        )
        assert proposal_id is not None

        # Тест голосования
        vote_result = nm.vote_on_proposal(proposal_id, "yes")
        assert vote_result is True

    def test_traffic_analyzer_with_shaped_traffic(self):
        """TrafficAnalyzer правильно анализирует shaped трафик."""
        shaper = TrafficShaper(TrafficProfile.VIDEO_STREAMING)
        analyzer = TrafficAnalyzer()

        # Генерируем и анализируем 100 пакетов
        for i in range(100):
            data = bytes([i % 256] * (100 + i * 10))
            shaped = shaper.shape_packet(data)
            analyzer.record_packet(len(shaped))

        stats = analyzer.get_statistics()

        assert stats["packets"] == 100
        assert stats["avg_size"] >= 1460  # video_streaming паддит до 1460
        assert stats["min_size"] >= 1460
        assert stats["max_size"] <= 1470  # С prefix

    def test_multiple_transports_comparison(self):
        """Сравнение overhead разных транспортов."""
        transports = {
            "xor": TransportManager.create("xor", key="key"),
            "faketls": TransportManager.create("faketls", sni="google.com"),
            "shadowsocks": TransportManager.create("shadowsocks", password="pass"),
        }

        test_data = b"Test payload for comparison" * 10  # 280 bytes

        results = {}
        for name, transport in transports.items():
            obfuscated = transport.obfuscate(test_data)
            recovered = transport.deobfuscate(obfuscated)

            assert recovered == test_data, f"{name}: roundtrip failed"

            results[name] = {
                "original": len(test_data),
                "obfuscated": len(obfuscated),
                "overhead": len(obfuscated) - len(test_data),
            }

        # XOR должен иметь минимальный overhead
        assert results["xor"]["overhead"] == 0

        # FakeTLS имеет TLS header overhead
        assert results["faketls"]["overhead"] > 0

        # Shadowsocks имеет overhead (nonce + tag + возможно padding)
        assert results["shadowsocks"]["overhead"] > 20  # минимум nonce + tag

    def test_dao_governance_full_cycle(self):
        """Полный цикл DAO: proposal -> vote -> tally."""
        engine = GovernanceEngine(node_id="proposer-node")

        # Создаём proposal
        proposal = engine.create_proposal(
            title="Обновить параметры сети",
            description="Увеличить интервал heartbeat до 60 секунд",
            actions=[
                {"type": "config_change", "key": "heartbeat_interval", "value": 60}
            ],
        )

        # Голосуем от нескольких узлов
        voters = ["node-1", "node-2", "node-3", "node-4", "node-5"]
        votes = [
            VoteType.YES,
            VoteType.YES,
            VoteType.YES,
            VoteType.NO,
            VoteType.ABSTAIN,
        ]

        for voter, vote in zip(voters, votes):
            result = engine.cast_vote(proposal.id, voter, vote)
            assert result is True, f"Голос от {voter} не принят"

        # Проверяем что голоса записаны
        assert len(proposal.votes) == 5

        # Подсчитываем вручную
        yes_count = sum(1 for v in proposal.votes.values() if v == VoteType.YES)
        no_count = sum(1 for v in proposal.votes.values() if v == VoteType.NO)
        abstain_count = sum(1 for v in proposal.votes.values() if v == VoteType.ABSTAIN)

        assert yes_count == 3
        assert no_count == 1
        assert abstain_count == 1

    def test_shaping_profiles_timing(self):
        """Проверяем что timing соответствует профилям."""
        profiles_timing = {
            TrafficProfile.VOICE_CALL: (20, 20),  # Строго 20ms
            TrafficProfile.GAMING: (10, 33),  # 10-33ms
            TrafficProfile.VIDEO_STREAMING: (5, 50),  # 5-50ms
        }

        for profile, (min_ms, max_ms) in profiles_timing.items():
            shaper = TrafficShaper(profile)
            delays = [shaper.get_send_delay() * 1000 for _ in range(100)]

            for delay in delays:
                assert (
                    min_ms <= delay <= max_ms + 1
                ), f"{profile.value}: delay {delay}ms out of range [{min_ms}, {max_ms}]"


class TestSecurityIntegration:
    """Тесты безопасности интеграции."""

    def test_key_mismatch_fails(self):
        """Разные ключи не позволяют расшифровать."""
        transport1 = TransportManager.create("shadowsocks", password="key1")
        transport2 = TransportManager.create("shadowsocks", password="key2")

        data = b"Secret message"
        encrypted = transport1.obfuscate(data)

        # Расшифровка с другим ключом должна провалиться
        with pytest.raises(Exception):
            transport2.deobfuscate(encrypted)

    def test_tampered_data_detected(self):
        """Изменённые данные обнаруживаются."""
        transport = TransportManager.create("shadowsocks", password="key")

        data = b"Original data"
        encrypted = transport.obfuscate(data)

        # Портим данные
        tampered = encrypted[:20] + bytes([encrypted[20] ^ 0xFF]) + encrypted[21:]

        # Должно выбросить исключение при проверке MAC
        with pytest.raises(Exception):
            transport.deobfuscate(tampered)


class TestPerformanceIntegration:
    """Тесты производительности интеграции."""

    def test_throughput_benchmark(self):
        """Измеряем throughput полного pipeline."""
        transport = TransportManager.create("xor", key="perf-test")
        shaper = TrafficShaper(TrafficProfile.FILE_DOWNLOAD)

        data = b"x" * 1400
        iterations = 1000

        start = time.perf_counter()

        for _ in range(iterations):
            obfuscated = transport.obfuscate(data)
            shaped = shaper.shape_packet(obfuscated)
            unshaped = shaper.unshape_packet(shaped)
            recovered = transport.deobfuscate(unshaped)

        elapsed = time.perf_counter() - start

        throughput_pps = iterations / elapsed
        throughput_mbps = (iterations * len(data) * 8) / elapsed / 1_000_000

        print(f"\n📊 Throughput: {throughput_pps:.0f} pps, {throughput_mbps:.2f} Mbps")

        # Реалистичный порог для полного pipeline с crypto в CI/sandbox.
        # Проверяем, что pipeline не деградировал критично, без завышенных
        # ожиданий от производительности виртуализированной среды.
        assert throughput_pps > 500, f"Throughput слишком низкий: {throughput_pps} pps"
        assert (
            throughput_mbps > 5
        ), f"Throughput должен быть > 5 Mbps, got {throughput_mbps:.2f}"
