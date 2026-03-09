#!/usr/bin/env python3
"""
avd_automation.py — x0tta6bl4 Android VPN CI/CD Automation
==========================================================

Automates the lifecycle of an Android Virtual Device (AVD) for:
- Testing the x0tta6bl4 Android VPN client.
- Registering Google accounts for Play Store testing.
- Running instrumentation tests in a headless environment.

Requirements:
- Android SDK (avdmanager, sdkmanager, emulator, adb)
- Python 3.x
"""

import subprocess
import time
import os
import sys
import logging

# Configuration
AVD_NAME = os.getenv("AVD_NAME", "x0tta6bl4_test_device")
TARGET_SDK = os.getenv("TARGET_SDK", "system-images;android-34;google_apis;x86_64")
DEVICE_PROFILE = os.getenv("DEVICE_PROFILE", "pixel_6")
APK_PATH = os.getenv("APK_PATH", "/mnt/projects/android-vpn.apk")

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_dependencies():
    """Verify that Android SDK tools are in the PATH."""
    tools = ["adb", "emulator", "avdmanager", "sdkmanager"]
    missing = []
    for tool in tools:
        if subprocess.call(["which", tool], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
            missing.append(tool)
    
    if missing:
        logger.error(f"❌ Missing Android SDK tools: {', '.join(missing)}")
        logger.info("Please ensure ANDROID_HOME is set and tools are in PATH.")
        sys.exit(1)
    logger.info("✅ All Android SDK dependencies found.")

def create_avd():
    """Create a new AVD if it doesn't exist."""
    logger.info(f"Checking for AVD: {AVD_NAME}...")
    result = subprocess.run(["avdmanager", "list", "avd"], capture_output=True, text=True)
    if AVD_NAME in result.stdout:
        logger.info(f"AVD {AVD_NAME} already exists. Skipping creation.")
        return

    logger.info(f"Creating AVD {AVD_NAME} with target {TARGET_SDK}...")
    # Ensure system image is installed
    subprocess.run(["sdkmanager", TARGET_SDK], check=True)
    
    # Create AVD
    cmd = [
        "avdmanager", "create", "avd",
        "-n", AVD_NAME,
        "-k", TARGET_SDK,
        "-d", DEVICE_PROFILE,
        "--force"
    ]
    # 'echo no' to skip hardware profile customization prompt
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
    process.communicate(input="no\n")
    if process.returncode == 0:
        logger.info(f"✅ AVD {AVD_NAME} created successfully.")
    else:
        logger.error(f"❌ Failed to create AVD {AVD_NAME}.")
        sys.exit(1)

def start_emulator():
    """Start the emulator in the background."""
    logger.info(f"Starting emulator {AVD_NAME} (headless)...")
    cmd = [
        "emulator",
        "-avd", AVD_NAME,
        "-no-window",
        "-no-audio",
        "-no-snapshot",
        "-gpu", "swiftshader_indirect",
        "-qemu", "-m", "2048"
    ]
    # Start emulator as a background process
    emulator_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    logger.info("Waiting for device to boot...")
    subprocess.run(["adb", "wait-for-device"], check=True)
    
    # Wait for sys.boot_completed
    while True:
        res = subprocess.run(["adb", "shell", "getprop", "sys.boot_completed"], capture_output=True, text=True)
        if "1" in res.stdout:
            break
        time.sleep(2)
    
    logger.info("✅ Emulator is ready.")
    return emulator_process

def automate_google_setup():
    """
    Automate Google Account skip/creation steps using ADB inputs.
    Note: This is highly dependent on the OS version and UI layout.
    """
    logger.info("Running Google Account automation...")
    # Unlock screen
    subprocess.run(["adb", "shell", "input", "keyevent", "82"]) # MENU/Unlock
    time.sleep(2)

    # Example: Open Add Account settings directly
    # adb shell am start -n com.google.android.gsf.login/com.google.android.gsf.login.LoginActivity
    
    # Simulating UI navigation to Skip phone verification
    # Note: Coordinates and text search may vary.
    # We use 'input text skip' as a heuristic.
    logger.info("Attempting to 'Skip' phone verification via input...")
    subprocess.run(["adb", "shell", "input", "text", "skip"])
    subprocess.run(["adb", "shell", "input", "keyevent", "66"]) # ENTER
    
    logger.info("ℹ️ Manual verification might still be required for Google UI changes.")

def install_and_run_tests():
    """Install the VPN APK and run instrumentation tests."""
    if not os.path.exists(APK_PATH):
        logger.warning(f"⚠️ APK not found at {APK_PATH}. Skipping installation.")
        return

    logger.info(f"Installing APK: {APK_PATH}...")
    subprocess.run(["adb", "install", "-r", APK_PATH], check=True)
    
    logger.info("Launching x0tta6bl4 VPN Main Activity...")
    # Replace with actual package name
    pkg_name = "com.x0tta6bl4.vpn"
    subprocess.run(["adb", "shell", "am", "start", "-n", f"{pkg_name}/.MainActivity"], check=True)
    
    time.sleep(5)
    logger.info("Running Instrumentation Tests...")
    # Replace with actual test package
    test_runner = f"{pkg_name}.test/androidx.test.runner.AndroidJUnitRunner"
    subprocess.run(["adb", "shell", "am", "instrument", "-w", test_runner])

def shutdown_emulator():
    """Gracefully shutdown the emulator."""
    logger.info("Shutting down emulator...")
    subprocess.run(["adb", "emu", "kill"])

if __name__ == "__main__":
    try:
        check_dependencies()
        create_avd()
        emu = start_emulator()
        automate_google_setup()
        install_and_run_tests()
    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        shutdown_emulator()
