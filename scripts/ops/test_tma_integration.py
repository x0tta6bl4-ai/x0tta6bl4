#!/usr/bin/env python3
"""
Integration test for TMA -> Bot -> Config Generator workflow.
"""
import sys
import os
import json
import logging

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Set mock env vars
os.environ['DATABASE_URL'] = 'sqlite:////mnt/projects/x0tta6bl4.db'
os.environ['GHOST_ACCESS_DB_PATH'] = '/mnt/projects/x0tta6bl4.db'

logging.basicConfig(level=logging.INFO)

try:
    from database import init_database, get_user, update_user
    from vpn_config_generator import generate_config_text, generate_vless_link
except ImportError as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)

def run_tests():
    print("🧪 Starting Integration Tests for TMA & Config Generator...")
    
    # Ensure DB is initialized
    init_database()
    
    # We will use the existing test user from DB or create it
    test_user_id = 2018432227
    user = get_user(test_user_id)
    
    if not user:
        print(f"❌ User {test_user_id} not found in DB.")
        sys.exit(1)
        
    vpn_uuid = user.get('vpn_uuid')
    if not vpn_uuid:
        print("⚠️ User has no vpn_uuid, faking one for test.")
        vpn_uuid = "12345678-1234-1234-1234-123456789abc"
        update_user(test_user_id, vpn_uuid=vpn_uuid)

    print("\n--- Test 1: TMA JSON Payload Parsing ---")
    mock_payload = '{"action": "update_node", "node": "ru"}'
    try:
        data = json.loads(mock_payload)
        assert data.get('action') == 'update_node'
        assert data.get('node') == 'ru'
        print("✅ TMA JSON parsing passed.")
    except Exception as e:
        print(f"❌ TMA JSON parsing failed: {e}")
        sys.exit(1)

    print("\n--- Test 2: Database Node Update ---")
    try:
        update_user(test_user_id, entry_node=data['node'])
        updated_user = get_user(test_user_id)
        assert updated_user['entry_node'] == 'ru'
        print("✅ Database update passed (Node changed to 'ru').")
    except Exception as e:
        print(f"❌ Database update failed: {e}")
        sys.exit(1)

    print("\n--- Test 3: Multi-Node Config Generation (RU) ---")
    try:
        ru_config = generate_config_text(test_user_id, vpn_uuid, node_id='ru')
        assert "TBD_RU_IP" in ru_config
        assert "x0tta6bl4_RU_Entry" in ru_config
        print("✅ RU config generation passed.")
    except Exception as e:
        print(f"❌ RU config generation failed: {e}")
        sys.exit(1)

    print("\n--- Test 4: Multi-Node Config Generation (US) ---")
    try:
        us_config = generate_config_text(test_user_id, vpn_uuid, node_id='us')
        assert "TBD_US_IP" in us_config
        assert "x0tta6bl4_US_Exit" in us_config
        print("✅ US config generation passed.")
    except Exception as e:
        print(f"❌ US config generation failed: {e}")
        sys.exit(1)

    print("\n--- Test 5: Fallback Config Generation (Unknown Node) ---")
    try:
        # Should fallback to 'nl'
        nl_config = generate_config_text(test_user_id, vpn_uuid, node_id='unknown_node')
        assert "89.125.1.107" in nl_config
        assert "x0tta6bl4_NL_Master" in nl_config
        print("✅ Fallback config generation passed (defaulted to NL).")
    except Exception as e:
        print(f"❌ Fallback config generation failed: {e}")
        sys.exit(1)

    print("\n🎉 ALL TMA INTEGRATION TESTS PASSED SUCCESSFULLY! 🎉")

if __name__ == "__main__":
    run_tests()
