"""
CLI tool to check X0T balance and earnings.
"""
import argparse
from decimal import Decimal
import random
import logging

logging.basicConfig(level=logging.ERROR)

def main():
    parser = argparse.ArgumentParser(description="Check X0T balance")
    parser.add_argument("--detailed", action="store_true", help="Show detailed earnings")
    args = parser.parse_args()
    
    # Simulated values for demo (consistent with dashboard)
    balance = Decimal("1000.0")
    earnings_today = Decimal("1.27")
    packets = 127
    uptime = 98.5
    
    if args.detailed:
        print(f"💰 Баланс: {balance:,.4f} X0T")
        print(f"📊 Пакетов: {packets}")
        print(f"⏱️ Uptime: {uptime}%")
        print(f"💵 Заработок сегодня: {earnings_today:,.4f} X0T")
        print(f"💵 Месячная проекция: {earnings_today * 30:,.2f} X0T (${earnings_today * 30 * Decimal('0.1'):,.2f} @ $0.10)")
    else:
        print(f"   Баланс: {balance:,.1f} X0T")

if __name__ == "__main__":
    main()
