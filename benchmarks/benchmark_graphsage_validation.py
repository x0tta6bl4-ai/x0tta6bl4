"""
GraphSAGE Anomaly Detector Benchmark & Validation Suite

This module provides comprehensive benchmarking and validation for the GraphSAGE
anomaly detection engine, including precision, recall, F1-score metrics.

Benchmarks:
- Model accuracy (precision, recall, F1)
- Inference latency (<50ms target)
- Model size (<5MB INT8 quantized target)
- Causal analysis integration
- Scalability (number of nodes, features)
"""

import logging
import time
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import json

try:
    from sklearn.metrics import (
        precision_score, recall_score, f1_score,
        confusion_matrix, roc_auc_score, classification_report
    )
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkMetrics:
    """Container for benchmark results"""
    # Classification metrics
    precision: float
    recall: float
    f1_score: float

    # Performance metrics
    inference_latency_ms: float
    model_size_mb: float
    throughput_samples_per_sec: float

    # Dataset metrics
    total_samples: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int

    # Optional fields (with defaults)
    roc_auc: Optional[float] = None
    benchmark_date: str = None
    
    def __post_init__(self):
        if self.benchmark_date is None:
            self.benchmark_date = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for logging/storage"""
        return {
            'precision': self.precision,
            'recall': self.recall,
            'f1_score': self.f1_score,
            'roc_auc': self.roc_auc,
            'inference_latency_ms': self.inference_latency_ms,
            'model_size_mb': self.model_size_mb,
            'throughput_samples_per_sec': self.throughput_samples_per_sec,
            'total_samples': self.total_samples,
            'true_positives': self.true_positives,
            'false_positives': self.false_positives,
            'true_negatives': self.true_negatives,
            'false_negatives': self.false_negatives,
            'benchmark_date': self.benchmark_date
        }
    
    def __str__(self) -> str:
        """Human-readable summary"""
        return f"""
╔════════════════════════════════════════════════════╗
║       GraphSAGE Anomaly Detection Benchmark        ║
╠════════════════════════════════════════════════════╣
║ Classification Metrics:                            ║
║   Precision:  {self.precision:.4f} (↑ reduce false alarms)     ║
║   Recall:     {self.recall:.4f}     (↑ catch all anomalies)     ║
║   F1-Score:   {self.f1_score:.4f}     (↑ balanced metric)       ║
║   ROC-AUC:    {f'{self.roc_auc:.4f}' if self.roc_auc is not None else 'N/A':<7}   (discrimination ability)   ║
║                                                    ║
║ Performance Metrics:                               ║
║   Latency:    {self.inference_latency_ms:.2f}ms   (target: <50ms)  ║
║   Model Size: {self.model_size_mb:.2f}MB   (target: <5MB)    ║
║   Throughput: {self.throughput_samples_per_sec:.0f} samples/sec        ║
║                                                    ║
║ Confusion Matrix:                                  ║
║   TP: {self.true_positives:>5}  |  FP: {self.false_positives:>5}              ║
║   FN: {self.false_negatives:>5}  |  TN: {self.true_negatives:>5}              ║
║                                                    ║
║ Dataset: {self.total_samples} samples            ║
║ Date: {self.benchmark_date}        ║
╚════════════════════════════════════════════════════╝
"""


class GraphSAGEBenchmark:
    """
    Comprehensive benchmark suite for GraphSAGE anomaly detector.
    
    Usage:
        benchmark = GraphSAGEBenchmark()
        metrics = benchmark.evaluate(y_true, y_pred, inference_times)
        print(metrics)
        benchmark.save_results(metrics, 'results.json')
    """
    
    def __init__(self):
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required: pip install scikit-learn")
        self.results_history: List[BenchmarkMetrics] = []
    
    def evaluate(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_pred_proba: Optional[np.ndarray] = None,
        inference_times: Optional[List[float]] = None,
        model_size_mb: Optional[float] = None
    ) -> BenchmarkMetrics:
        """
        Evaluate anomaly detector performance.
        
        Args:
            y_true: Ground truth labels (0=normal, 1=anomaly)
            y_pred: Predicted labels (0=normal, 1=anomaly)
            y_pred_proba: Predicted probabilities [0-1] (optional for ROC-AUC)
            inference_times: List of inference times in milliseconds
            model_size_mb: Size of model in MB
            
        Returns:
            BenchmarkMetrics with all computed statistics
        """
        # Validate inputs
        if len(y_true) != len(y_pred):
            raise ValueError("y_true and y_pred must have same length")
        
        y_true = np.array(y_true).astype(int)
        y_pred = np.array(y_pred).astype(int)
        
        # Compute classification metrics
        precision = precision_score(y_true, y_pred, zero_division=0)
        recall = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        
        # Compute ROC-AUC if probabilities provided
        roc_auc = None
        if y_pred_proba is not None:
            y_pred_proba = np.array(y_pred_proba)
            try:
                roc_auc = roc_auc_score(y_true, y_pred_proba)
            except ValueError:
                logger.warning("Could not compute ROC-AUC (need both classes)")
        
        # Compute confusion matrix
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
        
        # Compute performance metrics
        avg_latency_ms = np.mean(inference_times) if len(inference_times) > 0 else 0.0
        total_time = np.sum(inference_times) if len(inference_times) > 0 else 0.0
        throughput = (len(y_true) / total_time * 1000) if total_time > 0 else 0.0
        model_size = model_size_mb or 0.0
        
        metrics = BenchmarkMetrics(
            precision=precision,
            recall=recall,
            f1_score=f1,
            roc_auc=roc_auc,
            inference_latency_ms=avg_latency_ms,
            model_size_mb=model_size,
            throughput_samples_per_sec=throughput,
            total_samples=len(y_true),
            true_positives=int(tp),
            false_positives=int(fp),
            true_negatives=int(tn),
            false_negatives=int(fn)
        )
        
        self.results_history.append(metrics)
        return metrics
    
    def evaluate_with_report(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        target_names: Optional[List[str]] = None,
        **kwargs
    ) -> Tuple[BenchmarkMetrics, str]:
        """
        Evaluate with detailed classification report.
        
        Returns:
            (BenchmarkMetrics, detailed_report_string)
        """
        metrics = self.evaluate(y_true, y_pred, **kwargs)
        
        report = classification_report(
            y_true, y_pred,
            target_names=target_names or ['Normal', 'Anomaly'],
            zero_division=0
        )
        
        return metrics, report
    
    def check_target_metrics(self, metrics: BenchmarkMetrics) -> Dict[str, bool]:
        """
        Check if benchmark meets target metrics.
        
        Targets:
        - Precision: ≥94%
        - Recall: ≥94%
        - F1-Score: ≥94%
        - Latency: <50ms
        - Model Size: <5MB
        """
        targets = {
            'precision_target': metrics.precision >= 0.94,
            'recall_target': metrics.recall >= 0.94,
            'f1_target': metrics.f1_score >= 0.94,
            'latency_target': metrics.inference_latency_ms < 50,
            'model_size_target': metrics.model_size_mb < 5.0
        }
        
        all_met = all(targets.values())
        targets['all_targets_met'] = all_met
        
        logger.info(f"Target check: {targets}")
        return targets
    
    def save_results(self, metrics: BenchmarkMetrics, filepath: str) -> None:
        """Save benchmark results to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(metrics.to_dict(), f, indent=2)
        logger.info(f"Benchmark results saved to {filepath}")
    
    def load_results(self, filepath: str) -> BenchmarkMetrics:
        """Load benchmark results from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        return BenchmarkMetrics(**data)
    
    def compare_runs(
        self,
        metrics_list: List[BenchmarkMetrics]
    ) -> str:
        """
        Compare multiple benchmark runs and show improvements.
        """
        if len(metrics_list) < 2:
            return "Need at least 2 results to compare"
        
        baseline = metrics_list[0]
        comparison_str = f"Comparing {len(metrics_list)} benchmark runs:\n\n"
        
        for i, metrics in enumerate(metrics_list[1:], 1):
            precision_delta = (metrics.precision - baseline.precision) * 100
            recall_delta = (metrics.recall - baseline.recall) * 100
            f1_delta = (metrics.f1_score - baseline.f1_score) * 100
            latency_delta = metrics.inference_latency_ms - baseline.inference_latency_ms
            
            comparison_str += f"Run {i} vs Baseline:\n"
            comparison_str += f"  Precision: {precision_delta:+.2f}% ({metrics.precision:.4f})\n"
            comparison_str += f"  Recall: {recall_delta:+.2f}% ({metrics.recall:.4f})\n"
            comparison_str += f"  F1-Score: {f1_delta:+.2f}% ({metrics.f1_score:.4f})\n"
            comparison_str += f"  Latency: {latency_delta:+.2f}ms ({metrics.inference_latency_ms:.2f}ms)\n"
            comparison_str += "\n"
        
        return comparison_str


# Integration with Causal Analysis
class GraphSAGECausalIntegration:
    """
    Integrates GraphSAGE anomaly detection with causal analysis.
    
    When GraphSAGE detects an anomaly, this class can:
    1. Extract anomalous features
    2. Pass to causal analysis for root cause discovery
    3. Generate incident reports
    """
    
    def __init__(self, graphsage_detector=None, causal_engine=None):
        self.detector = graphsage_detector
        self.causal_engine = causal_engine
    
    def detect_and_analyze(
        self,
        node_id: str,
        features: Dict[str, float],
        threshold: float = 0.5
    ) -> Dict:
        """
        Detect anomalies and perform causal analysis.
        
        Returns:
            {
                'is_anomaly': bool,
                'anomaly_score': float,
                'causal_analysis': CausalAnalysisResult or None,
                'root_causes': List[str]
            }
        """
        # Step 1: GraphSAGE anomaly detection
        if not self.detector:
            return {'error': 'GraphSAGE detector not initialized'}
        
        prediction = self.detector.predict(node_id, features)
        
        if not prediction.is_anomaly or prediction.anomaly_score < threshold:
            return {
                'is_anomaly': False,
                'anomaly_score': prediction.anomaly_score,
                'causal_analysis': None
            }
        
        # Step 2: Causal analysis for root cause discovery
        causal_result = None
        if self.causal_engine:
            from src.ml.causal_analysis import IncidentEvent
            
            event = IncidentEvent(
                node_id=node_id,
                anomaly_score=prediction.anomaly_score,
                anomalous_features=prediction.features,
                timestamp=time.time()
            )
            
            causal_result = self.causal_engine.analyze(event)
        
        return {
            'is_anomaly': True,
            'anomaly_score': prediction.anomaly_score,
            'confidence': prediction.confidence,
            'causal_analysis': causal_result,
            'root_causes': causal_result.root_causes if causal_result else []
        }


# Example usage and testing
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Create synthetic test data
    np.random.seed(42)
    n_samples = 1000
    
    y_true = np.concatenate([
        np.zeros(900, dtype=int),      # 900 normal samples
        np.ones(100, dtype=int)         # 100 anomalies
    ])
    
    # Simulate predictions (90% accuracy)
    y_pred = y_true.copy()
    error_indices = np.random.choice(n_samples, size=100, replace=False)
    y_pred[error_indices] = 1 - y_pred[error_indices]
    
    # Simulate inference times
    inference_times = np.random.uniform(10, 40, n_samples)  # 10-40ms
    
    # Run benchmark
    benchmark = GraphSAGEBenchmark()
    metrics = benchmark.evaluate(
        y_true, y_pred,
        inference_times=inference_times,
        model_size_mb=4.5
    )
    
    print(metrics)
    
    # Check targets
    targets = benchmark.check_target_metrics(metrics)
    print(f"\nTarget metrics met: {targets['all_targets_met']}")
