#!/usr/bin/env python3
"""
WebRTC Leak Fix for x0tta6bl4 VPN

This module provides browser-level WebRTC leak prevention.
WebRTC can leak real IP address even when VPN is active.

Usage:
    from src.network.webrtc_leak_fix import WebRTCLeakFix
    
    fix = WebRTCLeakFix()
    fix.apply_browser_fixes()  # Apply to Chrome/Firefox
"""

import os
import logging
import platform
from typing import Optional, Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)


class WebRTCLeakFix:
    """
    Fix WebRTC leaks in browsers.
    
    WebRTC can bypass VPN and expose real IP address.
    This class provides fixes for major browsers.
    """
    
    # Chrome/Edge policies to disable WebRTC
    CHROME_POLICIES = {
        "WebRtcUdpPortRange": "",  # Disable UDP ports
        "WebRtcEventLogCollectionAllowed": False,
        "WebRtcTextLogsCollectionAllowed": False,
    }
    
    # Firefox preferences
    FIREFOX_PREFS = {
        "media.peerconnection.enabled": False,  # Disable WebRTC entirely
        "media.peerconnection.ice.default_address_only": True,
        "media.peerconnection.ice.no_host": True,
        "media.peerconnection.ice.relay_only": True,  # Force relay/TURN only
    }
    
    def __init__(self):
        self.system = platform.system()
        self.home = Path.home()
        
    def get_chrome_policy_path(self) -> Optional[Path]:
        """Get Chrome policy directory based on OS."""
        if self.system == "Linux":
            return Path("/etc/opt/chrome/policies/managed")
        elif self.system == "Darwin":
            return self.home / "Library/Application Support/Google/Chrome"
        elif self.system == "Windows":
            return Path("C:/Program Files (x86)/Google/Chrome/Application")
        return None
    
    def get_firefox_profile_path(self) -> Optional[Path]:
        """Get Firefox profile directory."""
        if self.system == "Linux":
            firefox_dir = self.home / ".mozilla/firefox"
        elif self.system == "Darwin":
            firefox_dir = self.home / "Library/Application Support/Firefox/Profiles"
        elif self.system == "Windows":
            firefox_dir = Path(os.environ.get("APPDATA", "")) / "Mozilla/Firefox/Profiles"
        else:
            return None
            
        # Find default profile
        if firefox_dir.exists():
            for profile in firefox_dir.iterdir():
                if profile.is_dir() and "default" in profile.name:
                    return profile
        return None
    
    def apply_chrome_fix(self) -> bool:
        """
        Apply WebRTC fix for Chrome/Chromium/Edge.
        
        Creates policy file to restrict WebRTC.
        """
        policy_path = self.get_chrome_policy_path()
        if not policy_path:
            logger.warning("Could not determine Chrome policy path")
            return False
            
        try:
            policy_path.mkdir(parents=True, exist_ok=True)
            
            import json
            policy_file = policy_path / "webrtc_fix.json"
            
            policy = {
                "WebRtcUdpPortRange": "",
                "WebRtcEventLogCollectionAllowed": False,
                "WebRtcTextLogsCollectionAllowed": False,
            }
            
            with open(policy_file, 'w') as f:
                json.dump(policy, f, indent=2)
                
            logger.info(f"Chrome WebRTC fix applied: {policy_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply Chrome fix: {e}")
            return False
    
    def apply_firefox_fix(self) -> bool:
        """
        Apply WebRTC fix for Firefox.
        
        Modifies user.js to disable WebRTC.
        """
        profile_path = self.get_firefox_profile_path()
        if not profile_path:
            logger.warning("Could not find Firefox profile")
            return False
            
        try:
            prefs_file = profile_path / "user.js"
            
            # Read existing prefs
            existing_prefs = {}
            if prefs_file.exists():
                with open(prefs_file, 'r') as f:
                    for line in f:
                        if line.strip().startswith('user_pref("'):
                            # Parse user_pref("key", value);
                            parts = line.strip().split('",', 1)
                            if len(parts) == 2:
                                key = parts[0].replace('user_pref("', '')
                                value = parts[1].rstrip(');').strip()
                                existing_prefs[key] = value
            
            # Merge with WebRTC fixes
            existing_prefs.update(self.FIREFOX_PREFS)
            
            # Write back
            with open(prefs_file, 'w') as f:
                f.write("// x0tta6bl4 WebRTC Leak Fix\n")
                f.write(f"// Generated automatically\n\n")
                for key, value in existing_prefs.items():
                    if isinstance(value, bool):
                        f.write(f'user_pref("{key}", {str(value).lower()});\n')
                    else:
                        f.write(f'user_pref("{key}", {value});\n')
                        
            logger.info(f"Firefox WebRTC fix applied: {prefs_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply Firefox fix: {e}")
            return False
    
    def apply_system_wide_fix(self) -> bool:
        """
        Apply system-wide firewall rules to block WebRTC traffic.
        
        Blocks common WebRTC ports and protocols.
        """
        if self.system != "Linux":
            logger.warning("System-wide fix only supported on Linux")
            return False
            
        try:
            import subprocess
            
            # Block common WebRTC STUN/TURN ports
            webrtc_ports = ["3478", "3479", "5349", "5350", "19302", "19303"]
            
            for port in webrtc_ports:
                # Block UDP (WebRTC primarily uses UDP)
                subprocess.run(
                    ["iptables", "-A", "OUTPUT", "-p", "udp", "--dport", port, "-j", "DROP"],
                    capture_output=True,
                    check=False
                )
                
            logger.info("System-wide WebRTC firewall rules applied")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply system-wide fix: {e}")
            return False
    
    def apply_browser_fixes(self) -> Dict[str, bool]:
        """
        Apply all available browser fixes.
        
        Returns:
            Dict with results for each browser
        """
        results = {
            "chrome": self.apply_chrome_fix(),
            "firefox": self.apply_firefox_fix(),
            "system_wide": self.apply_system_wide_fix(),
        }
        
        logger.info(f"WebRTC fix results: {results}")
        return results
    
    def check_webrtc_status(self) -> Dict[str, any]:
        """
        Check current WebRTC leak status.
        
        Returns diagnostic information.
        """
        status = {
            "chrome_policy_exists": False,
            "firefox_prefs_exists": False,
            "system_rules_active": False,
        }
        
        # Check Chrome policy
        chrome_path = self.get_chrome_policy_path()
        if chrome_path:
            policy_file = chrome_path / "webrtc_fix.json"
            status["chrome_policy_exists"] = policy_file.exists()
        
        # Check Firefox prefs
        firefox_profile = self.get_firefox_profile_path()
        if firefox_profile:
            prefs_file = firefox_profile / "user.js"
            status["firefox_prefs_exists"] = prefs_file.exists()
        
        # Check iptables (Linux only)
        if self.system == "Linux":
            try:
                import subprocess
                result = subprocess.run(
                    ["iptables", "-L", "OUTPUT", "-n"],
                    capture_output=True,
                    text=True
                )
                status["system_rules_active"] = "3478" in result.stdout
            except:
                pass
                
        return status


# Global instance
_webrtc_fix: Optional[WebRTCLeakFix] = None


def get_webrtc_fix() -> WebRTCLeakFix:
    """Get or create global WebRTC leak fix instance."""
    global _webrtc_fix
    if _webrtc_fix is None:
        _webrtc_fix = WebRTCLeakFix()
    return _webrtc_fix


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    fix = WebRTCLeakFix()
    
    print("Current WebRTC status:")
    print(fix.check_webrtc_status())
    
    print("\nApplying fixes...")
    results = fix.apply_browser_fixes()
    print(f"Results: {results}")
