"""
Configuration settings for Geo-Leak Detector
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional, Set
import os


class DatabaseSettings(BaseSettings):
    """PostgreSQL database settings"""
    host: str = Field(default="localhost", env="GEO_DB_HOST")
    port: int = Field(default=5432, env="GEO_DB_PORT")
    name: str = Field(default="geo_leak_detector", env="GEO_DB_NAME")
    user: str = Field(default="geo_user", env="GEO_DB_USER")
    password: str = Field(default="", env="GEO_DB_PASSWORD")
    
    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
    
    @property
    def sync_url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    """Redis settings for real-time alerting"""
    host: str = Field(default="localhost", env="GEO_REDIS_HOST")
    port: int = Field(default=6379, env="GEO_REDIS_PORT")
    db: int = Field(default=0, env="GEO_REDIS_DB")
    password: Optional[str] = Field(default=None, env="GEO_REDIS_PASSWORD")
    
    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class TelegramSettings(BaseSettings):
    """Telegram Bot settings"""
    enabled: bool = Field(default=False, env="GEO_TELEGRAM_ENABLED")
    bot_token: str = Field(default="", env="GEO_TELEGRAM_BOT_TOKEN")
    chat_id: str = Field(default="", env="GEO_TELEGRAM_CHAT_ID")
    alert_on_info: bool = Field(default=False, env="GEO_TELEGRAM_ALERT_INFO")
    alert_on_warning: bool = Field(default=True, env="GEO_TELEGRAM_ALERT_WARNING")
    alert_on_critical: bool = Field(default=True, env="GEO_TELEGRAM_ALERT_CRITICAL")


class PrometheusSettings(BaseSettings):
    """Prometheus metrics settings"""
    enabled: bool = Field(default=True, env="GEO_PROMETHEUS_ENABLED")
    port: int = Field(default=9090, env="GEO_PROMETHEUS_PORT")
    endpoint: str = Field(default="/metrics", env="GEO_PROMETHEUS_ENDPOINT")


class DetectionSettings(BaseSettings):
    """Leak detection settings"""
    check_interval: int = Field(default=30, env="GEO_CHECK_INTERVAL")
    ip_check_servers: List[str] = Field(default=[
        "https://ipleak.net/json/",
        "https://ipinfo.io/json",
        "https://ifconfig.me/all.json",
        "https://api.ipify.org?format=json",
    ])
    dns_check_servers: List[str] = Field(default=[
        "https://dnsleaktest.com/api/servers",
        "https://www.dnsleaktest.com/api/servers",
    ])
    webrtc_check_enabled: bool = Field(default=True, env="GEO_WEBRTC_CHECK_ENABLED")
    
    # Expected values (should be configured per deployment)
    expected_exit_ips: Set[str] = Field(default_factory=set, env="GEO_EXPECTED_EXIT_IPS")
    expected_dns_servers: Set[str] = Field(default={"127.0.0.1", "::1"}, env="GEO_EXPECTED_DNS_SERVERS")
    
    # Auto-remediation
    auto_remediate: bool = Field(default=True, env="GEO_AUTO_REMEDIATE")
    killswitch_script: str = Field(default="/usr/local/bin/killswitch.sh", env="GEO_KILLSWITCH_SCRIPT")


class MAPEKSettings(BaseSettings):
    """MAPE-K integration settings"""
    enabled: bool = Field(default=True, env="GEO_MAPEK_ENABLED")
    node_id: str = Field(default="geo-leak-detector", env="GEO_MAPEK_NODE_ID")
    consciousness_threshold: float = Field(default=0.5, env="GEO_CONSCIOUSNESS_THRESHOLD")
    api_endpoint: str = Field(default="http://localhost:8000/api/v1/mapek", env="GEO_MAPEK_API")


class APISettings(BaseSettings):
    """FastAPI settings"""
    host: str = Field(default="0.0.0.0", env="GEO_API_HOST")
    port: int = Field(default=8080, env="GEO_API_PORT")
    debug: bool = Field(default=False, env="GEO_DEBUG")
    secret_key: str = Field(..., env="GEO_SECRET_KEY")  # Required in production
    cors_origins: List[str] = Field(default=["*"], env="GEO_CORS_ORIGINS")


class Settings(BaseSettings):
    """Main application settings"""
    app_name: str = "Geo-Leak Detector"
    version: str = "1.0.0"
    environment: str = Field(default="development", env="GEO_ENV")
    
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    telegram: TelegramSettings = TelegramSettings()
    prometheus: PrometheusSettings = PrometheusSettings()
    detection: DetectionSettings = DetectionSettings()
    mapek: MAPEKSettings = MAPEKSettings()
    api: APISettings = APISettings()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
