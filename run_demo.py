#!/usr/bin/env python3
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Set demo mode
os.environ['DEMO_MODE'] = 'true'
os.environ['NODE_ID'] = 'demo-node-001'
os.environ['RPC_URL'] = 'https://sepolia.base.org'
os.environ['OPERATOR_PRIVATE_KEY'] = '0x' + '1' * 64  # Dummy key

# Run the app
if __name__ == '__main__':
    from app import create_app
    app = create_app()
    print("✅ x0tta6bl4 Node started in DEMO MODE")
    print("📊 Dashboard: http://localhost:8080")
    app.run(host='0.0.0.0', port=8080, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
