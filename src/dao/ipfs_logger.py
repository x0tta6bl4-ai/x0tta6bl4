"""
Логирование критических событий в IPFS для DAO аудита
"""
import time
import ipfshttpclient
from typing import Dict
import logging
import json
import hashlib

logger = logging.getLogger(__name__)

class DAOAuditLogger:
    def __init__(self, ipfs_api='/ip4/127.0.0.1/tcp/5001'):
        try:
            self.client = ipfshttpclient.connect(ipfs_api)
            logger.info(f"DAOAuditLogger initialized with IPFS API at {ipfs_api}")
        except Exception as e:
            self.client = None
            logger.error(f"Could not connect to IPFS daemon at {ipfs_api}: {e}")

    async def log_consciousness_event(self, event: Dict):
        """
        Логировать значительное изменение сознания в IPFS
        """
        if not self.client:
            logger.warning("IPFS client not available, skipping audit log.")
            return None

        # Добавляем timestamp и signature
        event['timestamp'] = time.time()
        event_str = json.dumps(event, sort_keys=True)
        event['signature'] = self._sign_event(event_str)
        
        try:
            # Загружаем в IPFS
            result = self.client.add_json(event)
            cid = result['Hash']
            
            # Пинаем для постоянного хранения
            self.client.pin.add(cid)
            
            logger.info(f"📜 DAO audit logged: ipfs://{cid} content={json.dumps(event)}")
            return cid
        except Exception as e:
            logger.error(f"Failed to log event to IPFS: {e}")
            return None

    def _sign_event(self, event_str: str) -> str:
        """Create a sha256 hash of the event string as a mock signature."""
        return hashlib.sha256(event_str.encode()).hexdigest()

