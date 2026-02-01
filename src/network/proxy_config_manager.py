"""
Configuration Management System for Residential Proxy Infrastructure.

Implements:
- Dynamic configuration loading and hot-reloading
- Environment-specific configuration (dev/staging/prod)
- Encrypted credential storage
- Configuration validation and schema enforcement
- Integration with proxy_manager and control_plane
"""
import os
import json
import yaml
import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from src.network.residential_proxy_manager import ProxyEndpoint, ProxyStatus

logger = logging.getLogger(__name__)


class Environment(Enum):
    """Deployment environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class ProxyProviderConfig:
    """Configuration for a proxy provider."""
    name: str
    enabled: bool = True
    host_template: str = ""
    port: int = 8080
    username: str = ""
    password: str = ""
    regions: List[str] = field(default_factory=list)
    priority: int = 100
    max_failures: int = 3
    health_check_interval: int = 60
    rate_limit_per_minute: int = 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding sensitive data)."""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "host_template": self.host_template,
            "port": self.port,
            "regions": self.regions,
            "priority": self.priority,
            "max_failures": self.max_failures,
            "health_check_interval": self.health_check_interval,
            "rate_limit_per_minute": self.rate_limit_per_minute
        }


@dataclass
class SelectionAlgorithmConfig:
    """Configuration for proxy selection algorithm."""
    strategy: str = "weighted_score"
    latency_weight: float = 0.3
    success_weight: float = 0.4
    stability_weight: float = 0.2
    geographic_weight: float = 0.1
    enable_predictive: bool = True
    predictive_window_size: int = 20
    
    def validate(self) -> List[str]:
        """Validate configuration."""
        errors = []
        total_weight = (self.latency_weight + self.success_weight + 
                       self.stability_weight + self.geographic_weight)
        if abs(total_weight - 1.0) > 0.01:
            errors.append(f"Weights must sum to 1.0, got {total_weight}")
        return errors


@dataclass
class HealthCheckConfig:
    """Configuration for health checking."""
    enabled: bool = True
    interval_seconds: int = 60
    timeout_seconds: int = 10
    max_retries: int = 3
    retry_delay_seconds: int = 5
    unhealthy_threshold: int = 3
    healthy_threshold: int = 2
    check_urls: List[str] = field(default_factory=lambda: [
        "https://www.google.com",
        "https://www.cloudflare.com"
    ])


@dataclass
class MetricsConfig:
    """Configuration for metrics collection."""
    enabled: bool = True
    retention_hours: int = 24
    aggregation_interval_seconds: int = 60
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    alert_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "failure_rate": 0.1,
        "p95_latency_ms": 2000,
        "error_rate": 0.05
    })


@dataclass
class SecurityConfig:
    """Security configuration."""
    api_key_required: bool = True
    api_key_header: str = "X-API-Key"
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 100
    rate_limit_burst: int = 10
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24
    allowed_origins: List[str] = field(default_factory=list)
    tls_enabled: bool = False
    tls_cert_path: str = ""
    tls_key_path: str = ""


@dataclass
class ProxyInfrastructureConfig:
    """Complete proxy infrastructure configuration."""
    environment: Environment = Environment.DEVELOPMENT
    version: str = "1.0.0"
    
    # Component configs
    providers: List[ProxyProviderConfig] = field(default_factory=list)
    selection: SelectionAlgorithmConfig = field(default_factory=SelectionAlgorithmConfig)
    health_check: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    # Control plane settings
    control_plane_host: str = "0.0.0.0"
    control_plane_port: int = 8081
    control_plane_workers: int = 4
    
    # Xray integration
    xray_config_path: str = "/usr/local/etc/xray/config.json"
    xray_reload_command: str = "systemctl reload xray"
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    def validate(self) -> List[str]:
        """Validate complete configuration."""
        errors = []
        
        # Validate selection weights
        errors.extend(self.selection.validate())
        
        # Validate providers
        if not self.providers:
            errors.append("At least one provider must be configured")
        
        for provider in self.providers:
            if provider.enabled and not provider.host_template:
                errors.append(f"Provider {provider.name} missing host_template")
        
        # Validate security
        if self.environment == Environment.PRODUCTION:
            if not self.security.api_key_required:
                errors.append("API key required in production")
            if not self.security.tls_enabled:
                logger.warning("TLS not enabled in production")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding sensitive data)."""
        return {
            "environment": self.environment.value,
            "version": self.version,
            "providers": [p.to_dict() for p in self.providers],
            "selection": asdict(self.selection),
            "health_check": asdict(self.health_check),
            "metrics": asdict(self.metrics),
            "security": {
                k: v for k, v in asdict(self.security).items()
                if k not in ("jwt_secret",)
            },
            "control_plane": {
                "host": self.control_plane_host,
                "port": self.control_plane_port,
                "workers": self.control_plane_workers
            },
            "xray": {
                "config_path": self.xray_config_path,
                "reload_command": self.xray_reload_command
            },
            "logging": {
                "level": self.log_level,
                "format": self.log_format
            }
        }


class SecureCredentialStore:
    """Secure storage for sensitive credentials."""
    
    def __init__(self, master_key: Optional[str] = None):
        self.master_key = master_key or os.environ.get("PROXY_CONFIG_MASTER_KEY")
        if not self.master_key:
            raise ValueError("Master key required for credential store")
        
        self._cipher = self._create_cipher()
        self._cache: Dict[str, str] = {}
    
    def _create_cipher(self) -> Fernet:
        """Create encryption cipher from master key."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=hashlib.sha256(b"proxy_config_salt").digest(),
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
        return Fernet(key)
    
    def encrypt(self, value: str) -> str:
        """Encrypt a value."""
        return self._cipher.encrypt(value.encode()).decode()
    
    def decrypt(self, encrypted: str) -> str:
        """Decrypt a value."""
        if encrypted in self._cache:
            return self._cache[encrypted]
        
        decrypted = self._cipher.decrypt(encrypted.encode()).decode()
        self._cache[encrypted] = decrypted
        return decrypted
    
    def clear_cache(self):
        """Clear decryption cache."""
        self._cache.clear()


class ProxyConfigManager:
    """
    Centralized configuration manager for proxy infrastructure.
    
    Features:
    - Hot-reloading of configuration
    - Environment-specific configs
    - Encrypted credential storage
    - Validation and schema enforcement
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        environment: Optional[Environment] = None
    ):
        self.config_path = config_path or os.environ.get(
            "PROXY_CONFIG_PATH",
            "/etc/proxy-infrastructure/config.yaml"
        )
        self.environment = environment or Environment(
            os.environ.get("PROXY_ENV", "development")
        )
        
        self.config: ProxyInfrastructureConfig = ProxyInfrastructureConfig()
        self.credential_store: Optional[SecureCredentialStore] = None
        self._watch_task: Optional[asyncio.Task] = None
        self._running = False
        self._change_handlers: List[Callable] = []
        self._last_hash: str = ""
        self._lock = asyncio.Lock()
    
    def _get_env_config_path(self) -> str:
        """Get environment-specific config path."""
        base_path = Path(self.config_path)
        env_path = base_path.parent / f"config.{self.environment.value}.yaml"
        return str(env_path) if env_path.exists() else self.config_path
    
    def _compute_hash(self, content: str) -> str:
        """Compute hash of configuration content."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    async def load(self) -> ProxyInfrastructureConfig:
        """Load configuration from file."""
        config_path = self._get_env_config_path()
        
        if not os.path.exists(config_path):
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return self.config
        
        try:
            with open(config_path, 'r') as f:
                content = f.read()
            
            self._last_hash = self._compute_hash(content)
            data = yaml.safe_load(content)
            
            # Parse configuration
            self.config = self._parse_config(data)
            
            # Initialize credential store if needed
            if any(p.password for p in self.config.providers):
                self.credential_store = SecureCredentialStore()
                self._decrypt_credentials()
            
            # Validate
            errors = self.config.validate()
            if errors:
                for error in errors:
                    logger.error(f"Config validation error: {error}")
                raise ValueError(f"Configuration validation failed: {errors}")
            
            logger.info(f"Configuration loaded from {config_path}")
            return self.config
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    def _parse_config(self, data: Dict[str, Any]) -> ProxyInfrastructureConfig:
        """Parse configuration from dictionary."""
        config = ProxyInfrastructureConfig(
            environment=Environment(data.get("environment", "development")),
            version=data.get("version", "1.0.0"),
            control_plane_host=data.get("control_plane", {}).get("host", "0.0.0.0"),
            control_plane_port=data.get("control_plane", {}).get("port", 8081),
            control_plane_workers=data.get("control_plane", {}).get("workers", 4),
            xray_config_path=data.get("xray", {}).get("config_path", "/usr/local/etc/xray/config.json"),
            xray_reload_command=data.get("xray", {}).get("reload_command", "systemctl reload xray"),
            log_level=data.get("logging", {}).get("level", "INFO"),
            log_format=data.get("logging", {}).get("format", "json")
        )
        
        # Parse providers
        for provider_data in data.get("providers", []):
            config.providers.append(ProxyProviderConfig(
                name=provider_data["name"],
                enabled=provider_data.get("enabled", True),
                host_template=provider_data.get("host_template", ""),
                port=provider_data.get("port", 8080),
                username=provider_data.get("username", ""),
                password=provider_data.get("password", ""),
                regions=provider_data.get("regions", []),
                priority=provider_data.get("priority", 100),
                max_failures=provider_data.get("max_failures", 3),
                health_check_interval=provider_data.get("health_check_interval", 60),
                rate_limit_per_minute=provider_data.get("rate_limit_per_minute", 100)
            ))
        
        # Parse selection config
        selection_data = data.get("selection", {})
        config.selection = SelectionAlgorithmConfig(
            strategy=selection_data.get("strategy", "weighted_score"),
            latency_weight=selection_data.get("latency_weight", 0.3),
            success_weight=selection_data.get("success_weight", 0.4),
            stability_weight=selection_data.get("stability_weight", 0.2),
            geographic_weight=selection_data.get("geographic_weight", 0.1),
            enable_predictive=selection_data.get("enable_predictive", True),
            predictive_window_size=selection_data.get("predictive_window_size", 20)
        )
        
        # Parse health check config
        health_data = data.get("health_check", {})
        config.health_check = HealthCheckConfig(
            enabled=health_data.get("enabled", True),
            interval_seconds=health_data.get("interval_seconds", 60),
            timeout_seconds=health_data.get("timeout_seconds", 10),
            max_retries=health_data.get("max_retries", 3),
            retry_delay_seconds=health_data.get("retry_delay_seconds", 5),
            unhealthy_threshold=health_data.get("unhealthy_threshold", 3),
            healthy_threshold=health_data.get("healthy_threshold", 2),
            check_urls=health_data.get("check_urls", [
                "https://www.google.com",
                "https://www.cloudflare.com"
            ])
        )
        
        # Parse metrics config
        metrics_data = data.get("metrics", {})
        config.metrics = MetricsConfig(
            enabled=metrics_data.get("enabled", True),
            retention_hours=metrics_data.get("retention_hours", 24),
            aggregation_interval_seconds=metrics_data.get("aggregation_interval_seconds", 60),
            prometheus_enabled=metrics_data.get("prometheus_enabled", True),
            prometheus_port=metrics_data.get("prometheus_port", 9090),
            alert_thresholds=metrics_data.get("alert_thresholds", {
                "failure_rate": 0.1,
                "p95_latency_ms": 2000,
                "error_rate": 0.05
            })
        )
        
        # Parse security config
        security_data = data.get("security", {})
        config.security = SecurityConfig(
            api_key_required=security_data.get("api_key_required", True),
            api_key_header=security_data.get("api_key_header", "X-API-Key"),
            rate_limit_enabled=security_data.get("rate_limit_enabled", True),
            rate_limit_requests_per_minute=security_data.get("rate_limit_requests_per_minute", 100),
            rate_limit_burst=security_data.get("rate_limit_burst", 10),
            jwt_secret=security_data.get("jwt_secret", ""),
            jwt_algorithm=security_data.get("jwt_algorithm", "HS256"),
            jwt_expiry_hours=security_data.get("jwt_expiry_hours", 24),
            allowed_origins=security_data.get("allowed_origins", []),
            tls_enabled=security_data.get("tls_enabled", False),
            tls_cert_path=security_data.get("tls_cert_path", ""),
            tls_key_path=security_data.get("tls_key_path", "")
        )
        
        return config
    
    def _decrypt_credentials(self):
        """Decrypt provider credentials."""
        if not self.credential_store:
            return
        
        for provider in self.config.providers:
            if provider.password.startswith("ENC:"):
                try:
                    provider.password = self.credential_store.decrypt(
                        provider.password[4:]
                    )
                except Exception as e:
                    logger.error(f"Failed to decrypt password for {provider.name}: {e}")
    
    async def save(self):
        """Save configuration to file."""
        config_path = self._get_env_config_path()
        
        # Create backup
        if os.path.exists(config_path):
            backup_path = f"{config_path}.bak"
            os.rename(config_path, backup_path)
        
        try:
            # Encrypt sensitive data
            data = self.config.to_dict()
            
            if self.credential_store:
                for i, provider in enumerate(self.config.providers):
                    if provider.password and not provider.password.startswith("ENC:"):
                        encrypted = self.credential_store.encrypt(provider.password)
                        data["providers"][i]["password"] = f"ENC:{encrypted}"
            
            with open(config_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)
            
            logger.info(f"Configuration saved to {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            # Restore backup
            if os.path.exists(f"{config_path}.bak"):
                os.rename(f"{config_path}.bak", config_path)
            raise
    
    async def _watch_config(self):
        """Watch for configuration file changes."""
        config_path = self._get_env_config_path()
        
        while self._running:
            try:
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        content = f.read()
                    
                    current_hash = self._compute_hash(content)
                    
                    if current_hash != self._last_hash:
                        logger.info("Configuration file changed, reloading...")
                        await self.load()
                        
                        # Notify handlers
                        for handler in self._change_handlers:
                            try:
                                await handler(self.config)
                            except Exception as e:
                                logger.error(f"Config change handler error: {e}")
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Config watch error: {e}")
                await asyncio.sleep(10)
    
    def on_change(self, handler: Callable):
        """Register a configuration change handler."""
        self._change_handlers.append(handler)
    
    async def start(self):
        """Start configuration manager with hot-reload."""
        await self.load()
        self._running = True
        self._watch_task = asyncio.create_task(self._watch_config())
        logger.info("Configuration manager started with hot-reload")
    
    async def stop(self):
        """Stop configuration manager."""
        self._running = False
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
        
        if self.credential_store:
            self.credential_store.clear_cache()
        
        logger.info("Configuration manager stopped")
    
    def get_provider_proxies(self) -> List[ProxyEndpoint]:
        """Generate proxy endpoints from provider configurations."""
        proxies = []
        
        for provider in self.config.providers:
            if not provider.enabled:
                continue
            
            for region in provider.regions:
                proxy = ProxyEndpoint(
                    id=f"{provider.name}-{region}",
                    host=provider.host_template,
                    port=provider.port,
                    username=provider.username,
                    password=provider.password,
                    region=region,
                    country_code=region.upper() if len(region) == 2 else "US"
                )
                proxies.append(proxy)
        
        return proxies
    
    def export_env_file(self, path: str):
        """Export configuration as environment file."""
        lines = [
            f"PROXY_ENV={self.config.environment.value}",
            f"CONTROL_PLANE_HOST={self.config.control_plane_host}",
            f"CONTROL_PLANE_PORT={self.config.control_plane_port}",
            f"XRAY_CONFIG_PATH={self.config.xray_config_path}",
            f"LOG_LEVEL={self.config.log_level}",
            ""
        ]
        
        # Provider-specific env vars
        for provider in self.config.providers:
            prefix = f"PROXY_PROVIDER_{provider.name.upper()}"
            lines.extend([
                f"{prefix}_HOST={provider.host_template}",
                f"{prefix}_PORT={provider.port}",
                f"{prefix}_USERNAME={provider.username}",
                f"{prefix}_REGIONS={','.join(provider.regions)}",
                ""
            ])
        
        with open(path, 'w') as f:
            f.write("\n".join(lines))
        
        logger.info(f"Environment file exported to {path}")


def create_default_config() -> ProxyInfrastructureConfig:
    """Create a default configuration for new deployments."""
    return ProxyInfrastructureConfig(
        environment=Environment.DEVELOPMENT,
        providers=[
            ProxyProviderConfig(
                name="oxylabs",
                host_template="pr.oxylabs.io",
                port=7777,
                regions=["us", "uk", "de"],
                priority=100
            )
        ],
        selection=SelectionAlgorithmConfig(
            strategy="weighted_score",
            latency_weight=0.3,
            success_weight=0.4,
            stability_weight=0.2,
            geographic_weight=0.1
        ),
        health_check=HealthCheckConfig(
            enabled=True,
            interval_seconds=60,
            timeout_seconds=10
        ),
        metrics=MetricsConfig(
            enabled=True,
            retention_hours=24,
            prometheus_enabled=True
        ),
        security=SecurityConfig(
            api_key_required=False,  # Enable in production
            rate_limit_enabled=True
        )
    )
