"""
Bio-Evo PoC: Genetic Algorithm + GraphSAGE for MTTR Optimization
================================================================

Simulates a 200-node mesh network to optimize MAPE-K hyperparameters 
using the BioEvoOptimizer. Target: MTTR < 2.5s.
"""

import logging
import random
from src.self_healing.bio_evo_optimizer import BioEvoOptimizer, Individual

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bio-evo-poc")

def simulate_mesh_recovery(individual: Individual, num_nodes: int = 200) -> dict:
    """
    Simulates recovery of a mesh network under given MAPE-K parameters.
    Returns simulated MTTR and False Positive Rate (FPR).
    """
    params = individual.params
    
    # Base recovery time heavily depends on monitor_interval and parallelism
    base_detection_time = params.monitor_interval / 2.0
    
    # Causal analysis time (simulated GraphSAGE inference)
    # Higher confidence threshold requires more iterations/samples
    causal_time = 0.5 + (params.causal_confidence_min ** 2)
    
    # Execution time
    # Higher parallelism reduces recovery time but increases risk of conflicts
    execution_time = 5.0 / params.recovery_parallelism
    
    # Calculate raw MTTR
    raw_mttr = base_detection_time + causal_time + execution_time
    
    # Anomaly threshold affects FPR and missed detections
    # If threshold is too low, FPR is high. If too high, MTTR increases due to missed early warnings.
    fpr = 0.01
    if params.anomaly_threshold < 0.7:
        fpr += (0.7 - params.anomaly_threshold) * 0.5
        
    if params.anomaly_threshold > 0.9:
        raw_mttr += 2.0 # Missed early warnings
        
    # Scale simulation to 200 nodes (adds slight communication overhead)
    scale_factor = 1.0 + (num_nodes / 10000.0)
    final_mttr = raw_mttr * scale_factor
    
    # Add random jitter
    final_mttr *= random.uniform(0.9, 1.1)
    fpr *= random.uniform(0.9, 1.1)
    
    return {"mttr": final_mttr, "fpr": fpr}

def run_poc():
    logger.info("=== Starting Bio-Evo PoC (200 Nodes Simulation) ===")
    
    optimizer = BioEvoOptimizer(population_size=30)
    generations = 50
    target_mttr = 2.5
    
    for gen in range(generations):
        # Evaluate fitness for all individuals
        for ind in optimizer.population:
            results = simulate_mesh_recovery(ind, num_nodes=200)
            optimizer.evaluate_fitness(ind, results)
            
        optimizer.evolve()
        
        best = optimizer.population[0]
        if gen % 5 == 0 or best.fitness < target_mttr:
            logger.info(f"Gen {gen:02d} | Best MTTR: {best.fitness:.3f}s | FPR: {simulate_mesh_recovery(best).get('fpr'):.3f} | Params: P={best.params.recovery_parallelism}, M_Int={best.params.monitor_interval:.1f}s")
            
        if best.fitness <= target_mttr:
            logger.info(f"✅ Target MTTR <= {target_mttr}s reached at generation {gen}!")
            break
            
    best_params = optimizer.get_best_params()
    logger.info("=== Final Optimized MAPE-K Parameters ===")
    logger.info(f"Monitor Interval:      {best_params.monitor_interval:.2f}s")
    logger.info(f"Anomaly Threshold:     {best_params.anomaly_threshold:.2f}")
    logger.info(f"Causal Min Confidence: {best_params.causal_confidence_min:.2f}")
    logger.info(f"Recovery Parallelism:  {best_params.recovery_parallelism}")
    logger.info(f"Reinforcement Rate:    {best_params.reinforcement_rate:.3f}")
    
if __name__ == "__main__":
    run_poc()
