#!/usr/bin/env python3
"""
Example: Integration with Existing Python Project
=================================================

Demonstrates how to integrate x0tta6bl4 into an existing Python project.
This example shows how to use the self-healing mesh architecture with
post-quantum cryptography in an existing Flask application.
"""

# Import existing Flask app
from flask import Flask, jsonify, request

# Import x0tta6bl4 components
from src.self_healing.mape_k import SelfHealingManager
from src.security.pqc_core import PQCCore
from src.monitoring.prometheus import PrometheusMetrics
from src.network.mesh_router import MeshRouter

app = Flask(__name__)

# Initialize x0tta6bl4 components
self_healing_manager = None
pqc_core = None
mesh_router = None
prometheus_metrics = None

@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify(
        status="ok",
        x0tta6bl4_connected=self_healing_manager is not None,
        mesh_nodes=len(mesh_router.get_nodes()) if mesh_router else 0
    )

@app.route("/api/data")
def get_data():
    """Example API endpoint using x0tta6bl4 features."""
    try:
        # Track API request in Prometheus
        prometheus_metrics.increment_api_requests("get_data")

        # Perform some business logic here
        data = {
            "message": "Data from x0tta6bl4-integrated API",
            "nodes": mesh_router.get_nodes()
        }

        return jsonify(data)
    except Exception as e:
        prometheus_metrics.increment_api_errors("get_data")
        return jsonify(error=str(e)), 500

@app.route("/api/sensitive")
def get_sensitive_data():
    """Example of using PQC for sensitive operations."""
    try:
        # Track API request
        prometheus_metrics.increment_api_requests("get_sensitive_data")

        # Example: Encrypt sensitive data using PQC
        sensitive_data = "This is sensitive information"
        encrypted_data = pqc_core.encrypt_sensitive_data(sensitive_data)

        return jsonify(encrypted_data=encrypted_data)
    except Exception as e:
        prometheus_metrics.increment_api_errors("get_sensitive_data")
        return jsonify(error=str(e)), 500

def main():
    """Main entry point."""
    global self_healing_manager, pqc_core, mesh_router, prometheus_metrics

    print("🚀 Integrating x0tta6bl4 into existing Flask application")
    print("=" * 60)

    # Step 1: Initialize x0tta6bl4 components
    print("\n📦 Initializing x0tta6bl4 components...")
    try:
        # Initialize Prometheus metrics
        prometheus_metrics = PrometheusMetrics()

        # Initialize PQC core for encryption/decryption
        pqc_core = PQCCore()

        # Initialize mesh router for self-healing network
        mesh_router = MeshRouter(node_id="flask-app-1")

        # Initialize self-healing manager
        self_healing_manager = SelfHealingManager(node_id="flask-app-1")
        self_healing_manager.start_monitoring()

        print("✅ x0tta6bl4 components initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize x0tta6bl4 components: {e}")
        import sys
        sys.exit(1)

    # Step 2: Start Flask app
    print("\n🌐 Starting Flask application...")
    app.run(debug=True, port=5000)

    # Step 3: Stop x0tta6bl4 components
    print("\n🛑 Stopping x0tta6bl4 components...")
    self_healing_manager.stop_monitoring()

if __name__ == "__main__":
    main()
