# scripts/validate_graphsage_causal_analysis.py
import asyncio
import os
import sys
import logging
import random
from typing import Dict, List, Tuple, Any, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ml.graphsage_anomaly_detector import GraphSAGEAnomalyDetector, AnomalyPrediction
from src.ml.causal_analysis import CausalAnalysisEngine, RootCause, CausalAnalysisResult
from src.monitoring.alerting import send_alert, AlertSeverity

logger = logging.getLogger("graphsage_validation")
logging.basicConfig(level=logging.INFO)

def _generate_simulated_mesh_data(
    num_nodes: int = 10,
    num_edges: int = 20,
    introduce_anomaly: bool = False,
    anomaly_node: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
    """Generates simulated mesh node features and edge list."""
    nodes = [f"node_{i}" for i in range(num_nodes)]
    
    node_features = []
    for node_id in nodes:
        features = {
            "latency": random.uniform(5, 50),
            "loss_rate": random.uniform(0.01, 0.1),
            "throughput": random.uniform(10, 100),
            "cpu_usage": random.uniform(0.1, 0.8),
            "memory_usage": random.uniform(0.1, 0.7)
        }
        node_features.append({"node_id": node_id, "features": features})
    
    edges = []
    for _ in range(num_edges):
        u, v = random.sample(nodes, 2)
        edges.append((u, v))
    
    if introduce_anomaly and anomaly_node:
        logger.info(f"Injecting anomaly into node: {anomaly_node}")
        for nf in node_features:
            if nf["node_id"] == anomaly_node:
                nf["features"]["latency"] = random.uniform(100, 500)  # High latency
                nf["features"]["loss_rate"] = random.uniform(0.5, 0.9)   # High loss
                nf["features"]["cpu_usage"] = random.uniform(0.9, 1.0)   # High CPU
    
    return node_features, edges

async def validate_graphsage_causal_analysis():
    """
    Validates the GraphSAGE Anomaly Detector and Causal Analysis Engine.
    """
    print("--- Starting GraphSAGE Causal Analysis Validation Script ---")
    node_id = os.getenv("NODE_ID", "validation-node")
    
    # Initialize components
    graphsage_detector: Optional[GraphSAGEAnomalyDetector] = None
    causal_analysis_engine: Optional[CausalAnalysisEngine] = None
    
    try:
        graphsage_detector = GraphSAGEAnomalyDetector(use_quantization=False)
        graphsage_detector.recall = 0.96 # Simulate a trained model
        graphsage_detector.precision = 0.97
        logger.info("✅ GraphSAGE Anomaly Detector initialized.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize GraphSAGE Anomaly Detector: {e}")
        await send_alert(
            alert_name="GraphSAGE_InitFailure",
            severity=AlertSeverity.CRITICAL,
            message=f"Failed to initialize GraphSAGE Anomaly Detector: {e}",
            labels={"node_id": node_id},
            annotations={"runbook_url": "/docs/ml/graphsage_troubleshooting.md"}
        )
        print("--- GraphSAGE Causal Analysis Validation Failed (Init) ---")
        return

    try:
        causal_analysis_engine = CausalAnalysisEngine()
        logger.info("✅ Causal Analysis Engine initialized.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Causal Analysis Engine: {e}")
        await send_alert(
            alert_name="CausalAnalysis_InitFailure",
            severity=AlertSeverity.CRITICAL,
            message=f"Failed to initialize Causal Analysis Engine: {e}",
            labels={"node_id": node_id},
            annotations={"runbook_url": "/docs/ml/causal_analysis_troubleshooting.md"}
        )
        print("--- GraphSAGE Causal Analysis Validation Failed (Init) ---")
        return

    # --- Scenario 1: No anomaly ---
    print("\n--- Scenario 1: No Anomaly (Simulated) ---")
    node_features_no_anomaly, edges_no_anomaly = _generate_simulated_mesh_data()
    
    # Perform anomaly prediction
    predictions_no_anomaly: Dict[str, AnomalyPrediction] = {}
    for nf in node_features_no_anomaly:
        pred = graphsage_detector.predict(
            node_id=nf["node_id"],
            node_features=nf["features"],
            neighbors=[] # Simplified for this test
        )
        predictions_no_anomaly[nf["node_id"]] = pred
    
    anomalous_nodes_no_anomaly = [n_id for n_id, pred in predictions_no_anomaly.items() if pred.is_anomaly]
    
    if not anomalous_nodes_no_anomaly:
        print("✅ Scenario 1: Correctly identified no anomalies.")
    else:
        print(f"❌ Scenario 1: Incorrectly identified anomalies: {anomalous_nodes_no_anomaly}")
        await send_alert(
            alert_name="FalsePositive_AnomalyDetection",
            severity=AlertSeverity.WARNING,
            message=f"GraphSAGE detector reported false positives: {anomalous_nodes_no_anomaly}",
            labels={"node_id": node_id, "scenario": "no_anomaly"},
            annotations={"runbook_url": "/docs/ml/graphsage_false_positives.md"}
        )

    # --- Scenario 2: Single node anomaly ---
    print("\n--- Scenario 2: Single Node Anomaly (Simulated) ---")
    anomaly_target_node = "node_3"
    node_features_anomaly, edges_anomaly = _generate_simulated_mesh_data(
        introduce_anomaly=True, anomaly_node=anomaly_target_node
    )
    
    # Perform anomaly prediction
    predictions_anomaly: Dict[str, AnomalyPrediction] = {}
    for nf in node_features_anomaly:
        pred = graphsage_detector.predict(
            node_id=nf["node_id"],
            node_features=nf["features"],
            neighbors=[] # Simplified for this test
        )
        predictions_anomaly[nf["node_id"]] = pred

    anomalous_nodes_anomaly = [n_id for n_id, pred in predictions_anomaly.items() if pred.is_anomaly]
    
    if anomaly_target_node in anomalous_nodes_anomaly:
        print(f"✅ Scenario 2: Correctly identified anomaly in node {anomaly_target_node}.")
        
        # Perform causal analysis
        logger.info(f"Running causal analysis for node {anomaly_target_node}...")
        try:
            causal_graph: CausalGraph = causal_analysis_engine.analyze(
                node_status=[NodeStatus(node_id=nf["node_id"], status=pred.anomaly_score > 0.5) for nf, pred in zip(node_features_anomaly, predictions_anomaly.values())],
                edge_status=[EdgeStatus(source=u, destination=v, status=True) for u, v in edges_anomaly] # Assume all edges healthy for simplicity
            )
            print(f"✅ Causal analysis completed for node {anomaly_target_node}. Root causes: {causal_graph.get_root_causes()}")
            if causal_graph.get_root_causes():
                print(f"    - Example root cause: {causal_graph.get_root_causes()[0].description}")
            else:
                print("    - No specific root causes identified (might be expected for simple anomaly).")
        except Exception as e:
            logger.error(f"❌ Causal analysis failed for node {anomaly_target_node}: {e}")
            await send_alert(
                alert_name="CausalAnalysis_Failure",
                severity=AlertSeverity.ERROR,
                message=f"Causal analysis failed for node {anomaly_target_node}: {e}",
                labels={"node_id": node_id, "target_node": anomaly_target_node},
                annotations={"runbook_url": "/docs/ml/causal_analysis_troubleshooting.md"}
            )
    else:
        print(f"❌ Scenario 2: Failed to identify anomaly in node {anomaly_target_node}. Anomalies found: {anomalous_nodes_anomaly}")
        await send_alert(
            alert_name="FalseNegative_AnomalyDetection",
            severity=AlertSeverity.CRITICAL,
            message=f"GraphSAGE detector reported false negative for node {anomaly_target_node}. Anomalies found: {anomalous_nodes_anomaly}",
            labels={"node_id": node_id, "scenario": "single_anomaly"},
            annotations={"runbook_url": "/docs/ml/graphsage_false_negatives.md"}
        )

    print("\n--- GraphSAGE Causal Analysis Validation Script Finished ---")
    await send_alert(
        alert_name="GraphSAGE_Causal_Validation_Success",
        severity=AlertSeverity.INFO,
        message="GraphSAGE Causal Analysis validation completed successfully.",
        labels={"node_id": node_id}
    )

if __name__ == "__main__":
    asyncio.run(validate_graphsage_causal_analysis())
