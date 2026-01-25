"""Pytest configuration for x0tta6bl4.

Ensures that the project root is on sys.path so imports like `from src...` work
in unit tests regardless of the working directory.
"""

import os
import sys
import pytest
import unittest.mock as mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Mock optional dependencies to prevent import errors during testing
mocked_modules = {
    'torch': mock.MagicMock(),
    'torch.nn': mock.MagicMock(),
    'torch.nn.functional': mock.MagicMock(),
    'torch_geometric': mock.MagicMock(),
    'torch_geometric.nn': mock.MagicMock(),
    'liboqs': mock.MagicMock(),
    'oqs': mock.MagicMock(),
    'bcc': mock.MagicMock(),
    'prometheus_api_client': mock.MagicMock(),
    'sentence_transformers': mock.MagicMock(),
    'sentence_transformers.SentenceTransformer': mock.MagicMock(),
    'hnswlib': mock.MagicMock(),
    'shap': mock.MagicMock(),
    'numba': mock.MagicMock(),
    'flwr': mock.MagicMock(),
    'web3': mock.MagicMock(),
    'aioipfs': mock.MagicMock(),
}

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Automatically mock optional dependencies for all tests."""
    with mock.patch.dict('sys.modules', mocked_modules):
        yield

@pytest.fixture
def production_mode(monkeypatch):
    """Set production mode for tests."""
    monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "true")

@pytest.fixture
def staging_mode(monkeypatch):
    """Set staging mode for tests."""
    monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "false")

@pytest.fixture
def mock_pqc():
    """Mock PQC components."""
    with mock.patch('src.security.post_quantum_liboqs.LIBOQS_AVAILABLE', True):
        with mock.patch('src.security.post_quantum_liboqs.PQMeshSecurityLibOQS') as mock_pqc:
            yield mock_pqc

@pytest.fixture
def mock_ml():
    """Mock ML components."""
    with mock.patch('src.ml.graphsage_anomaly_detector.GraphSAGEAnomalyDetector') as mock_detector:
        yield mock_detector
