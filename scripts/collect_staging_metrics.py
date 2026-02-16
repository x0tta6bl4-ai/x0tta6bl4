#!/usr/bin/env python3
"""
Скрипт для сбора реальных метрик из staging deployment

Использование:
    python scripts/collect_staging_metrics.py --namespace x0tta6bl4-staging
    python scripts/collect_staging_metrics.py --url http://staging.x0tta6bl4.io
"""

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
RESULTS_DIR = PROJECT_ROOT / "benchmarks" / "results"


def collect_kubectl_metrics(namespace: str) -> Dict:
    """Сбор метрик через kubectl"""
    logger.info(f"Сбор метрик через kubectl из namespace: {namespace}")

    metrics = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": "kubectl",
        "namespace": namespace,
        "pods": {},
        "services": {},
        "deployments": {},
        "metrics": {},
    }

    try:
        # Pods
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
            capture_output=True,
            text=True,
            check=True,
        )
        pods_data = json.loads(result.stdout)

        for pod in pods_data.get("items", []):
            pod_name = pod["metadata"]["name"]
            metrics["pods"][pod_name] = {
                "status": pod["status"].get("phase"),
                "restarts": pod["status"]
                .get("containerStatuses", [{}])[0]
                .get("restartCount", 0),
                "ready": pod["status"].get("conditions", []),
                "created": pod["metadata"].get("creationTimestamp"),
            }

        # Services
        result = subprocess.run(
            ["kubectl", "get", "svc", "-n", namespace, "-o", "json"],
            capture_output=True,
            text=True,
            check=True,
        )
        services_data = json.loads(result.stdout)

        for svc in services_data.get("items", []):
            svc_name = svc["metadata"]["name"]
            metrics["services"][svc_name] = {
                "type": svc["spec"].get("type"),
                "ports": [
                    {"port": p.get("port"), "targetPort": p.get("targetPort")}
                    for p in svc["spec"].get("ports", [])
                ],
                "selector": svc["spec"].get("selector", {}),
            }

        # Deployments
        result = subprocess.run(
            ["kubectl", "get", "deployments", "-n", namespace, "-o", "json"],
            capture_output=True,
            text=True,
            check=True,
        )
        deployments_data = json.loads(result.stdout)

        for deploy in deployments_data.get("items", []):
            deploy_name = deploy["metadata"]["name"]
            metrics["deployments"][deploy_name] = {
                "replicas": deploy["spec"].get("replicas"),
                "ready_replicas": deploy["status"].get("readyReplicas", 0),
                "available_replicas": deploy["status"].get("availableReplicas", 0),
            }

        logger.info(
            f"✅ Собрано метрик: {len(metrics['pods'])} pods, {len(metrics['services'])} services"
        )

    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при выполнении kubectl: {e}")
        logger.error(f"Вывод: {e.stderr}")
    except FileNotFoundError:
        logger.warning("kubectl не найден. Пропускаю сбор метрик через kubectl.")

    return metrics


def collect_api_metrics(url: str) -> Dict:
    """Сбор метрик через API"""
    logger.info(f"Сбор метрик через API: {url}")

    metrics = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": "api",
        "url": url,
        "endpoints": {},
    }

    # Health check
    try:
        response = requests.get(f"{url}/health", timeout=5)
        if response.status_code == 200:
            metrics["endpoints"]["health"] = response.json()
            logger.info("✅ Health check успешен")
        else:
            logger.warning(f"Health check вернул статус: {response.status_code}")
    except Exception as e:
        logger.warning(f"Не удалось получить health check: {e}")

    # Dependencies check
    try:
        response = requests.get(f"{url}/health/dependencies", timeout=5)
        if response.status_code == 200:
            metrics["endpoints"]["dependencies"] = response.json()
            logger.info("✅ Dependencies check успешен")
    except Exception as e:
        logger.warning(f"Не удалось получить dependencies check: {e}")

    # Metrics endpoint (Prometheus format)
    try:
        response = requests.get(f"{url}/metrics", timeout=10)
        if response.status_code == 200:
            metrics["endpoints"]["prometheus_metrics"] = response.text[
                :10000
            ]  # Первые 10KB
            logger.info("✅ Prometheus metrics получены")
    except Exception as e:
        logger.warning(f"Не удалось получить Prometheus metrics: {e}")

    return metrics


def collect_prometheus_metrics(prometheus_url: Optional[str] = None) -> Dict:
    """Сбор метрик из Prometheus (если доступен)"""
    if not prometheus_url:
        logger.info("Prometheus URL не указан. Пропускаю сбор метрик из Prometheus.")
        return {}

    logger.info(f"Сбор метрик из Prometheus: {prometheus_url}")

    metrics = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": "prometheus",
        "url": prometheus_url,
        "queries": {},
    }

    # Примеры запросов
    queries = {
        "error_rate": 'rate(http_requests_total{status=~"5.."}[5m])',
        "request_latency_p95": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
        "cpu_usage": "avg(rate(container_cpu_usage_seconds_total[5m]))",
        "memory_usage": "avg(container_memory_usage_bytes)",
    }

    for query_name, query in queries.items():
        try:
            response = requests.get(
                f"{prometheus_url}/api/v1/query", params={"query": query}, timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                metrics["queries"][query_name] = data.get("data", {})
                logger.info(f"✅ Запрос {query_name} выполнен")
        except Exception as e:
            logger.warning(f"Не удалось выполнить запрос {query_name}: {e}")

    return metrics


def save_metrics(metrics: Dict, filename: str):
    """Сохранение метрик в файл"""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = RESULTS_DIR / filename

    with open(filepath, "w") as f:
        json.dump(metrics, f, indent=2)

    logger.info(f"✅ Метрики сохранены в: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="Сбор метрик из staging deployment")
    parser.add_argument(
        "--namespace", default="x0tta6bl4-staging", help="Kubernetes namespace"
    )
    parser.add_argument("--url", help="Staging API URL")
    parser.add_argument("--prometheus-url", help="Prometheus URL")
    parser.add_argument("--output", help="Output filename")

    args = parser.parse_args()

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    all_metrics = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "staging_namespace": args.namespace,
        "staging_url": args.url,
        "metrics": {},
    }

    # Сбор через kubectl
    if args.namespace:
        kubectl_metrics = collect_kubectl_metrics(args.namespace)
        all_metrics["metrics"]["kubectl"] = kubectl_metrics

    # Сбор через API
    if args.url:
        api_metrics = collect_api_metrics(args.url)
        all_metrics["metrics"]["api"] = api_metrics

    # Сбор из Prometheus
    if args.prometheus_url:
        prometheus_metrics = collect_prometheus_metrics(args.prometheus_url)
        all_metrics["metrics"]["prometheus"] = prometheus_metrics

    # Сохранение
    filename = args.output or f"staging_metrics_{timestamp}.json"
    save_metrics(all_metrics, filename)

    logger.info("✅ Сбор метрик завершен")
    return 0


if __name__ == "__main__":
    sys.exit(main())
