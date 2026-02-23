"""
Standalone Federated Learning (Flower) Server
=============================================

Starts a production-ready Flower server for federated learning
of the x0tta6bl4 GraphSAGE models.
"""

import argparse
import logging
import os
import signal
import sys
from typing import Dict, Optional

import flwr as fl
from src.ai.federated_learning import FederatedLearningCoordinator

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] fl-server: %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Federated Learning Server")
    parser.add_argument("--host", default="0.0.0.0", help="Listen host")
    parser.add_argument("--port", type=int, default=8080, help="Listen port")
    parser.add_argument("--rounds", type=int, default=50, help="Number of training rounds")
    parser.add_argument("--min-clients", type=int, default=3, help="Minimum clients for a round")
    parser.add_argument("--target-epsilon", type=float, default=1.0, help="Differential privacy epsilon")

    args = parser.parse_args()

    logger.info("=== starting x0tta6bl4 Federated Learning Server ===")
    logger.info(f"Listening on {args.host}:{args.port}")
    logger.info(f"Target rounds: {args.rounds}, Min clients: {args.min_clients}")

    # Initialize coordinator logic (for strategy and knowledge aggregation)
    coordinator = FederatedLearningCoordinator(
        num_clients=args.min_clients,
        num_rounds=args.rounds,
        target_epsilon=args.target_epsilon
    )

    # Use our custom Heterogeneous Weighted FedAvg strategy
    strategy = coordinator.create_hw_strategy()

    # Define server config
    config = fl.server.ServerConfig(num_rounds=args.rounds)

    # Start Flower server
    try:
        fl.server.start_server(
            server_address=f"{args.host}:{args.port}",
            config=config,
            strategy=strategy,
        )
    except Exception as e:
        logger.error(f"Flower server failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
