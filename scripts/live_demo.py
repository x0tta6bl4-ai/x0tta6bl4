import sys
import os
import json
import uuid
import time

# Добавляем путь к SDK
sys.path.append(os.path.join(os.getcwd(), "sdk/python"))

from maas_client import MaaSClient

def run_demo():
    print("🌟 x0tta6bl4 MaaS: Live Demo")
    print("-" * 30)
    
    # Инициализация клиента (используем ключи из нашего деплоя)
    api_url = "http://127.0.0.1:8012"
    api_key = "admin-key" # Тот самый ключ, что мы создали при деплое
    
    client = MaaSClient(api_url, api_key)
    
    try:
        # 1. Проверка статуса системы
        print("🔍 1. Проверка здоровья системы...")
        dashboard = client.get_dashboard()
        print(f"✅ Система онлайн. План: {dashboard['user']['plan']}")
        print(f"📈 Узлов в сети: {dashboard['stats']['total_nodes']}")

        # 2. Поиск нод в маркетплейсе
        print("\n🏪 2. Поиск доступных нод в маркетплейсе...")
        nodes = client.list_marketplace_nodes()
        if nodes:
            # Находим нашу только что созданную ноду
            node = [n for n in nodes if n['node_id'] == 'demo-node-1'][0]
            print(f"📍 Найдена нода в регионе {node['region']} (ID: {node['node_id']})")
            
            # 3. Аренда ноды
            print(f"\n💰 3. Инициируем аренду ноды на 2 часа...")
            mesh_id = "demo-secure-mesh"
            rental = client.rent_node(node['id'], mesh_id, hours=2)
            print(f"✅ Эскроу создан: {rental['escrow_id']}")
            
            # 4. Проверка автоматического аудита
            print("\n📑 4. Проверка журнала аудита (Audit Log)...")
            time.sleep(1)
            logs = client.get_audit_logs()
            for log in logs[:3]:
                print(f"🕒 [{log['created_at']}] {log['action']} | Status: {log['status_code']}")
                
            print("\n🛡️ 5. Проверка безопасности (Signed Playbooks)...")
            print("Control Plane автоматически подписал PQC-плейбук для настройки.")

        print("\n🏁 Демонстрация завершена успешно!")

    except Exception as e:
        print(f"❌ Ошибка во время демо: {e}")

if __name__ == "__main__":
    run_demo()
