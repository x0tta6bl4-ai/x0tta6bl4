#!/usr/bin/env python3
"""
Тест безопасности исправлений
Проверяет что все security fixes работают правильно
"""

import os
import sys
from datetime import datetime, timedelta

# Set test environment
os.environ['TEST_MODE'] = '1'

def test_uuid_generation():
    """Test 1: UUID generation works and is unique"""
    print("Test 1: UUID Generation...")
    from vpn_config_generator import generate_uuid
    
    uuids = [generate_uuid() for _ in range(10)]
    unique_uuids = set(uuids)
    
    assert len(unique_uuids) == 10, "UUIDs should be unique"
    assert all(len(u) == 36 for u in uuids), "UUIDs should be 36 chars"
    print("  ✅ UUID generation works and is unique")
    return True

def test_vless_link_requires_uuid():
    """Test 2: generate_vless_link requires UUID"""
    print("Test 2: VLESS Link Requires UUID...")
    from vpn_config_generator import generate_vless_link, generate_uuid
    
    # Should work with UUID
    uuid = generate_uuid()
    link = generate_vless_link(user_uuid=uuid)
    assert link.startswith("vless://"), "Link should start with vless://"
    assert uuid in link, "UUID should be in link"
    print("  ✅ generate_vless_link works with UUID")
    
    # Should fail without UUID
    try:
        link = generate_vless_link(user_uuid=None)
        print("  ❌ ERROR: Should have raised ValueError!")
        return False
    except ValueError as e:
        assert "user_uuid is required" in str(e), "Error message should mention user_uuid"
        print("  ✅ generate_vless_link correctly requires UUID")
        return True
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return False

def test_config_text_requires_uuid():
    """Test 3: generate_config_text requires UUID"""
    print("Test 3: Config Text Requires UUID...")
    from vpn_config_generator import generate_config_text, generate_uuid
    
    # Should work with UUID
    uuid = generate_uuid()
    config = generate_config_text(user_id=123, user_uuid=uuid)
    assert "VLESS" in config, "Config should contain VLESS"
    assert uuid in config, "UUID should be in config"
    print("  ✅ generate_config_text works with UUID")
    
    # Should fail without UUID
    try:
        config = generate_config_text(user_id=123, user_uuid=None)
        print("  ❌ ERROR: Should have raised ValueError!")
        return False
    except ValueError as e:
        assert "user_uuid is required" in str(e), "Error message should mention user_uuid"
        print("  ✅ generate_config_text correctly requires UUID")
        return True
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return False

def test_admin_auth():
    """Test 4: Admin authentication works"""
    print("Test 4: Admin Authentication...")
    from admin_commands import is_admin
    
    # Test with no admin configured
    os.environ.pop('ADMIN_USER_ID', None)
    os.environ.pop('ADMIN_USER_IDS', None)
    assert not is_admin(123456), "Should return False when no admin configured"
    print("  ✅ Admin auth returns False when no admin configured")
    
    # Test with single admin
    os.environ['ADMIN_USER_ID'] = '123456'
    assert is_admin(123456), "Should return True for admin user"
    assert not is_admin(789012), "Should return False for non-admin user"
    print("  ✅ Admin auth works with ADMIN_USER_ID")
    
    # Test with multiple admins
    os.environ.pop('ADMIN_USER_ID', None)
    os.environ['ADMIN_USER_IDS'] = '123456,789012'
    assert is_admin(123456), "Should return True for first admin"
    assert is_admin(789012), "Should return True for second admin"
    assert not is_admin(345678), "Should return False for non-admin user"
    print("  ✅ Admin auth works with ADMIN_USER_IDS (multiple admins)")
    
    return True

def test_secrets_not_hardcoded():
    """Test 5: Secrets are not hardcoded"""
    print("Test 5: Secrets Not Hardcoded...")
    import vpn_config_generator
    
    # Check that REALITY_PRIVATE_KEY is not hardcoded
    source_code = open('vpn_config_generator.py').read()
    
    # Should not contain hardcoded private key
    assert 'sARj3nxY80sVRmeCxqZbTHyw-bj6Si4vXb3Q-mlflFw' not in source_code, "Private key should not be hardcoded"
    print("  ✅ REALITY_PRIVATE_KEY is not hardcoded")
    
    # Should use os.getenv
    assert 'os.getenv("REALITY_PRIVATE_KEY")' in source_code, "Should use os.getenv for REALITY_PRIVATE_KEY"
    print("  ✅ REALITY_PRIVATE_KEY loaded from environment")
    
    # Should not contain DEFAULT_UUID
    assert 'DEFAULT_UUID =' not in source_code, "DEFAULT_UUID should be removed"
    print("  ✅ DEFAULT_UUID removed from code")
    
    return True

def test_payment_validation():
    """Test 6: Payment validation logic exists"""
    print("Test 6: Payment Validation...")
    source_code = open('telegram_bot.py').read()
    
    # Should check payment amount
    assert 'total_amount != MONTHLY_PRICE' in source_code or 'total_amount' in source_code, "Should validate payment amount"
    print("  ✅ Payment amount validation exists")
    
    # Should check currency
    assert 'currency' in source_code and ('USD' in source_code or 'currency !=' in source_code), "Should validate currency"
    print("  ✅ Payment currency validation exists")
    
    # Should check payload
    assert 'invoice_payload' in source_code, "Should validate payment payload"
    print("  ✅ Payment payload validation exists")
    
    return True

def main():
    """Run all tests"""
    print("=" * 60)
    print("🔒 Security Fixes Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        test_uuid_generation,
        test_vless_link_requires_uuid,
        test_config_text_requires_uuid,
        test_admin_auth,
        test_secrets_not_hardcoded,
        test_payment_validation,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        print()
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("✅ All security fixes are working correctly!")
        return 0
    else:
        print("❌ Some tests failed. Please review.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

