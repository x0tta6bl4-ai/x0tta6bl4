import json
import time
import random
from http.server import BaseHTTPRequestHandler, HTTPServer

class TelemetrySim(BaseHTTPRequestHandler):
    """Simulates a mesh node API for the dashboard."""
    
    start_time = time.time()
    mesh_status = "ALIVE"
    node_count = 142
    
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With, Content-Type")

    def do_GET(self):
        if self.path == '/api/stats':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self._send_cors_headers()
            self.end_headers()
            
            uptime = int(time.time() - self.start_time)
            
            # Simulate slight fluctuations
            current_nodes = self.node_count + random.randint(-2, 2)
            
            data = {
                "mesh": {
                    "status": self.mesh_status,
                    "peers": current_nodes - 1,
                    "mttr": 2.45
                },
                "uptime": uptime,
                "mem_usage": f"{random.randint(120, 150)}MB",
                "pqc_entropy": "0.998" if self.mesh_status == "ALIVE" else "0.000"
            }
            self.wfile.write(json.dumps(data).encode())
            
        elif self.path == '/':
            # Serve the dashboard file
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('src/web/dashboard.html', 'rb') as f:
                self.wfile.write(f.read())

    def do_POST(self):
        if self.path == '/api/inject-fault':
            self.send_response(200)
            self._send_cors_headers()
            self.end_headers()
            
            # Trigger "Self-healing" sequence
            print("!!! FAULT INJECTED - Starting MAPE-K cycle !!!")
            self.mesh_status = "RECOVERING"
            
            # In a real scenario, this would trigger actual node logic
            # Here we just respond OK
            self.wfile.write(json.dumps({"status": "healing"}).encode())

def run(port=8080):
    server_address = ('', port)
    httpd = HTTPServer(server_address, TelemetrySim)
    print(f"🧭 Telemetry Sim running on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
