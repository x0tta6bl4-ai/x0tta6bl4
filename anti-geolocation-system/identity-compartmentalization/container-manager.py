#!/usr/bin/env python3
"""
Identity Compartmentalization Manager
Manages isolated container/VM profiles with distinct fingerprints and credentials
"""

import argparse
import json
import logging
import os
import random
import string
import subprocess
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set
import yaml


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/var/log/identity-manager.log')
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class BrowserFingerprint:
    """Browser fingerprint configuration"""
    user_agent: str
    screen_resolution: str
    color_depth: int
    timezone: str
    language: str
    platform: str
    hardware_concurrency: int
    device_memory: int
    touch_support: bool
    canvas_noise: bool = True
    webgl_vendor: str = ""
    webgl_renderer: str = ""
    fonts: List[str] = field(default_factory=list)


@dataclass
class IdentityProfile:
    """Identity profile for compartmentalization"""
    id: str
    name: str
    description: str
    created_at: datetime
    expires_at: Optional[datetime]
    browser_fingerprint: BrowserFingerprint
    mac_address: str
    hostname: str
    timezone: str
    locale: str
    vpn_endpoint: str
    dns_servers: List[str]
    container_name: str
    active: bool = False
    last_used: Optional[datetime] = None
    usage_count: int = 0
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['expires_at'] = self.expires_at.isoformat() if self.expires_at else None
        data['last_used'] = self.last_used.isoformat() if self.last_used else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'IdentityProfile':
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['expires_at'] = datetime.fromisoformat(data['expires_at']) if data['expires_at'] else None
        data['last_used'] = datetime.fromisoformat(data['last_used']) if data['last_used'] else None
        data['browser_fingerprint'] = BrowserFingerprint(**data['browser_fingerprint'])
        return cls(**data)


class FingerprintGenerator:
    """Generates realistic browser fingerprints"""
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]
    
    SCREEN_RESOLUTIONS = [
        "1920x1080", "1366x768", "1440x900", "1536x864", "1280x720",
        "1600x900", "1280x1024", "1680x1050", "2560x1440", "3840x2160"
    ]
    
    TIMEZONES = [
        "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
        "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Moscow",
        "Asia/Tokyo", "Asia/Shanghai", "Asia/Singapore", "Asia/Dubai",
        "Australia/Sydney", "Pacific/Auckland"
    ]
    
    LOCALES = [
        "en-US", "en-GB", "de-DE", "fr-FR", "es-ES", "it-IT",
        "ja-JP", "zh-CN", "ru-RU", "pt-BR", "nl-NL", "pl-PL"
    ]
    
    PLATFORMS = ["Win32", "Win64", "MacIntel", "Linux x86_64"]
    
    WEBGL_VENDORS = [
        "Intel Inc.", "NVIDIA Corporation", "AMD", "Apple Inc.", "Google Inc."
    ]
    
    WEBGL_RENDERERS = [
        "Intel Iris OpenGL Engine", "NVIDIA GeForce GTX 1060", "AMD Radeon Pro 5500M",
        "Apple M1", "ANGLE (Intel, Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0)"
    ]
    
    COMMON_FONTS = [
        "Arial", "Arial Black", "Arial Narrow", "Calibri", "Cambria",
        "Comic Sans MS", "Courier New", "Georgia", "Impact", "Times New Roman",
        "Trebuchet MS", "Verdana", "Helvetica", "Tahoma", "Palatino"
    ]
    
    @classmethod
    def generate(cls) -> BrowserFingerprint:
        """Generate a random but realistic browser fingerprint"""
        ua = random.choice(cls.USER_AGENTS)
        
        # Extract platform from UA
        if "Windows" in ua:
            platform = "Win32" if "Win64" not in ua else "Win64"
        elif "Macintosh" in ua:
            platform = "MacIntel"
        else:
            platform = "Linux x86_64"
        
        return BrowserFingerprint(
            user_agent=ua,
            screen_resolution=random.choice(cls.SCREEN_RESOLUTIONS),
            color_depth=random.choice([24, 32]),
            timezone=random.choice(cls.TIMEZONES),
            language=random.choice(cls.LOCALES),
            platform=platform,
            hardware_concurrency=random.choice([2, 4, 6, 8]),
            device_memory=random.choice([2, 4, 8, 16]),
            touch_support=random.random() < 0.3,  # 30% chance
            canvas_noise=True,
            webgl_vendor=random.choice(cls.WEBGL_VENDORS),
            webgl_renderer=random.choice(cls.WEBGL_RENDERERS),
            fonts=random.sample(cls.COMMON_FONTS, k=random.randint(8, 15))
        )


class IdentityManager:
    """Manages identity profiles"""
    
    CONFIG_DIR = Path("/etc/anti-geolocation/identities")
    PROFILES_FILE = CONFIG_DIR / "profiles.json"
    
    def __init__(self):
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.profiles: Dict[str, IdentityProfile] = {}
        self._load_profiles()
    
    def _load_profiles(self):
        """Load profiles from disk"""
        if self.PROFILES_FILE.exists():
            try:
                with open(self.PROFILES_FILE, 'r') as f:
                    data = json.load(f)
                    for profile_id, profile_data in data.items():
                        self.profiles[profile_id] = IdentityProfile.from_dict(profile_data)
                logger.info(f"Loaded {len(self.profiles)} profiles")
            except Exception as e:
                logger.error(f"Failed to load profiles: {e}")
    
    def _save_profiles(self):
        """Save profiles to disk"""
        try:
            data = {k: v.to_dict() for k, v in self.profiles.items()}
            with open(self.PROFILES_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save profiles: {e}")
    
    def _generate_mac(self) -> str:
        """Generate random MAC address"""
        oui = "02:00:00"  # Locally administered
        nic = ':'.join([f'{random.randint(0, 255):02x}' for _ in range(3)])
        return f"{oui}:{nic}"
    
    def _generate_hostname(self) -> str:
        """Generate random hostname"""
        adjectives = ["blue", "red", "green", "yellow", "purple", "orange", "pink", "gray"]
        nouns = ["laptop", "desktop", "workstation", "server", "pc", "computer", "device"]
        return f"{random.choice(adjectives)}-{random.choice(nouns)}-{random.randint(100, 999)}"
    
    def create_profile(
        self,
        name: str,
        description: str = "",
        duration_hours: Optional[int] = None,
        browser_type: str = "firefox"
    ) -> IdentityProfile:
        """Create a new identity profile"""
        
        profile_id = str(uuid.uuid4())[:8]
        fingerprint = FingerprintGenerator.generate()
        
        expires_at = None
        if duration_hours:
            expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        profile = IdentityProfile(
            id=profile_id,
            name=name,
            description=description,
            created_at=datetime.now(),
            expires_at=expires_at,
            browser_fingerprint=fingerprint,
            mac_address=self._generate_mac(),
            hostname=self._generate_hostname(),
            timezone=fingerprint.timezone,
            locale=fingerprint.language,
            vpn_endpoint="auto",
            dns_servers=["127.0.0.1"],
            container_name=f"identity-{profile_id}",
            active=False,
            last_used=None,
            usage_count=0
        )
        
        self.profiles[profile_id] = profile
        self._save_profiles()
        
        logger.info(f"Created profile: {profile_id} ({name})")
        return profile
    
    def get_profile(self, profile_id: str) -> Optional[IdentityProfile]:
        """Get a profile by ID"""
        return self.profiles.get(profile_id)
    
    def list_profiles(self, active_only: bool = False) -> List[IdentityProfile]:
        """List all profiles"""
        profiles = list(self.profiles.values())
        if active_only:
            profiles = [p for p in profiles if p.active]
        return sorted(profiles, key=lambda p: p.created_at, reverse=True)
    
    def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile"""
        if profile_id in self.profiles:
            profile = self.profiles[profile_id]
            if profile.active:
                logger.warning(f"Cannot delete active profile: {profile_id}")
                return False
            del self.profiles[profile_id]
            self._save_profiles()
            logger.info(f"Deleted profile: {profile_id}")
            return True
        return False
    
    def activate_profile(self, profile_id: str) -> bool:
        """Activate a profile"""
        # Deactivate all other profiles first
        for pid, profile in self.profiles.items():
            if profile.active:
                self.deactivate_profile(pid)
        
        profile = self.profiles.get(profile_id)
        if not profile:
            return False
        
        profile.active = True
        profile.last_used = datetime.now()
        profile.usage_count += 1
        
        self._save_profiles()
        logger.info(f"Activated profile: {profile_id}")
        
        # Apply system settings
        self._apply_profile_settings(profile)
        
        return True
    
    def deactivate_profile(self, profile_id: str) -> bool:
        """Deactivate a profile"""
        profile = self.profiles.get(profile_id)
        if not profile:
            return False
        
        profile.active = False
        self._save_profiles()
        logger.info(f"Deactivated profile: {profile_id}")
        
        return True
    
    def _apply_profile_settings(self, profile: IdentityProfile):
        """Apply profile settings to system"""
        try:
            # Set hostname
            subprocess.run(
                ["hostnamectl", "set-hostname", profile.hostname],
                check=True, capture_output=True
            )
            
            # Set timezone
            subprocess.run(
                ["timedatectl", "set-timezone", profile.timezone],
                check=True, capture_output=True
            )
            
            # Set MAC address for primary interface
            # This would need to be customized based on network setup
            
            logger.info(f"Applied settings for profile: {profile.id}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to apply profile settings: {e}")
    
    def cleanup_expired(self) -> int:
        """Remove expired profiles"""
        expired = []
        now = datetime.now()
        
        for profile_id, profile in self.profiles.items():
            if profile.expires_at and profile.expires_at < now:
                if not profile.active:
                    expired.append(profile_id)
        
        for profile_id in expired:
            del self.profiles[profile_id]
        
        if expired:
            self._save_profiles()
            logger.info(f"Cleaned up {len(expired)} expired profiles")
        
        return len(expired)


class DockerContainerManager:
    """Manages Docker containers for identity isolation"""
    
    DOCKERFILE_TEMPLATE = '''
FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \\
    firefox-esr \\
    xvfb \\
    pulseaudio \\
    dbus-x11 \\
    --no-install-recommends \\
    && rm -rf /var/lib/apt/lists/*

# Create user
RUN useradd -m -s /bin/bash browser

# Set timezone
ENV TZ={timezone}
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Set locale
ENV LANG={locale}
ENV LC_ALL={locale}

# Copy Firefox profile
COPY firefox-profile/ /home/browser/.mozilla/firefox/
RUN chown -R browser:browser /home/browser/.mozilla

USER browser
WORKDIR /home/browser

# Start Firefox
CMD ["firefox-esr", "--no-remote", "-P", "default"]
'''
    
    def __init__(self, identity_manager: IdentityManager):
        self.identity_manager = identity_manager
    
    def create_container(self, profile_id: str) -> bool:
        """Create a Docker container for a profile"""
        profile = self.identity_manager.get_profile(profile_id)
        if not profile:
            return False
        
        # Create Dockerfile
        dockerfile_content = self.DOCKERFILE_TEMPLATE.format(
            timezone=profile.timezone,
            locale=profile.locale
        )
        
        build_dir = Path(f"/tmp/identity-{profile_id}")
        build_dir.mkdir(parents=True, exist_ok=True)
        
        with open(build_dir / "Dockerfile", 'w') as f:
            f.write(dockerfile_content)
        
        # Create Firefox profile
        self._create_firefox_profile(build_dir / "firefox-profile", profile)
        
        # Build container
        try:
            subprocess.run(
                ["docker", "build", "-t", profile.container_name, str(build_dir)],
                check=True, capture_output=True
            )
            logger.info(f"Created container: {profile.container_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to build container: {e}")
            return False
    
    def _create_firefox_profile(self, profile_dir: Path, profile: IdentityProfile):
        """Create Firefox profile with fingerprint"""
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        # Create user.js with fingerprint settings
        user_js = f'''
// Identity Profile: {profile.name}
// Generated: {datetime.now().isoformat()}

// User Agent
user_pref("general.useragent.override", "{profile.browser_fingerprint.user_agent}");

// Screen resolution
user_pref("privacy.resistFingerprinting", false);
user_pref("privacy.window.maxInnerWidth", {profile.browser_fingerprint.screen_resolution.split('x')[0]});
user_pref("privacy.window.maxInnerHeight", {profile.browser_fingerprint.screen_resolution.split('x')[1]});

// Timezone
user_pref("privacy.resistFingerprinting.spoof TZ", false);

// Language
user_pref("intl.accept_languages", "{profile.browser_fingerprint.language}");
user_pref("intl.locale.requested", "{profile.browser_fingerprint.language}");

// Platform
user_pref("general.platform.override", "{profile.browser_fingerprint.platform}");

// Hardware
user_pref("dom.maxHardwareConcurrency", {profile.browser_fingerprint.hardware_concurrency});
user_pref("dom.deviceMemory", {profile.browser_fingerprint.device_memory});

// WebRTC disabled
user_pref("media.peerconnection.enabled", false);

// Geolocation disabled
user_pref("geo.enabled", false);

// DNS over HTTPS
user_pref("network.trr.mode", 2);
user_pref("network.trr.uri", "https://dns.quad9.net/dns-query");
'''
        
        with open(profile_dir / "user.js", 'w') as f:
            f.write(user_js)
    
    def run_container(self, profile_id: str) -> bool:
        """Run a container for a profile"""
        profile = self.identity_manager.get_profile(profile_id)
        if not profile:
            return False
        
        try:
            subprocess.run(
                [
                    "docker", "run", "-d",
                    "--name", profile.container_name,
                    "--rm",
                    "--network", "host",
                    "--env", f"DISPLAY={os.environ.get('DISPLAY', ':0')}",
                    "-v", "/tmp/.X11-unix:/tmp/.X11-unix:ro",
                    profile.container_name
                ],
                check=True, capture_output=True
            )
            logger.info(f"Started container: {profile.container_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to run container: {e}")
            return False
    
    def stop_container(self, profile_id: str) -> bool:
        """Stop a running container"""
        profile = self.identity_manager.get_profile(profile_id)
        if not profile:
            return False
        
        try:
            subprocess.run(
                ["docker", "stop", profile.container_name],
                check=True, capture_output=True
            )
            logger.info(f"Stopped container: {profile.container_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to stop container: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description='Identity Compartmentalization Manager')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Create profile
    create_parser = subparsers.add_parser('create', help='Create a new identity profile')
    create_parser.add_argument('name', help='Profile name')
    create_parser.add_argument('--description', '-d', help='Profile description')
    create_parser.add_argument('--duration', '-t', type=int, help='Duration in hours')
    create_parser.add_argument('--browser', '-b', default='firefox', help='Browser type')
    
    # List profiles
    subparsers.add_parser('list', help='List all profiles')
    
    # Activate profile
    activate_parser = subparsers.add_parser('activate', help='Activate a profile')
    activate_parser.add_argument('profile_id', help='Profile ID')
    
    # Deactivate profile
    deactivate_parser = subparsers.add_parser('deactivate', help='Deactivate a profile')
    deactivate_parser.add_argument('profile_id', help='Profile ID')
    
    # Delete profile
    delete_parser = subparsers.add_parser('delete', help='Delete a profile')
    delete_parser.add_argument('profile_id', help='Profile ID')
    
    # Show profile details
    show_parser = subparsers.add_parser('show', help='Show profile details')
    show_parser.add_argument('profile_id', help='Profile ID')
    
    # Cleanup expired
    subparsers.add_parser('cleanup', help='Remove expired profiles')
    
    # Docker commands
    docker_parser = subparsers.add_parser('docker', help='Docker container management')
    docker_subparsers = docker_parser.add_subparsers(dest='docker_command')
    
    docker_create = docker_subparsers.add_parser('create', help='Create container')
    docker_create.add_argument('profile_id', help='Profile ID')
    
    docker_run = docker_subparsers.add_parser('run', help='Run container')
    docker_run.add_argument('profile_id', help='Profile ID')
    
    docker_stop = docker_subparsers.add_parser('stop', help='Stop container')
    docker_stop.add_argument('profile_id', help='Profile ID')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    manager = IdentityManager()
    docker_manager = DockerContainerManager(manager)
    
    if args.command == 'create':
        profile = manager.create_profile(
            name=args.name,
            description=args.description or "",
            duration_hours=args.duration,
            browser_type=args.browser
        )
        print(f"Created profile: {profile.id}")
        print(f"  Name: {profile.name}")
        print(f"  Hostname: {profile.hostname}")
        print(f"  MAC: {profile.mac_address}")
        print(f"  Timezone: {profile.timezone}")
        print(f"  User Agent: {profile.browser_fingerprint.user_agent[:60]}...")
        
    elif args.command == 'list':
        profiles = manager.list_profiles()
        if not profiles:
            print("No profiles found")
        else:
            print(f"{'ID':<10} {'Name':<20} {'Active':<8} {'Created':<20}")
            print("-" * 60)
            for p in profiles:
                active = "YES" if p.active else "NO"
                created = p.created_at.strftime("%Y-%m-%d %H:%M")
                print(f"{p.id:<10} {p.name:<20} {active:<8} {created:<20}")
                
    elif args.command == 'activate':
        if manager.activate_profile(args.profile_id):
            print(f"Activated profile: {args.profile_id}")
        else:
            print(f"Failed to activate profile: {args.profile_id}")
            return 1
            
    elif args.command == 'deactivate':
        if manager.deactivate_profile(args.profile_id):
            print(f"Deactivated profile: {args.profile_id}")
        else:
            print(f"Failed to deactivate profile: {args.profile_id}")
            return 1
            
    elif args.command == 'delete':
        if manager.delete_profile(args.profile_id):
            print(f"Deleted profile: {args.profile_id}")
        else:
            print(f"Failed to delete profile: {args.profile_id}")
            return 1
            
    elif args.command == 'show':
        profile = manager.get_profile(args.profile_id)
        if profile:
            print(json.dumps(profile.to_dict(), indent=2))
        else:
            print(f"Profile not found: {args.profile_id}")
            return 1
            
    elif args.command == 'cleanup':
        count = manager.cleanup_expired()
        print(f"Cleaned up {count} expired profiles")
        
    elif args.command == 'docker':
        if args.docker_command == 'create':
            if docker_manager.create_container(args.profile_id):
                print(f"Created container for profile: {args.profile_id}")
            else:
                print(f"Failed to create container")
                return 1
                
        elif args.docker_command == 'run':
            if docker_manager.run_container(args.profile_id):
                print(f"Started container for profile: {args.profile_id}")
            else:
                print(f"Failed to start container")
                return 1
                
        elif args.docker_command == 'stop':
            if docker_manager.stop_container(args.profile_id):
                print(f"Stopped container for profile: {args.profile_id}")
            else:
                print(f"Failed to stop container")
                return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
