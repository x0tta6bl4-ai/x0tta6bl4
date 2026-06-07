import os
import subprocess
import threading
import time
from flask import Flask, request, jsonify, send_from_directory

# Initialize Flask to serve static files from current directory
app = Flask(__name__, static_folder='.', static_url_path='')

# Configuration for Ghost Pulse VPN
VPN_ENCRYPTION_KEY = "VMYlEF9wQr47XZb4x+V1J57SWj4/bdNLVXWquSXaCyM="
VPN_SERVER = "89.125.1.107"
VPN_PORT = "9999"
PULSE_MODE = "corporate"

vpn_process = None

def run_vpn():
    global vpn_process
    env = os.environ.copy()
    env["VPN_ENCRYPTION_KEY"] = VPN_ENCRYPTION_KEY
    env["VPN_SERVER"] = VPN_SERVER
    env["VPN_PORT"] = VPN_PORT
    env["PULSE_MODE"] = PULSE_MODE

    # Run the client script with sudo -E to preserve env
    cmd = ["sudo", "-E", "python3", "ghost_pulse_vpn.py", "client"]

    try:
        vpn_process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print(f"VPN Process started (PID: {vpn_process.pid})")
        stdout, stderr = vpn_process.communicate()
        print(f"VPN Exit: {stdout} {stderr}")
    except Exception as e:
        print(f"VPN Launch Error: {e}")

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/vpn/toggle', methods=['POST'])
def toggle_vpn():
    global vpn_process
    data = request.json
    active = data.get('active', False)

    if active:
        if vpn_process and vpn_process.poll() is None:
            return jsonify({"status": "Connected", "message": "Already running"})

        thread = threading.Thread(target=run_vpn)
        thread.daemon = True
        thread.start()

        time.sleep(2)
        return jsonify({"status": "Connected"})
    else:
        if vpn_process:
            subprocess.run(["sudo", "pkill", "-f", "ghost_pulse_vpn.py"])
            vpn_process = None

        return jsonify({"status": "Disconnected"})

@app.route('/api/vpn/status', methods=['GET'])
def vpn_status():
    result = subprocess.run(["ip", "addr", "show", "x0t-clnt0"], capture_output=True)
    is_up = result.returncode == 0
    return jsonify({
        "status": "Connected" if is_up else "Disconnected",
        "interface": "x0t-clnt0" if is_up else None
    })

if __name__ == '__main__':
    # Safely pkill old instances without sudo if possible, or just skip it
    # subprocess.run(["pkill", "-f", "ghost_pulse_vpn.py"])

    print("Starting x0tta6bl4 VPN GUI Backend on http://localhost:8089")
    app.run(host='127.0.0.1', port=8089)
