#!/usr/bin/env python3
import os
import sys
from vpn_config_generator import XUIAPIClient, generate_vless_link
import json

# Load .env (simplified)
def load_env():
    try:
        with open(".env", "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ[k] = v
    except FileNotFoundError:
        pass

load_env()

def run_demo():
    print("🚀 Running x0tta6bl4 Commercial Prototype Demo...")
    print(f"📂 DB Path: {os.getenv('XUI_DB_PATH')}")
    print(f"🔑 Private Key: {'Set' if os.getenv('REALITY_PRIVATE_KEY') else 'Not Set'}")
    
    try:
        xui = XUIAPIClient()
        email = "demo_user@x0tta6bl4.com"
        
        print(f"\n1️⃣ Provisioning user: {email}...")
        result = xui.create_user(user_id=888, email=email, remark="demo_commercial_test")
        
        print("\n✅ SUCCESS! Real VPN account created in x-ui.db")
        print(f"🔗 VLESS Link:")
        print(f"\033[96m{result['vless_link']}\033[0m")
        print("\nЭто реальная ссылка. Вы можете вставить ее в v2rayNG или Nekobox прямо сейчас.")
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")

if __name__ == "__main__":
    run_demo()
