"""Coverage-focused tests for fixtures defined in tests/conftest.py."""

import os
import runpy
import sys
import types
from pathlib import Path


def test_production_mode_fixture_sets_env(production_mode):
    assert os.getenv("X0TTA6BL4_PRODUCTION") == "true"


def test_staging_mode_fixture_sets_env(staging_mode):
    assert os.getenv("X0TTA6BL4_PRODUCTION") == "false"


def test_db_session_fixture(db_session):
    # Works for both real SQLAlchemy session and fallback MagicMock.
    assert hasattr(db_session, "query")


def test_cache_session_fixture(cache_session):
    cache_session["k"] = "v"
    assert cache_session["k"] == "v"


def test_ml_models_session_fixture(ml_models_session):
    assert "anomaly_detector" in ml_models_session
    assert "graphsage" in ml_models_session
    assert "embeddings" in ml_models_session


def test_config_session_fixture(config_session):
    temp_dir, config = config_session
    assert temp_dir is not None
    assert config["test_mode"] is True
    assert "temp_dir" in config


def test_performance_tracker_fixture(performance_tracker):
    assert "start_time" in performance_tracker
    assert "start_memory" in performance_tracker
    assert "tests" in performance_tracker
    assert "imports" in performance_tracker
    performance_tracker["tests"]["fixture_probe"] = {"duration": 0.001}


def test_fresh_mock_dependencies_fixture(fresh_mock_dependencies):
    assert "tensorflow" in fresh_mock_dependencies
    assert "transformers" in fresh_mock_dependencies
    assert "tensorflow" in sys.modules
    assert "transformers" in sys.modules


def test_conftest_top_level_fallback_imports(monkeypatch):
    conftest_path = Path(__file__).resolve().parents[1] / "conftest.py"
    project_root = str(conftest_path.parents[1])

    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != project_root])
    monkeypatch.setitem(sys.modules, "torch", None)
    monkeypatch.setitem(sys.modules, "torch_geometric", None)
    monkeypatch.setitem(sys.modules, "prometheus_client", None)

    # Executes top-level fallback branches in tests/conftest.py.
    runpy.run_path(str(conftest_path))


def test_mock_fixtures_without_heavy_imports(monkeypatch):
    conftest_path = Path(__file__).resolve().parents[1] / "conftest.py"
    namespace = runpy.run_path(str(conftest_path))

    pq_mod = types.ModuleType("src.security.post_quantum_liboqs")
    pq_mod.LIBOQS_AVAILABLE = False
    pq_mod.PQMeshSecurityLibOQS = object
    monkeypatch.setitem(sys.modules, "src.security.post_quantum_liboqs", pq_mod)

    ml_pkg = types.ModuleType("src.ml")
    ml_pkg.__path__ = []
    monkeypatch.setitem(sys.modules, "src.ml", ml_pkg)

    ml_mod = types.ModuleType("src.ml.graphsage_anomaly_detector")
    ml_mod.GraphSAGEAnomalyDetector = object
    monkeypatch.setitem(sys.modules, "src.ml.graphsage_anomaly_detector", ml_mod)

    mock_pqc = getattr(namespace["mock_pqc"], "__wrapped__", namespace["mock_pqc"])
    pqc_gen = mock_pqc()
    assert next(pqc_gen) is not None
    pqc_gen.close()

    mock_ml = getattr(namespace["mock_ml"], "__wrapped__", namespace["mock_ml"])
    ml_gen = mock_ml()
    assert next(ml_gen) is not None
    ml_gen.close()


def test_db_and_app_session_fallback_branches(monkeypatch):
    conftest_path = Path(__file__).resolve().parents[1] / "conftest.py"
    namespace = runpy.run_path(str(conftest_path))

    monkeypatch.setitem(sys.modules, "sqlalchemy", None)
    monkeypatch.setitem(sys.modules, "sqlalchemy.orm", None)
    db_session = getattr(namespace["db_session"], "__wrapped__", namespace["db_session"])
    db_gen = db_session()
    db_obj = next(db_gen)
    assert hasattr(db_obj, "query")
    db_gen.close()

    monkeypatch.setitem(sys.modules, "src.core.app", None)
    app_session = getattr(
        namespace["app_session"], "__wrapped__", namespace["app_session"]
    )
    app_gen = app_session()
    assert next(app_gen) is not None
    app_gen.close()

    app_mod = types.ModuleType("src.core.app")
    app_mod.app = object()
    monkeypatch.setitem(sys.modules, "src.core.app", app_mod)
    app_gen_ok = app_session()
    assert next(app_gen_ok) is app_mod.app
    app_gen_ok.close()
