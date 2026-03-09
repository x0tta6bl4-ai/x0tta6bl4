# x0tta6bl4 Android Automation Suite

This directory contains scripts for automating Android application testing and environment setup, specifically for the x0tta6bl4 VPN/Mesh client.

## Components

### 1. `avd_automation.py`
Automates the creation, booting, and testing lifecycle of an Android Virtual Device (AVD).
- **Headless mode:** Runs in CI environments without a GUI.
- **Google Account Automation:** Attempts to skip phone verification for testing purposes.
- **Test execution:** Automatically installs the VPN APK and runs instrumentation tests.

**Usage:**
```bash
python3 scripts/android/avd_automation.py
```

### 2. `sms_provider.py`
A utility to interact with SMS-Activate (and other providers) to receive verification codes.
- **Purpose:** Used as a fallback when Google Play Console or Google Account registration requires a phone number for KYC/verification.
- **Service:** Defaults to 'go' (Google).
- **Country:** Supports multiple country codes (e.g., 0 for Russia).

**Usage:**
```bash
export SMS_ACTIVATE_API_KEY="your_key"
python3 scripts/android/sms_provider.py --service go --country 0
```

## Setup & Dependencies

1. **Android SDK:** Ensure `ANDROID_HOME` is set and `platform-tools`, `emulator`, and `cmdline-tools` are in your `PATH`.
2. **Python Requirements:**
   - `requests` (for `sms_provider.py`)
   
To install Python dependencies:
```bash
pip install requests
```

## CI/CD Integration

These scripts are designed to be triggered within a GitLab CI or GitHub Actions environment to verify Android client builds on every commit.
