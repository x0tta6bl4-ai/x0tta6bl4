"""
Geneva Stego-mesh v2 PoC
========================

Trains a genetic algorithm to find an evasion strategy (DNA)
that bypasses the DPI simulator with > 95% success rate.
"""

import logging
import os
import random
from src.anti_censorship.geneva_genetic import GenevaGeneticOptimizer
from src.anti_censorship.stego_mesh import StegoMeshProtocol
from scripts.dpi_simulator import DPISimulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("geneva-poc")

def run_geneva_training():
    logger.info("=== Starting Geneva DPI Evasion PoC (Stego-mesh v2) ===")
    
    # 1. Setup Environment
    # Master key MUST be loaded from secure secret storage.
    # For PoC, use GENEVA_MASTER_KEY environment variable.
    # In production, use Vault, AWS Secrets Manager, or Kubernetes Secrets.
    master_key = os.environ.get("GENEVA_MASTER_KEY")
    if not master_key:
        logger.error(
            "GENEVA_MASTER_KEY environment variable is not set. "
            "For PoC testing, you can set it to a test value, e.g.: "
            "export GENEVA_MASTER_KEY='test_poc_key_do_not_use_in_production'"
        )
        raise RuntimeError(
            "GENEVA_MASTER_KEY environment variable must be set. "
            "Refusing to use hardcoded keys for security."
        )
    master_key = master_key.encode()
    logger.info("Using GENEVA_MASTER_KEY from environment (length: %d bytes)", len(master_key))
    
    dpi = DPISimulator()
    optimizer = GenevaGeneticOptimizer(population_size=20)
    
    raw_payload = b'{"type": "heartbeat", "node_id": "test-node", "data": "very secret payload that dpi hates"}'
    
    generations = 15
    target_bypass_rate = 0.95
    
    logger.info(f"Target Bypass Rate: {target_bypass_rate * 100:.1f}%")
    
    # 2. Training Loop
    for gen in range(generations):
        fitness_results = {}
        
        for idx, dna in enumerate(optimizer.population):
            # Apply DNA to StegoMesh
            stego = StegoMeshProtocol(master_key, evasion_dna=dna)
            
            # Test evasion across multiple trials
            trials = 10
            successes = 0
            
            for _ in range(trials):
                # Encode packet (which applies Geneva actions)
                packets = stego.encode_packet(raw_payload, protocol_mimic="http")
                if not isinstance(packets, list):
                    packets = [packets]
                
                # Check if ANY of the resulting packets trigger DPI
                detected = False
                for p in packets:
                    res = dpi.inspect(p)
                    # Penalize high entropy or detected signatures
                    if res["detected"] or res["entropy"] > 6.5:
                        detected = True
                        break
                
                if not detected:
                    successes += 1
            
            # Calculate fitness: bypass rate
            # Subtract small penalty for too many packets (efficiency)
            packet_overhead = max(0, len(packets) - 1) * 0.05
            fitness = (successes / trials) - packet_overhead
            fitness_results[idx] = max(0.0, fitness)
            
        # Evolve population
        optimizer.evolve(fitness_results)
        best_dna = optimizer.get_best_strategy()
        
        logger.info(f"Generation {gen} | Best Strategy: {best_dna} | Fitness: {best_dna.fitness:.2f}")
        
        if best_dna.fitness >= target_bypass_rate:
            logger.info(f"✅ Target bypass rate >= {target_bypass_rate*100}% achieved at generation {gen}!")
            break

    logger.info("=== Final Evasion Strategy (DNA) ===")
    logger.info(f"Actions: {optimizer.get_best_strategy()}")
    logger.info("Ready for deployment to Stego-mesh v2.")

if __name__ == "__main__":
    run_geneva_training()
