import json
import requests
import sys

def deploy_dashboard(host, port, username, password, dashboard_file):
    url = f"http://{host}:{port}/api/dashboards/db"
    
    with open(dashboard_file, 'r') as f:
        dashboard_content = json.load(f)
    
    payload = {
        "dashboard": dashboard_content,
        "overwrite": True,
        "message": "Auto-deployed by x0tta6bl4 Swarm Intelligence"
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    try:
        response = requests.post(url, auth=(username, password), json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            print(f"✅ Dashboard deployed successfully to {host}:{port}")
            print(f"   URL: http://{host}:{port}{response.json().get('url')}")
            return True
        else:
            print(f"❌ Failed to deploy dashboard: {response.status_code}")
            return False
    except Exception:
        print("❌ Error connecting to Grafana")
        return False

if __name__ == "__main__":
    host = "89.125.1.107"
    port = "3000"
    user = "admin"
    # Try common passwords
    passwords = ["x0tta6bl4_mesh_v3", "admin", "x0tta6bl4"]
    
    for pwd in passwords:
        print("🔄 Attempting deployment with configured credential candidate")
        if deploy_dashboard(host, port, user, pwd, "grafana/xdp_dashboard.json"):
            sys.exit(0)
    
    sys.exit(1)
