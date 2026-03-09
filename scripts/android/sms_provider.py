#!/usr/bin/env python3
"""
sms_provider.py — x0tta6bl4 SMS API Fallback for Google Play KYC
================================================================

Handles automated SMS reception for account verification.
Supports SMS-Activate and other providers via a unified interface.

Usage:
    export SMS_ACTIVATE_API_KEY="your_key"
    python3 sms_provider.py --service google --country 0
"""

import os
import time
import requests
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SMSActivateProvider:
    BASE_URL = "https://api.sms-activate.org/stubs/handler_api.php"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _request(self, action: str, **kwargs):
        params = {"api_key": self.api_key, "action": action}
        params.update(kwargs)
        response = requests.get(self.BASE_URL, params=params)
        return response.text

    def get_number(self, service: str = "go", country: int = 0):
        """
        Request a phone number for a specific service.
        Service 'go' is for Google.
        """
        logger.info(f"Requesting number for service '{service}' in country '{country}'...")
        res = self._request("getNumber", service=service, country=country)
        # Result format: ACCESS_NUMBER:$id:$number
        if res.startswith("ACCESS_NUMBER"):
            _, activation_id, number = res.split(":")
            logger.info(f"✅ Received number: {number} (ID: {activation_id})")
            return activation_id, number
        else:
            logger.error(f"❌ Failed to get number: {res}")
            return None, None

    def wait_for_sms(self, activation_id: str, timeout: int = 300, interval: int = 10):
        """Poll for SMS code for a given activation ID."""
        logger.info(f"Waiting for SMS on activation {activation_id} (timeout {timeout}s)...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            res = self._request("getStatus", id=activation_id)
            # Result format: STATUS_OK:$code
            if res.startswith("STATUS_OK"):
                _, code = res.split(":")
                logger.info(f"✅ Received SMS Code: {code}")
                return code
            elif res == "STATUS_WAIT_CODE":
                logger.info("Still waiting for SMS...")
            else:
                logger.warning(f"Unexpected status: {res}")
            
            time.sleep(interval)
        
        logger.error("❌ Timeout reached while waiting for SMS.")
        return None

def main():
    parser = argparse.ArgumentParser(description="x0tta6bl4 SMS Fallback Utility")
    parser.add_argument("--service", default="go", help="Service code (e.g., 'go' for Google)")
    parser.add_argument("--country", type=int, default=0, help="Country code (0 for Russia)")
    args = parser.parse_args()

    api_key = os.getenv("SMS_ACTIVATE_API_KEY")
    if not api_key:
        logger.error("SMS_ACTIVATE_API_KEY environment variable not set.")
        return

    provider = SMSActivateProvider(api_key)
    act_id, number = provider.get_number(args.service, args.country)
    
    if act_id and number:
        print(f"PHONE_NUMBER={number}")
        print(f"ACTIVATION_ID={act_id}")
        
        # Example: manually trigger wait if needed
        # code = provider.wait_for_sms(act_id)
        # if code:
        #     print(f"VERIFICATION_CODE={code}")

if __name__ == "__main__":
    main()
