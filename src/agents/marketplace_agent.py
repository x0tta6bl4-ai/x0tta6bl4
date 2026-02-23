import json
import logging
import time
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MarketplaceAgent")

class MarketplaceAgent:
    """
    Управляет P2P арендой узлов в меш-сети x0tta6bl4.
    Соединяет владельцев оборудования и потребителей MaaS.
    """
    def __init__(self):
        self.listings = []
        self.state_file = "/mnt/projects/marketplace_state.json"

    def sync_listings(self):
        # Имитация получения списка доступных узлов от провайдеров
        logger.info("Scanning for available P2P nodes...")
        self.listings = [
            {"id": "node-DE-01", "cpu": 4, "ram": "8GB", "price_h": 0.05, "status": "available"},
            {"id": "node-US-05", "cpu": 2, "ram": "4GB", "price_h": 0.02, "status": "rented"}
        ]
        with open(self.state_file, 'w') as f:
            json.dump(self.listings, f, indent=2)
        logger.info(f"Marketplace updated: {len(self.listings)} nodes active.")

    def run(self):
        while True:
            self.sync_listings()
            time.sleep(60)

if __name__ == "__main__":
    agent = MarketplaceAgent()
    agent.run()
