class PrometheusExporter:
    def __init__(self):
        self.metrics = {}

    def set_gauge(self, name: str, value: float):
        self.metrics[name] = value
        # In a real implementation, this would update prometheus client
