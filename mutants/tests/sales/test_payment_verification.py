# tests/sales/test_payment_verification.py
import unittest
from unittest.mock import patch, Mock
from datetime import datetime, timedelta
import requests

from src.sales.payment_verification import TronScanVerifier, TONVerifier

class TestTronScanVerifier(unittest.TestCase):

    def setUp(self):
        self.verifier = TronScanVerifier(api_key="test-key")
        self.wallet_address = "TXYZ..."
        self.order_id = "ORDER-123"
        self.expected_amount = 10.0

    @patch('requests.get')
    def test_verify_payment_success(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "transaction_id": "tx123",
                    "value": "10000000",
                    "block_timestamp": int(datetime.now().timestamp() * 1000),
                    "memo": "Payment for ORDER-123",
                    "to": self.wallet_address,
                }
            ]
        }
        mock_get.return_value = mock_response

        result = self.verifier.verify_payment(self.wallet_address, self.expected_amount, self.order_id)
        
        self.assertTrue(result['verified'])
        self.assertEqual(result['transaction_hash'], 'tx123')
        self.assertEqual(result['amount'], 10.0)
        self.assertIsNone(result['error'])

    @patch('requests.get')
    def test_no_matching_transaction_found(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response

        result = self.verifier.verify_payment(self.wallet_address, self.expected_amount, self.order_id)
        
        self.assertFalse(result['verified'])
        self.assertEqual(result['error'], 'No transactions found')

    @patch('requests.get')
    def test_transaction_too_old(self, mock_get):
        two_days_ago = datetime.now() - timedelta(days=2)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "transaction_id": "tx123",
                    "value": "10000000",
                    "block_timestamp": int(two_days_ago.timestamp() * 1000),
                    "memo": "Payment for ORDER-123",
                    "to": self.wallet_address,
                }
            ]
        }
        mock_get.return_value = mock_response

        result = self.verifier.verify_payment(self.wallet_address, self.expected_amount, self.order_id)
        
        self.assertFalse(result['verified'])
        self.assertEqual(result['error'], 'No matching transaction found')

    @patch('requests.get')
    def test_memo_does_not_match(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "transaction_id": "tx123",
                    "value": "10000000",
                    "block_timestamp": int(datetime.now().timestamp() * 1000),
                    "memo": "Payment for something else",
                    "to": self.wallet_address,
                }
            ]
        }
        mock_get.return_value = mock_response

        result = self.verifier.verify_payment(self.wallet_address, self.expected_amount, self.order_id)
        
        self.assertFalse(result['verified'])
        self.assertEqual(result['error'], 'No matching transaction found')

    @patch('requests.get')
    def test_amount_is_incorrect(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "transaction_id": "tx123",
                    "value": "5000000", # 5 USDT instead of 10
                    "block_timestamp": int(datetime.now().timestamp() * 1000),
                    "memo": "Payment for ORDER-123",
                    "to": self.wallet_address,
                }
            ]
        }
        mock_get.return_value = mock_response

        result = self.verifier.verify_payment(self.wallet_address, self.expected_amount, self.order_id)
        
        self.assertFalse(result['verified'])
        self.assertEqual(result['error'], 'No matching transaction found')

    @patch('requests.get')
    def test_api_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("Connection error")

        result = self.verifier.verify_payment(self.wallet_address, self.expected_amount, self.order_id)
        
        self.assertFalse(result['verified'])
        self.assertIn("API request failed", result['error'])

    @patch('requests.get')
    def test_malformed_response(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"invalid_data": []}
        mock_get.return_value = mock_response

        result = self.verifier.verify_payment(self.wallet_address, self.expected_amount, self.order_id)
        
        self.assertFalse(result['verified'])
        self.assertEqual(result['error'], 'No transactions found')



class TestTONVerifier(unittest.TestCase):

    def setUp(self):
        self.verifier = TONVerifier(api_key="test-key-ton")
        self.wallet_address = "UQ..."
        self.order_id = "ORDER-456"
        self.expected_amount = 5.0

    @patch('requests.get')
    def test_verify_payment_success(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "transactions": [
                {
                    "hash": "ton_tx123",
                    "utime": int(datetime.now().timestamp()),
                    "success": True,
                    "in_msg": {
                        "value": "5000000000",
                        "source": "UQ...",
                        "destination": { "address": self.wallet_address },
                        "message": "ORDER-456",
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        result = self.verifier.verify_payment(self.wallet_address, self.expected_amount, self.order_id)

        self.assertTrue(result['verified'])
        self.assertEqual(result['transaction_hash'], 'ton_tx123')
        self.assertEqual(result['amount'], 5.0)
        self.assertIsNone(result['error'])

    @patch('requests.get')
    def test_no_matching_transaction_found(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"transactions": []}
        mock_get.return_value = mock_response

        result = self.verifier.verify_payment(self.wallet_address, self.expected_amount, self.order_id)
        
        self.assertFalse(result['verified'])
        self.assertEqual(result['error'], 'No transactions found')

    @patch('requests.get')
    def test_transaction_too_old(self, mock_get):
        two_days_ago = datetime.now() - timedelta(days=2)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "transactions": [
                {
                    "hash": "ton_tx123",
                    "utime": int(two_days_ago.timestamp()),
                    "success": True,
                    "in_msg": {
                        "value": "5000000000",
                        "source": "UQ...",
                        "destination": { "address": self.wallet_address },
                        "message": "ORDER-456",
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        result = self.verifier.verify_payment(self.wallet_address, self.expected_amount, self.order_id)
        
        self.assertFalse(result['verified'])
        self.assertEqual(result['error'], 'No matching transaction found')

    @patch('requests.get')
    def test_comment_does_not_match(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "transactions": [
                {
                    "hash": "ton_tx123",
                    "utime": int(datetime.now().timestamp()),
                    "success": True,
                    "in_msg": {
                        "value": "5000000000",
                        "source": "UQ...",
                        "destination": { "address": self.wallet_address },
                        "message": "some other order",
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        result = self.verifier.verify_payment(self.wallet_address, self.expected_amount, self.order_id)
        
        self.assertFalse(result['verified'])
        self.assertEqual(result['error'], 'No matching transaction found')

    @patch('requests.get')
    def test_amount_is_incorrect(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "transactions": [
                {
                    "hash": "ton_tx123",
                    "utime": int(datetime.now().timestamp()),
                    "success": True,
                    "in_msg": {
                        "value": "1000000000", # 1 TON instead of 5
                        "source": "UQ...",
                        "destination": { "address": self.wallet_address },
                        "message": "ORDER-456",
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        result = self.verifier.verify_payment(self.wallet_address, self.expected_amount, self.order_id)
        
        self.assertFalse(result['verified'])
        self.assertEqual(result['error'], 'No matching transaction found')
        
    @patch('requests.get')
    def test_transaction_not_successful(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "transactions": [
                {
                    "hash": "ton_tx123",
                    "utime": int(datetime.now().timestamp()),
                    "success": False,
                    "in_msg": {
                        "value": "5000000000",
                        "source": "UQ...",
                        "destination": { "address": self.wallet_address },
                        "message": "ORDER-456",
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        result = self.verifier.verify_payment(self.wallet_address, self.expected_amount, self.order_id)
        
        self.assertFalse(result['verified'])
        self.assertEqual(result['error'], 'No matching transaction found')

    @patch('requests.get')
    def test_api_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("Connection error")

        result = self.verifier.verify_payment(self.wallet_address, self.expected_amount, self.order_id)
        
        self.assertFalse(result['verified'])
        self.assertIn("API request failed", result['error'])

    @patch('requests.get')
    def test_malformed_response(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"invalid_data": []}
        mock_get.return_value = mock_response

        result = self.verifier.verify_payment(self.wallet_address, self.expected_amount, self.order_id)
        
        self.assertFalse(result['verified'])
        self.assertEqual(result['error'], 'No transactions found')


if __name__ == '__main__':
    unittest.main()

