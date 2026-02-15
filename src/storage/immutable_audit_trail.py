"""
Immutable Audit Trail
======================

Реализация неизменяемого аудит-трейла с использованием IPFS и Ethereum.
Обеспечивает полную прозрачность и верифицируемость всех действий в системе.
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Проверка доступности зависимостей
try:
    import ipfshttpclient

    IPFS_AVAILABLE = True
except ImportError:
    IPFS_AVAILABLE = False
    logger.warning("IPFS client not available")

try:
    from web3 import Web3

    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    logger.warning("Web3 not available")


class MerkleTree:
    """
    Простая реализация Merkle Tree для верификации записей.
    """

    @staticmethod
    def hash_data(data: bytes) -> str:
        """Хеширование данных"""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def compute_merkle_root(records: List[bytes]) -> str:
        """
        Вычисление корня Merkle дерева.

        Args:
            records: Список записей для хеширования

        Returns:
            Корень Merkle дерева
        """
        if not records:
            return ""

        # Хешируем каждую запись
        hashes = [MerkleTree.hash_data(record) for record in records]

        # Строим дерево снизу вверх
        while len(hashes) > 1:
            new_hashes = []
            for i in range(0, len(hashes), 2):
                if i + 1 < len(hashes):
                    # Объединяем два хеша
                    combined = hashes[i] + hashes[i + 1]
                    new_hashes.append(MerkleTree.hash_data(combined.encode()))
                else:
                    # Нечётное количество - дублируем последний
                    new_hashes.append(hashes[i])
            hashes = new_hashes

        return hashes[0] if hashes else ""


class ImmutableAuditTrail:
    """
    Неизменяемый аудит-трейл для x0tta6bl4.

    Хранит все критические события в IPFS и регистрирует их в Ethereum
    для обеспечения полной прозрачности и верифицируемости.
    """

    def __init__(
        self,
        ipfs_client=None,
        ethereum_contract=None,
        ethereum_address: Optional[str] = None,
    ):
        """
        Инициализация аудит-трейла.

        Args:
            ipfs_client: Клиент IPFS (создаётся если None)
            ethereum_contract: Ethereum контракт (опционально)
            ethereum_address: Адрес Ethereum контракта
        """
        # Инициализация IPFS
        self.ipfs_client = ipfs_client
        if ipfs_client is None and IPFS_AVAILABLE:
            try:
                self.ipfs_client = ipfshttpclient.connect()
                logger.info("✅ IPFS client connected")
            except Exception as e:
                logger.warning(f"Failed to connect to IPFS: {e}")
                self.ipfs_client = None

        # Инициализация Ethereum
        self.ethereum_contract = ethereum_contract
        self.ethereum_address = ethereum_address
        self.web3 = None

        if ethereum_contract is None and WEB3_AVAILABLE:
            try:
                # В production здесь должен быть реальный Web3 провайдер
                # self.web3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
                logger.info("Ethereum integration available (not connected)")
            except Exception as e:
                logger.warning(f"Failed to connect to Ethereum: {e}")

        self.records: List[Dict[str, Any]] = []
        logger.info("Immutable Audit Trail initialized")

    def add_record(
        self, record_type: str, data: Dict[str, Any], auditor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Добавление записи в аудит-трейл.

        Args:
            record_type: Тип записи (mapek_decision, dao_vote, security_event, etc.)
            data: Данные записи
            auditor: Адрес/ID аудитора

        Returns:
            Созданная запись с IPFS CID и Merkle root
        """
        # Создаём запись
        record = {
            "type": record_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
            "auditor": auditor or "system",
            "version": "1.0",
        }

        # Сериализуем в JSON
        record_json = json.dumps(record, sort_keys=True)
        record_bytes = record_json.encode("utf-8")

        # Вычисляем хеш записи
        record_hash = hashlib.sha256(record_bytes).hexdigest()

        # Добавляем в IPFS
        ipfs_cid = None
        if self.ipfs_client:
            try:
                result = self.ipfs_client.add_bytes(record_bytes)
                ipfs_cid = result
                logger.debug(f"Record added to IPFS: {ipfs_cid}")
            except Exception as e:
                logger.error(f"Failed to add record to IPFS: {e}")

        # Вычисляем Merkle root для всех записей
        all_records = [json.dumps(r, sort_keys=True).encode() for r in self.records]
        all_records.append(record_bytes)
        merkle_root = MerkleTree.compute_merkle_root(all_records)

        # Обогащаем запись метаданными
        record["ipfs_cid"] = ipfs_cid
        record["merkle_root"] = merkle_root
        record["record_hash"] = record_hash

        # Регистрируем в Ethereum (если доступно)
        if self.ethereum_contract:
            try:
                # В production здесь будет вызов smart contract
                # self.ethereum_contract.functions.addAuditRecord(
                #     ipfs_cid, record_type, merkle_root
                # ).transact()
                logger.debug("Record registered in Ethereum (simulated)")
            except Exception as e:
                logger.error(f"Failed to register in Ethereum: {e}")

        # Сохраняем локально
        self.records.append(record)

        logger.info(
            f"Audit record added: type={record_type}, "
            f"ipfs_cid={ipfs_cid}, merkle_root={merkle_root[:16]}..."
        )

        return record

    def verify_record(self, record: Dict[str, Any]) -> bool:
        """
        Верификация записи.

        Args:
            record: Запись для верификации

        Returns:
            True если запись верифицирована
        """
        try:
            # Проверяем хеш записи
            record_json = json.dumps(record, sort_keys=True)
            record_bytes = record_json.encode("utf-8")
            computed_hash = hashlib.sha256(record_bytes).hexdigest()

            if computed_hash != record.get("record_hash"):
                logger.warning("Record hash mismatch")
                return False

            # Проверяем IPFS (если доступно)
            if record.get("ipfs_cid") and self.ipfs_client:
                try:
                    ipfs_data = self.ipfs_client.cat(record["ipfs_cid"])
                    if ipfs_data != record_bytes:
                        logger.warning("IPFS data mismatch")
                        return False
                except Exception as e:
                    logger.warning(f"Failed to verify IPFS: {e}")

            # Проверяем Merkle root
            all_records = [json.dumps(r, sort_keys=True).encode() for r in self.records]
            computed_root = MerkleTree.compute_merkle_root(all_records)

            if computed_root != record.get("merkle_root"):
                logger.warning("Merkle root mismatch")
                return False

            return True

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False

    def get_records(
        self,
        record_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Получение записей с фильтрацией.

        Args:
            record_type: Фильтр по типу
            start_time: Начальное время
            end_time: Конечное время

        Returns:
            Список записей
        """
        filtered = self.records

        if record_type:
            filtered = [r for r in filtered if r.get("type") == record_type]

        if start_time:
            filtered = [
                r
                for r in filtered
                if datetime.fromisoformat(r["timestamp"]) >= start_time
            ]

        if end_time:
            filtered = [
                r
                for r in filtered
                if datetime.fromisoformat(r["timestamp"]) <= end_time
            ]

        return filtered

    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики аудит-трейла"""
        stats = {
            "total_records": len(self.records),
            "records_by_type": {},
            "ipfs_enabled": self.ipfs_client is not None,
            "ethereum_enabled": self.ethereum_contract is not None,
        }

        for record in self.records:
            record_type = record.get("type", "unknown")
            stats["records_by_type"][record_type] = (
                stats["records_by_type"].get(record_type, 0) + 1
            )

        return stats
