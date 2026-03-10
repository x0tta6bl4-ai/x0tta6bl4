import unittest
from unittest.mock import patch, MagicMock
import sqlite3
import json
import os
import subprocess
from vpn_config_generator import XUIAPIClient

class TestXUIAPIClient(unittest.TestCase):
    def setUp(self):
        # Использование временной БД для тестов
        self.test_db = "/tmp/test_xui_unit.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
            
        # Настройка БД с начальными данными
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE inbounds (
                id INTEGER PRIMARY KEY,
                port INTEGER,
                stream_settings TEXT
            )
        """)
        
        # Начальные настройки Reality с двумя ID: ["6b", "b2c4"]
        initial_settings = {
            "realitySettings": {
                "privateKey": "OLD_PRIVATE_KEY",
                "shortIds": ["6b", "b2c4"]
            }
        }
        
        # Порт 443 согласно плану Codex
        cursor.execute("INSERT INTO inbounds (port, stream_settings) VALUES (?, ?)", 
                       (443, json.dumps(initial_settings)))
        conn.commit()
        conn.close()
        
        # Инициализация клиента
        self.client = XUIAPIClient(db_path=self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    @patch('subprocess.run')
    def test_rotate_reality_credentials_unit(self, mock_run):
        # 1. Мок subprocess.run для возврата фейковых ключей xray
        # Формат: Private key: <key>\nPublic key: <key>
        fake_stdout = "Private key: FAKE_PRIV_KEY_LENGTH_LONG_ENOUGH_FOR_VALIDATION\nPublic key: FAKE_PUB_KEY_LENGTH_LONG_ENOUGH_FOR_VALIDATION"
        mock_run.return_value = MagicMock(stdout=fake_stdout, returncode=0)
        
        # Устанавливаем порт 443 в модуле (как это делает vpn_config_generator)
        import vpn_config_generator
        vpn_config_generator.VPN_PORT = 443
        
        # 2. Вызов метода ротации
        result = self.client.rotate_reality_credentials()
        
        # 3. Валидация вызова subprocess
        mock_run.assert_any_call(["xray", "x25519"], capture_output=True, text=True, check=True, timeout=10)
        
        # 4. Проверка результата в БД
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT stream_settings FROM inbounds WHERE port = 443")
        updated_json = cursor.fetchone()[0]
        updated_settings = json.loads(updated_json)
        conn.close()
        
        new_short_ids = updated_settings["realitySettings"]["shortIds"]
        new_private_key = updated_settings["realitySettings"]["privateKey"]
        
        # Требования из скриншота 00:47:
        # - len(shortIds) == 3 (добавился новый)
        # - "6b" и "b2c4" всё ещё в списке
        # - shortIds не стал списком из 1 элемента
        self.assertEqual(len(new_short_ids), 3, f"Ожидалось 3 ID, получено {len(new_short_ids)}: {new_short_ids}")
        self.assertIn("6b", new_short_ids)
        self.assertIn("b2c4", new_short_ids)
        self.assertNotEqual(len(new_short_ids), 1, "Список shortIds не должен перезаписываться одним элементом!")
        
        # Проверка обновления ключа
        self.assertEqual(new_private_key, "FAKE_PRIV_KEY_LENGTH_LONG_ENOUGH_FOR_VALIDATION")
        
        print("\n✅ T-3 TEST PASSED: rotate_reality_credentials logic verified with mocks.")

if __name__ == '__main__':
    unittest.main()
