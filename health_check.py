#!/usr/bin/env python3
"""
Health check для x0tta6bl4 системы
Проверяет работоспособность всех компонентов
"""

import sys
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_database():
    """Check database connectivity"""
    try:
        from database import get_user_stats, init_database
        stats = get_user_stats()
        logger.info(f"✅ Database: OK (Users: {stats['total_users']})")
        return True
    except Exception as e:
        logger.error(f"❌ Database: FAILED - {e}")
        return False

def check_vpn_generator():
    """Check VPN config generator"""
    try:
        from vpn_config_generator import generate_vless_link, generate_config_text
        link = generate_vless_link()
        config = generate_config_text(12345)
        logger.info("✅ VPN Generator: OK")
        return True
    except Exception as e:
        logger.error(f"❌ VPN Generator: FAILED - {e}")
        return False

def check_qr_generator():
    """Check QR code generator"""
    try:
        from qr_code_generator import generate_qr_code_for_vless
        test_link = "vless://test@example.com:443"
        qr = generate_qr_code_for_vless(test_link)
        if qr:
            logger.info("✅ QR Generator: OK")
            return True
        else:
            logger.warning("⚠️ QR Generator: Not available (qrcode not installed)")
            return True  # Not critical
    except ImportError:
        logger.warning("⚠️ QR Generator: Not available (qrcode not installed)")
        return True  # Not critical
    except Exception as e:
        logger.error(f"❌ QR Generator: FAILED - {e}")
        return False

def check_admin_commands():
    """Check admin commands"""
    try:
        from admin_commands import is_admin, get_admin_stats
        logger.info("✅ Admin Commands: OK")
        return True
    except ImportError:
        logger.warning("⚠️ Admin Commands: Not available")
        return True  # Not critical
    except Exception as e:
        logger.error(f"❌ Admin Commands: FAILED - {e}")
        return False

def main():
    """Run all health checks"""
    print("🏥 x0tta6bl4 Health Check")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    checks = [
        ("Database", check_database),
        ("VPN Generator", check_vpn_generator),
        ("QR Generator", check_qr_generator),
        ("Admin Commands", check_admin_commands),
    ]
    
    results = []
    for name, check_func in checks:
        result = check_func()
        results.append((name, result))
    
    print()
    print("=" * 50)
    print("📊 Summary:")
    
    all_ok = True
    for name, result in results:
        status = "✅ OK" if result else "❌ FAILED"
        print(f"  {name}: {status}")
        if not result:
            all_ok = False
    
    print()
    if all_ok:
        print("✅ All critical checks passed!")
        return 0
    else:
        print("❌ Some checks failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())

