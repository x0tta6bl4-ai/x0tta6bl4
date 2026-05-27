# REDACTED REVIEW COPY - NOT DEPLOYABLE
# source: /opt/ghost-access-bot/current/telegram_bot_simple.py
# raw content was read into memory only and not stored locally

#!/usr/bin/env python3
"""
Минимальный Telegram бот для Ghost Access.

VERIFIED HERE:
  - модуль можно импортировать локально
  - entrypoint стартует через aiogram 3.x polling path без import-time падения

NOT VERIFIED YET:
  - ответы в реальном чате Telegram
  - платежный flow
"""

import asyncio
import base64
from decimal import Decimal, ROUND_HALF_UP
import fcntl
import html
import json
import logging
import os
import secrets
import socket
import statistics
import subprocess
import threading
import time
import uuid
from io import BytesIO
import onboarding_logic
from pathlib import Path
from datetime import UTC, datetime, timedelta
from typing import Optional, TypedDict
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

try:
    import qrcode
except ImportError:
    qrcode = None

try:
    from aiogram import Bot, Dispatcher, Router
    from aiogram.exceptions import TelegramConflictError
    from aiogram.filters import Command, CommandObject
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.types import (
        BotCommand,
        BufferedInputFile,
        CallbackQuery,
        InlineKeyboardMarkup,
        InlineQuery,
        InlineQueryResultArticle,
        InputTextMessageContent,
        Message,
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    AIOGRAM_AVAILABLE = True
except ImportError:
    AIOGRAM_AVAILABLE = False
    Bot = Dispatcher = Router = None
    TelegramConflictError = Command = CommandObject = MemoryStorage = None
    BotCommand = BufferedInputFile = CallbackQuery = InlineKeyboardMarkup = None
    InlineQuery = InlineQueryResultArticle = InputTextMessageContent = Message = None
    InlineKeyboardBuilder = None
from typing import TypedDict

from xray_client_naming import build_human_xray_email
from database import (
    # Type definitions
    UserRecord,
    DeviceRecord,
    PaymentRecord,
    EgressMode,
    DeviceStatus,
    PaymentStatus,
    # High-level operations
    DatabaseOperations,
    # Legacy operations
    create_pending_payment,
    create_device,
    create_user,
    claim_offline_subscription,
    ensure_legacy_primary_device,
    ensure_trial_claim,
    get_global_referral_stats,
    has_activity,
    has_trial_claim,
    get_recent_activity_for_user,
    get_recent_payments_for_user,
    get_recent_rate_limited_count,
    get_recent_users,
    get_rate_limit_stats,
    get_suspicious_users,
    get_top_rate_limited_users,
    grant_referral_bonus_days,
    expire_stale_pending_payments,
    get_db_connection,
    get_device,
    get_payment,
    get_payment_queue_quality_24h,
    get_payment_queue_quality_prev_24h,
    get_payment_status_summary,
    get_pending_payments,
    get_pending_payments_requiring_reminder,
    get_processed_payments,
    get_recent_referral_rewards,
    get_recent_referrals,
    get_referral_summary,
    get_top_referrers,
    get_user,
    is_user_active,
    get_user_extra_device_slots,
    get_user_by_subscription_token,
    get_offline_subscription_by_token,
    get_subscription_accesses,
    get_user_egress_mode,
    get_user_devices,
    get_user_stats,
    init_database,
    log_activity,
    mark_referral_paid,
    mark_referral_trial_started,
    record_payment,
    register_request_event,
    count_recent_request_events,
    record_referral_open,
    revoke_device,
    transition_pending_payment,
    update_device,
    update_payment_status,
    update_user,
    set_user_egress_mode,
    ensure_user_subscription_token,
    record_subscription_access,
    mark_subscription_access_notified,
    count_subscription_accesses,
    delete_device,
    get_broadcast_user_ids,
    create_promo_code,
    redeem_promo_code,
    list_promo_codes,
    delete_promo_code,
    delete_user_account,
    add_user_extra_device_slots,
    is_webhook_processed,
    record_webhook_processed,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# TYPE DEFINITIONS
# ============================================================================

class PlanConfig(TypedDict):
    """Type-safe plan configuration."""
    label: str
    amount: int
    days: int
    devices: int


class DeviceSlotAddonConfig(TypedDict):
    """Paid add-on for additional device slots."""
    label: str
    amount: int
    slots: int


class RateLimitState(TypedDict):
    """Rate limiting state per user."""
    first_request: float
    count: int
    warned: bool


class CachedPayload(TypedDict):
    """Generic cache entry structure."""
    loaded_at: float
    path: str
    payload: Optional[dict]


# ============================================================================
# GLOBAL STATE
# ============================================================================

_VPN_SERVICE_AGENT_CACHE: dict[str, object] = {
    "loaded_at": 0.0,
    "path": "",
    "payload": None,
}
_VPN_DELIVERY_SAMPLE_CACHE: dict[str, object] = {
    "samples": [],
}
_WARP_TIMEOUT_SIGNAL_CACHE: dict[str, object] = {
    "loaded_at": 0.0,
    "payload": None,
}
_SUBSCRIPTION_RATE_LIMIT_STATE: dict[str, list[float]] = {}
_SUBSCRIPTION_RATE_LIMIT_LOCK = threading.Lock()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    logging.error("TELEGRAM_BOT_TOKEN not set - Bot will not function")

BOT_BRAND = os.getenv("BOT_BRAND", "Ghost Access")
BOT_USERNAME = os.getenv("BOT_USERNAME", "ghost_access_bot").lstrip("@")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "").strip().lstrip("@")
TELEGRAM_POLLING_ENABLED = os.getenv("TELEGRAM_POLLING_ENABLED", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
VPN_SERVER = os.getenv("VPN_SERVER", "").strip()
if not VPN_SERVER:
    if TELEGRAM_POLLING_ENABLED:
        raise SystemExit("VPN_SERVER not set")
    VPN_SERVER = "127.0.0.1"
PROFILE_VPN_SERVER = os.getenv("PROFILE_VPN_SERVER", VPN_SERVER)
VPN_PORT = int(os.getenv("VPN_PORT", "443"))
SECONDARY_VPN_PORT = int(os.getenv("SECONDARY_VPN_PORT", "2083"))
LEGACY_DIAGNOSTIC_VPN_PORT = int(os.getenv("LEGACY_DIAGNOSTIC_VPN_PORT", "39829"))
NL_BETA_VPN_SERVER = os.getenv("NL_BETA_VPN_SERVER", VPN_SERVER).strip() or VPN_SERVER
NL_BETA_VPN_PORT = int(os.getenv("NL_BETA_VPN_PORT", "2443"))
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "7"))
REFERRAL_TRIAL_BONUS_DAYS = int(os.getenv("REFERRAL_TRIAL_BONUS_DAYS", "1"))
REFERRAL_BONUS_DAYS = int(os.getenv("REFERRAL_BONUS_DAYS", "7"))
REFERRAL_BONUS_CAP_DAYS = int(os.getenv("REFERRAL_BONUS_CAP_DAYS", "90"))
XRAY_CONFIG_PATH = os.getenv("XRAY_CONFIG_PATH", "/usr/local/etc/xray/config.json")
XRAY_CLIENT_MANAGER = os.getenv(
    "XRAY_CLIENT_MANAGER", "/mnt/projects/scripts/xui_client_manager.py"
)
XRAY_RUNTIME_USER_MANAGER = os.getenv("XRAY_RUNTIME_USER_MANAGER", "").strip() or (
    "/opt/ghost-access-bot/scripts/xray_runtime_user_manager.py"
    if os.path.exists("/opt/ghost-access-bot/scripts/xray_runtime_user_manager.py")
    else "/mnt/projects/scripts/xray_runtime_user_manager.py"
)
ENABLE_XHTTP_FALLBACK = os.getenv("ENABLE_XHTTP_FALLBACK", "0").strip() in {
    "1",
    "true",
    "yes",
    "on",
}
ENABLE_SECONDARY_REALITY_FALLBACK = (
    os.getenv("ENABLE_SECONDARY_REALITY_FALLBACK", "0").strip() in {"1", "true", "yes", "on"}
    and SECONDARY_VPN_PORT != VPN_PORT
)
ENABLE_ANDROID_STEALTH_NL_BETA_FALLBACK = (
    os.getenv("ENABLE_ANDROID_STEALTH_NL_BETA_FALLBACK", "0").strip().lower()
    in {"1", "true", "yes", "on"}
)
EXPOSE_FALLBACK_TRANSPORTS = (
    os.getenv("EXPOSE_FALLBACK_TRANSPORTS", "0").strip().lower() in {"1", "true", "yes", "on"}
)
SPB_REALITY_SERVER_NAME = os.getenv("SPB_REALITY_SERVER_NAME", "www.cloudflare.com").strip()
SPB_REALITY_FINGERPRINT = os.getenv("SPB_REALITY_FINGERPRINT", "chrome").strip()
SPB_REALITY_PUBLIC_KEY = os.getenv(
    "SPB_REALITY_PUBLIC_KEY",
    "AZmSghVAZbdZOWxxEw2cmOXRucFKDn6Bf45YrNZ6bx8",
).strip()
SPB_REALITY_SHORT_ID = os.getenv("SPB_REALITY_SHORT_ID", "a1b2c3d4").strip()
SPB_REALITY_FLOW = os.getenv("SPB_REALITY_FLOW", "xtls-rprx-vision").strip()
SPB_REALITY_NETWORK = os.getenv("SPB_REALITY_NETWORK", "tcp").strip()
SPB_PROFILE_SERVER = os.getenv("SPB_PROFILE_SERVER", "195.58.48.193").strip() or "195.58.48.193"
SPB_PROFILE_PRIMARY_PORT = int(os.getenv("SPB_PROFILE_PRIMARY_PORT", str(VPN_PORT)))
NL_BETA_REALITY_SERVER_NAME = os.getenv(
    "NL_BETA_REALITY_SERVER_NAME", "www.microsoft.com"
).strip()
NL_BETA_REALITY_FINGERPRINT = os.getenv("NL_BETA_REALITY_FINGERPRINT", "chrome").strip()
NL_BETA_REALITY_PUBLIC_KEY = (
    os.getenv("NL_BETA_REALITY_PUBLIC_KEY", "").strip()
    or os.getenv("REALITY_PUBLIC_KEY", "").strip()
    or SPB_REALITY_PUBLIC_KEY
)
NL_BETA_REALITY_SHORT_ID = (
    os.getenv("NL_BETA_REALITY_SHORT_ID", "").strip() or SPB_REALITY_SHORT_ID
)
YOOMONEY_RECEIVER = os.getenv("YOOMONEY_RECEIVER", "").strip()
YOOMONEY_PAYMENT_TYPE = os.getenv("YOOMONEY_PAYMENT_TYPE", "SB").strip() or "SB"
YOOMONEY_API_TOKEN = os.getenv("YOOMONEY_API_TOKEN", "").strip()
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "").strip()
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "").strip()
YOOKASSA_RETURN_URL = os.getenv("YOOKASSA_RETURN_URL", "").strip()
YOOKASSA_WEBHOOK_SECRET = os.getenv("YOOKASSA_WEBHOOK_SECRET", "").strip()
CARDLINK_API_TOKEN = os.getenv("CARDLINK_API_TOKEN", "").strip()
CARDLINK_SHOP_ID = os.getenv("CARDLINK_SHOP_ID", "").strip()
CARDLINK_WEBHOOK_PORT = int(os.getenv("CARDLINK_WEBHOOK_PORT", "8880"))
SUBSCRIPTION_HTTP_PORT = int(os.getenv("SUBSCRIPTION_HTTP_PORT", str(CARDLINK_WEBHOOK_PORT)))
SUBSCRIPTION_BASE_URL = os.getenv("SUBSCRIPTION_BASE_URL", "").strip().rstrip("/")
WEB_ACCESS_BASE_URL = os.getenv("WEB_ACCESS_BASE_URL", "").strip().rstrip("/")
SUBSCRIPTION_RATE_LIMIT_WINDOW_SECONDS = int(
    os.getenv("SUBSCRIPTION_RATE_LIMIT_WINDOW_SECONDS", "60")
)
SUBSCRIPTION_RATE_LIMIT_MAX_REQUESTS = int(
    os.getenv("SUBSCRIPTION_RATE_LIMIT_MAX_REQUESTS", "30")
)
HAPP_APPSTORE_URL = "https://apps.apple.com/us/app/happ-proxy-utility/id6504287215"
STREISAND_APPSTORE_URL = "https://apps.apple.com/app/streisand/id6450534064"
V2RAYTUN_APPSTORE_URL = "https://apps.apple.com/app/v2raytun/id6476628951"
HIDDIFY_DOWNLOAD_URL = "https://hiddify.com/app/"
V2RAYNG_PLAY_URL = "https://play.google.com/store/apps/details?id=com.v2ray.ang"
V2RAYN_DOWNLOAD_URL = "https://github.com/2dust/v2rayN/releases"
VPN_SERVICE_AGENT_LATEST_PATH = os.getenv("VPN_SERVICE_AGENT_LATEST_PATH", "").strip()
VPN_SERVICE_AGENT_STALE_SECONDS = int(os.getenv("VPN_SERVICE_AGENT_STALE_SECONDS", "1800"))
VPN_SERVICE_AGENT_CACHE_SECONDS = int(os.getenv("VPN_SERVICE_AGENT_CACHE_SECONDS", "30"))
WARP_TIMEOUT_SIGNAL_CACHE_SECONDS = int(
    os.getenv("WARP_TIMEOUT_SIGNAL_CACHE_SECONDS", "30")
)
WARP_TIMEOUT_SIGNAL_WINDOW_MINUTES = int(
    os.getenv("WARP_TIMEOUT_SIGNAL_WINDOW_MINUTES", "15")
)
WARP_TIMEOUT_SIGNAL_THRESHOLD = int(os.getenv("WARP_TIMEOUT_SIGNAL_THRESHOLD", "10"))
WARP_EOF_SIGNAL_THRESHOLD = int(os.getenv("WARP_EOF_SIGNAL_THRESHOLD", "25"))
DEVICE_ACTIVITY_SYNC_SCRIPT = os.getenv(
    "DEVICE_ACTIVITY_SYNC_SCRIPT",
    (
        "/opt/ghost-access-bot/current/scripts/sync_xray_device_activity.py"
        if os.path.exists("/opt/ghost-access-bot/current/scripts/sync_xray_device_activity.py")
        else "/mnt/projects/scripts/sync_xray_device_activity.py"
    ),
)
DEVICE_ACTIVITY_SYNC_INTERVAL_SECONDS = int(
    os.getenv("DEVICE_ACTIVITY_SYNC_INTERVAL_SECONDS", "60")
)
YOOMONEY_POLL_INTERVAL_SECONDS = int(os.getenv("YOOMONEY_POLL_INTERVAL_SECONDS", "30"))

DELIVERY_PROFILE_DEFAULT_NL = "default_nl"
DELIVERY_PROFILE_ANDROID_STEALTH_SPB = "android_stealth_spb"
DELIVERY_PROFILE_FALLBACK_NL = "fallback_nl"
ENTRY_NODE_NL = "nl"
ENTRY_NODE_SPB = "spb"
CLIENT_FAMILY_GENERIC = "generic"
CLIENT_FAMILY_ANDROID_STEALTH = "android_stealth"
DEFAULT_ANDROID_STEALTH_ALLOWED_PACKAGES = (
    "org.telegram.messenger",
    "com.android.chrome",
    "org.mozilla.firefox",
    "com.google.android.youtube",
)
ANDROID_STEALTH_ALLOWED_PACKAGES = tuple(
    pkg.strip()
    for pkg in os.getenv(
        "ANDROID_STEALTH_ALLOWED_PACKAGES",
        ",".join(DEFAULT_ANDROID_STEALTH_ALLOWED_PACKAGES),
    ).split(",")
    if pkg.strip()
)
ANDROID_STEALTH_VPN_DNS_SERVERS = tuple(
    server.strip()
    for server in os.getenv("ANDROID_STEALTH_VPN_DNS", "1.1.1.1,1.0.0.1").split(",")
    if server.strip()
)

# Prometheus metrics configuration
PROMETHEUS_ENABLED = os.getenv("PROMETHEUS_ENABLED", "0").strip() in {"1", "true", "yes", "on"}
PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", "9090"))

# Optional prometheus_client import
try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, start_http_server as prom_start_server
    _prometheus_available = True
except ImportError:
    _prometheus_available = False

if PROMETHEUS_ENABLED and _prometheus_available:
    # Payment operation metrics
    PAYMENT_TOTAL = Counter(
        "ghost_payment_total",
        "Total payments processed",
        ["provider", "status"]
    )
    PAYMENT_DURATION = Histogram(
        "ghost_payment_duration_seconds",
        "Payment processing duration",
        ["provider"],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
    )
    WEBHOOK_TOTAL = Counter(
        "ghost_webhook_total",
        "Total webhooks received",
        ["provider", "status"]
    )
    PROVISIONING_FAILURES = Counter(
        "ghost_provisioning_failures_total",
        "Total Xray provisioning failures",
        ["provider"]
    )
    SUBSCRIPTION_LINK_REQUESTS = Counter(
        "ghost_subscription_link_requests_total",
        "Total subscription link requests",
        ["transport"]
    )
else:
    PAYMENT_TOTAL = None
    PAYMENT_DURATION = None
    WEBHOOK_TOTAL = None
    PROVISIONING_FAILURES = None
    SUBSCRIPTION_LINK_REQUESTS = None
PENDING_PAYMENT_EXPIRE_HOURS = int(os.getenv("PENDING_PAYMENT_EXPIRE_HOURS", "24"))
PAYMENT_QUEUE_ALERT_THRESHOLD = int(os.getenv("PAYMENT_QUEUE_ALERT_THRESHOLD", "1"))
PAYMENT_QUEUE_DIGEST_MINUTES = int(os.getenv("PAYMENT_QUEUE_DIGEST_MINUTES", "60"))
BOT_SINGLETON_LOCK_FILE = os.getenv(
    "BOT_SINGLETON_LOCK_FILE",
    "/tmp/ghost-access-bot.lock",
).strip()
def _default_xray_runtime_config_path() -> str:
    configured = os.getenv("XRAY_RUNTIME_CONFIG_PATH", "").strip()
    if configured:
        return configured

    candidates = [
        os.getenv("XRAY_CONFIG_PATH", "").strip(),
        "/usr/local/etc/xray/config.json",
        "/usr/local/x-ui/bin/config.json",
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return "/usr/local/etc/xray/config.json"


XRAY_RUNTIME_CONFIG_PATH = _default_xray_runtime_config_path()
XRAY_RUNTIME_API_SERVER = os.getenv("XRAY_RUNTIME_API_SERVER", "").strip()
XRAY_RUNTIME_TAGS = os.getenv("XRAY_RUNTIME_TAGS", "").strip()
GHOST_ACCESS_DB_PATH = (
    os.getenv("GHOST_ACCESS_DB_PATH", "").strip()
    or (
        "/opt/ghost-access-bot/shared/x0tta6bl4.db"
        if os.path.exists("/opt/ghost-access-bot/shared/x0tta6bl4.db")
        else "x0tta6bl4.db"
    )
)
DEVICE_ACTIVITY_STATE_FILE = os.getenv(
    "DEVICE_ACTIVITY_STATE_FILE",
    "/var/lib/ghost-access/xray_access_sync_state.json",
).strip()
ADMIN_USER_IDS = {
    int(value.strip())
    for value in os.getenv("ADMIN_USER_IDS", "").split(",")
    if value.strip().isdigit()
}


def _ru_day_word(value: int) -> str:
    value = abs(int(value))
    if value % 10 == 1 and value % 100 != 11:
        return "день"
    if value % 10 in {2, 3, 4} and value % 100 not in {12, 13, 14}:
        return "дня"
    return "дней"


TRIAL_DAYS_TEXT = f"{TRIAL_DAYS} {_ru_day_word(TRIAL_DAYS)}"
TRIAL_CTA_TEXT = f"{TRIAL_DAYS_TEXT} бесплатно"


def _validate_startup_env() -> None:
    """Validate critical env vars at import time. Fail loud, not silent."""
    warnings = []
    if not ADMIN_USER_IDS:
        warnings.append("ADMIN_USER_IDS is empty — admin commands and alerts will not work")
    if not os.path.exists(XRAY_CLIENT_MANAGER):
        warnings.append(f"XRAY_CLIENT_MANAGER not found: {XRAY_CLIENT_MANAGER}")
    provider = "none"
    if os.getenv("YOOMONEY_RECEIVER", "").strip():
        provider = "yoomoney"
    elif os.getenv("YOOKASSA_SHOP_ID", "").strip() and os.getenv("YOOKASSA_SECRET_KEY", "").strip():
        provider = "yookassa"
    elif os.getenv("CARDLINK_API_TOKEN", "").strip() and os.getenv("CARDLINK_SHOP_ID", "").strip():
        provider = "cardlink"
    if provider == "none":
        warnings.append(
            "No payment provider configured (YOOMONEY_RECEIVER / YOOKASSA_SHOP_ID / CARDLINK_API_TOKEN)"
        )
    if not os.getenv("SUBSCRIPTION_BASE_URL", "").strip():
        warnings.append(
            "SUBSCRIPTION_BASE_URL is empty — subscription auto-update links will not work"
        )
    for w in warnings:
        logger.warning("STARTUP CHECK: %s", w)
    if warnings:
        logger.warning(
            "STARTUP CHECK: %d issue(s) found — bot will start but some features are degraded",
            len(warnings),
        )


_validate_startup_env()

PLANS: dict[str, PlanConfig] = {
    "basic_1m": {"label": "1 месяц", "amount": 149, "days": 30, "devices": 2},
    "basic_3m": {"label": "3 месяца", "amount": 399, "days": 90, "devices": 3},
    "basic_6m": {"label": "6 месяцев", "amount": 699, "days": 180, "devices": 4},
    "basic_12m": {"label": "12 месяцев", "amount": 1099, "days": 365, "devices": 5},
}

DEVICE_SLOT_ADDONS: dict[str, DeviceSlotAddonConfig] = {
    "device_slot_1": {
        "label": "+1 слот устройства",
        "amount": int(os.getenv("EXTRA_DEVICE_SLOT_PRICE", "99")),
        "slots": 1,
    },
}
MAX_EXTRA_DEVICE_SLOTS = int(os.getenv("MAX_EXTRA_DEVICE_SLOTS", "5"))

DEVICE_LIMITS = {
    "trial": 1,
    "basic_1m": 2,
    "basic_3m": 3,
    "basic_6m": 4,
    "basic_12m": 5,
}

PLAN_ALIASES = {
    "base": "basic_1m",
    "pro": "basic_3m",
    "plus": "basic_6m",
    "year": "basic_12m",
}

DEVICE_TYPE_LABELS = {
    "my_phone": "Мой телефон",
    "my_pc": "Мой компьютер",
    "child_phone": "Телефон ребенка",
    "tablet": "Планшет",
    "other": "Устройство",
    # Legacy compat
    "android": "Android",
    "windows": "Windows",
    "iphone": "iPhone",
    "mac": "Mac",
}

DEVICE_TYPE_NUMBERING = {
    "my_phone": False,
    "my_pc": False,
    "child_phone": True,
    "tablet": False,
    "other": True,
    "android": False,
    "windows": False,
    "iphone": False,
    "mac": False,
}

USER_PAYMENT_STATUS_LABELS = {
    "pending": "ожидает проверки",
    "approved": "подтверждена",
    "completed": "завершена",
    "rejected": "отклонена",
    "expired": "истекла",
}

router = Router()
INSTANCE_HOST = socket.gethostname()
INSTANCE_PID = os.getpid()
INSTANCE_TAG = f"{INSTANCE_HOST}:{INSTANCE_PID}"
_LOCK_HANDLE = None
ADMIN_INPUT_MODE: dict[int, str] = {}
ADMIN_USER_BROWSER_STATE: dict[int, dict[str, str]] = {}
DEVICE_RENAME_PENDING: dict[int, int] = {}
ADMIN_USERS_PAGE_SIZE = 12
XRAY_RELOAD_DEBOUNCE_SECONDS = int(os.getenv("XRAY_RELOAD_DEBOUNCE_SECONDS", "5"))
XRAY_RUNTIME_CMD_TIMEOUT_SECONDS = int(
    os.getenv("XRAY_RUNTIME_CMD_TIMEOUT_SECONDS", "30")
)
_XRAY_RELOAD_TASK: asyncio.Task | None = None
_XRAY_RELOAD_REASONS: set[str] = set()


def acquire_single_instance_lock() -> None:
    global _LOCK_HANDLE
    lock_handle = open(BOT_SINGLETON_LOCK_FILE, "a+", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_handle.seek(0)
        owner = lock_handle.read().strip() or "unknown"
        raise SystemExit(
            f"another local bot instance already holds {BOT_SINGLETON_LOCK_FILE}: {owner}"
        ) from exc

    lock_handle.seek(0)
    lock_handle.truncate(0)
    lock_handle.write(INSTANCE_TAG)
    lock_handle.flush()
    _LOCK_HANDLE = lock_handle


def release_single_instance_lock() -> None:
    global _LOCK_HANDLE
    if _LOCK_HANDLE is None:
        return
    try:
        _LOCK_HANDLE.seek(0)
        _LOCK_HANDLE.truncate(0)
        fcntl.flock(_LOCK_HANDLE.fileno(), fcntl.LOCK_UN)
    finally:
        _LOCK_HANDLE.close()
        _LOCK_HANDLE = None


RATE_LIMITS = {
    "trial": (2, 60),
    "config": (4, 60),
    "repair": (4, 60),
    "invite": (6, 60),
}
SUSPICIOUS_RATE_LIMIT_THRESHOLD = int(os.getenv("SUSPICIOUS_RATE_LIMIT_THRESHOLD", "10"))


def get_user_state(user_id: int) -> tuple[str, dict | None]:
    user = get_user(user_id)
    if not user:
        return "new", None

    expires_at = parse_expires_at(user.get("expires_at"))
    if not expires_at or datetime.now() > expires_at:
        return "expired", user

    if user.get("plan") == "trial":
        return "trial_active", user
    return "paid_active", user


def check_rate_limit(user_id: int, action: str) -> bool:
    config = RATE_LIMITS.get(action)
    if not config:
        return True

    limit, window_seconds = config
    recent_rate_limited = get_recent_rate_limited_count(user_id, window_hours=24)
    if recent_rate_limited >= SUSPICIOUS_RATE_LIMIT_THRESHOLD:
        limit = max(1, limit // 2)
    recent_events = count_recent_request_events(user_id, action, window_seconds)
    if recent_events >= limit:
        return False
    register_request_event(user_id, action)
    return True


async def enforce_rate_limit(message: Message | CallbackQuery, action: str) -> bool:
    user_id = message.from_user.id
    if check_rate_limit(user_id, action):
        return True

    log_activity(user_id, f"rate_limited:{action}")
    text = f"{BOT_BRAND}\n\nСлишком часто.\nПодожди немного и попробуй ещё раз."
    if isinstance(message, CallbackQuery):
        await message.message.answer(text)
        await message.answer()
    else:
        await message.answer(text)
    return False


async def safe_edit(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
) -> None:
    """Edit the callback message in-place. Falls back to answer() if edit fails."""
    try:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )


def build_main_menu_for_state(state: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if state == "new":
        builder.button(text=TRIAL_CTA_TEXT, callback_data="trial")
        builder.button(text="Купить подписку", callback_data="buy")
        builder.button(text="Помощь", callback_data="guide")
        builder.adjust(1, 1, 1)
    elif state == "trial_active":
        builder.button(text="Подключить", callback_data="config")
        builder.button(text="Купить подписку", callback_data="buy")
        builder.button(text="Помощь", callback_data="guide")
        builder.adjust(1, 1, 1)
    elif state == "paid_active":
        builder.button(text="Подключить", callback_data="config")
        builder.button(text="Кабинет", callback_data="account")
        builder.button(text="Помощь", callback_data="repair")
        builder.adjust(1, 1, 1)
    elif state == "expired":
        builder.button(text="Купить подписку", callback_data="buy")
        builder.button(text="Помощь", callback_data="guide")
        builder.adjust(1, 1)
    else:
        builder.button(text=TRIAL_CTA_TEXT, callback_data="trial")
        builder.button(text="Купить подписку", callback_data="buy")
        builder.button(text="Помощь", callback_data="guide")
        builder.adjust(1, 1, 1)
    return builder.as_markup()


def build_main_menu(user_id: int | None = None) -> InlineKeyboardMarkup:
    if user_id is None:
        return build_main_menu_for_state("new")
    state, _ = get_user_state(user_id)
    builder = InlineKeyboardBuilder.from_markup(build_main_menu_for_state(state))
    if get_latest_pending_payment(user_id):
        builder.button(text="Продолжить оплату", callback_data="buy:resume_latest")
    if is_admin(user_id):
        builder.button(text="Оператор", callback_data="admin")
        builder.adjust(2, 2, 2, 2, 1, 1)
    elif get_latest_pending_payment(user_id):
        builder.adjust(2, 2, 2, 2, 1)
    return builder.as_markup()


def get_recommended_plan_key(user_id: int) -> str:
    state, user = get_user_state(user_id)
    if state in {"new", "trial_active", "expired"}:
        return "basic_1m"
    if user and user.get("plan") in {"basic_6m", "basic_12m"}:
        return user["plan"]
    return "basic_3m"


def _plan_button_label(plan_key: str, plan: dict, recommended: bool) -> str:
    base_monthly = PLANS["basic_1m"]["amount"]
    per_month = round(plan["amount"] / (plan["days"] / 30))
    save_pct = round((1 - per_month / base_monthly) * 100) if per_month < base_monthly else 0
    devices = plan.get("devices", DEVICE_LIMITS.get(plan_key, 1))
    label = f"{plan['label']} • {plan['amount']}₽ • {devices} устр."
    if save_pct > 0:
        label += f" • -{save_pct}%"
    if recommended:
        label = f"⭐ {label}"
    return label


def build_buy_menu(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    latest_pending = get_latest_pending_payment(user_id)
    if latest_pending:
        builder.button(text="Продолжить оплату", callback_data="buy:resume_latest")
    payment_provider = get_active_payment_provider()
    recommended_key = get_recommended_plan_key(user_id)
    ordered_plan_keys = [recommended_key] + [key for key in PLANS if key != recommended_key]
    for plan_key in ordered_plan_keys:
        plan = PLANS[plan_key]
        label = _plan_button_label(plan_key, plan, plan_key == recommended_key)
        if payment_provider == "cardlink":
            builder.button(text=label, callback_data=f"buy:cardlink:{plan_key}")
        elif payment_provider == "yookassa":
            builder.button(text=label, callback_data=f"buy:yookassa:{plan_key}")
        elif payment_provider == "yoomoney":
            builder.button(text=label, callback_data=f"buy:yoomoney:{plan_key}")
        else:
            builder.button(text=label, callback_data="buy:manual")
    builder.button(text="Я уже оплатил", callback_data="buy:paid")
    builder.button(text="Мои заявки", callback_data="payments")
    builder.button(text="Назад", callback_data="menu")
    builder.adjust(1)
    return builder.as_markup()


def build_post_config_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Кабинет", callback_data="account")
    builder.button(text="Помощь", callback_data="repair")
    builder.button(text="Главное меню", callback_data="menu")
    builder.adjust(1, 1, 1)
    return builder.as_markup()


def build_payment_success_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Подключить", callback_data="config")
    builder.button(text="Кабинет", callback_data="account")
    builder.button(text="Помощь", callback_data="repair")
    builder.adjust(1, 1, 1)
    return builder.as_markup()


def build_connect_delivery_menu(
    context: str,
    *,
    has_fallback: bool = False,
    show_main_menu: bool = True,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_fallback:
        builder.button(text=fallback_delivery_button_text(), callback_data=f"connect:fallback:{context}")
    builder.button(text="Помощь", callback_data="guide")
    if show_main_menu:
        builder.button(text="Главное меню", callback_data="menu")
        builder.adjust(1, 1, 1)
    else:
        builder.adjust(1, 1)
    return builder.as_markup()


def build_waiting_payment_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Оплатил 1м", callback_data="buy:claim:basic_1m")
    builder.button(text="Оплатил 3м", callback_data="buy:claim:basic_3m")
    builder.button(text="Оплатил 6м", callback_data="buy:claim:basic_6m")
    builder.button(text="Оплатил 12м", callback_data="buy:claim:basic_12m")
    builder.button(text="Мои заявки", callback_data="payments")
    builder.button(text="Показать мой ID", callback_data="support:id")
    builder.button(text="Главное меню", callback_data="menu")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def build_support_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if SUPPORT_USERNAME:
        builder.button(text="Написать в поддержку", url=f"https://t.me/{SUPPORT_USERNAME}")
    builder.button(text="Показать мой ID", callback_data="support:id")
    builder.button(text="Личный кабинет", callback_data="account")
    builder.button(text="Купить подписку", callback_data="buy")
    builder.button(text="Главное меню", callback_data="menu")
    builder.adjust(1, 2, 2)
    return builder.as_markup()


def render_extra_device_slot_offer_text(user_id: int) -> str:
    user = get_user(user_id)
    current_extra = get_extra_device_slots_value(user, user_id)
    addon = DEVICE_SLOT_ADDONS["device_slot_1"]
    return (
        f"{BOT_BRAND}\n\n"
        "Дополнительный слот устройства\n\n"
        f"Сейчас докуплено: +{current_extra}\n"
        f"Лимит add-on слотов: +{MAX_EXTRA_DEVICE_SLOTS}\n"
        f"Покупка: {addon['label']}\n"
        f"Цена: {addon['amount']} ₽\n\n"
        "Слот добавится к аккаунту сразу после подтверждения оплаты."
    )


def build_extra_device_slot_menu(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    addon_key = "device_slot_1"
    if cardlink_configured():
        builder.button(text="Оплатить картой", callback_data=f"buy:cardlink:{addon_key}")
    if yookassa_configured():
        builder.button(text="Оплатить через СБП", callback_data=f"buy:yookassa:{addon_key}")
    if YOOMONEY_RECEIVER:
        builder.button(text="Оплатить YooMoney", callback_data=f"buy:yoomoney:{addon_key}")
    builder.button(text="Я уже оплатил", callback_data=f"buy:claim:{addon_key}")
    builder.button(text="Личный кабинет", callback_data="account")
    builder.button(text="Главное меню", callback_data="menu")
    builder.adjust(1, 1, 1, 1, 1)
    return builder.as_markup()


def build_account_menu(user_id: int) -> InlineKeyboardMarkup:
    state, user = get_user_state(user_id)
    builder = InlineKeyboardBuilder()
    if state == "new":
        builder.button(text=TRIAL_CTA_TEXT, callback_data="trial")
        builder.button(text="Купить подписку", callback_data="buy")
        builder.button(text="Помощь", callback_data="guide")
    elif state == "expired":
        builder.button(text="Продлить подписку", callback_data="buy")
        builder.button(text="Устройства", callback_data="devices")
        builder.button(text="Помощь", callback_data="guide")
    else:
        builder.button(text="Устройства", callback_data="devices")
        builder.button(text="Оплаты", callback_data="payments")
        builder.button(text="Пригласить друга", callback_data="invite")
        if user:
            expires_at = parse_expires_at(user.get("expires_at"))
            if expires_at and (expires_at - datetime.now()).days < 7:
                builder.button(text="Продлить", callback_data="buy")
            current_plan = user.get("plan", "")
            if current_plan and current_plan != "basic_12m" and current_plan != "trial":
                builder.button(text="Сменить план", callback_data="upgrade")
            if current_plan and current_plan != "trial":
                builder.button(text="Заморозить", callback_data="freeze")
                if get_extra_device_slots_value(user, user_id) < MAX_EXTRA_DEVICE_SLOTS:
                    builder.button(text="Докупить слот", callback_data="buy:addon:device_slot_1")
        builder.button(text="Помощь", callback_data="repair")
    if is_admin(user_id):
        builder.button(text="Оператор", callback_data="admin")
    builder.button(text="Главное меню", callback_data="menu")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def build_invite_menu(user_id: int) -> InlineKeyboardMarkup:
    invite_link = build_invite_link(user_id)
    share_text = quote(
        f"{BOT_BRAND}\n\n"
        f"{TRIAL_DAYS_TEXT} бесплатно.\n"
        "Подключение по QR или ссылке через Telegram.\n\n"
        f"{invite_link}",
        safe="",
    )
    share_url = (
        f"https://t.me/share/url?url={quote(invite_link, safe='')}"
        f"&text={share_text}"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="Поделиться ссылкой", url=share_url)
    builder.button(text="Мои бонусы", callback_data="rewards")
    builder.button(text="Личный кабинет", callback_data="account")
    builder.button(text="Главное меню", callback_data="menu")
    builder.adjust(1, 2, 1)
    return builder.as_markup()


def build_user_payments_menu(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for payment in get_recent_payments_for_user(user_id, limit=5):
        purchase_key = parse_payment_purchase_key(payment) or "manual"
        plan_label = render_purchase_label(purchase_key)
        amount = f"{payment.get('amount', 0):.0f}"
        status = payment.get("payment_status") or "unknown"
        status_label = render_user_payment_status(status)
        builder.button(
            text=f"#{payment['payment_id']} • {plan_label} • {amount}₽ • {status_label}",
            callback_data=f"user_payment:view:{payment['payment_id']}",
        )
    builder.button(text="Купить подписку", callback_data="buy")
    builder.button(text="Я уже оплатил", callback_data="buy:paid")
    builder.button(text="Личный кабинет", callback_data="account")
    builder.button(text="Главное меню", callback_data="menu")
    if is_admin(user_id):
        builder.button(text="Оператор", callback_data="admin")
    builder.adjust(1, 1, 1, 1, 2, 1)
    return builder.as_markup()


def build_yookassa_checkout_menu(confirmation_url: str, user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Оплатить через СБП", url=confirmation_url)
    builder.button(text="Мои заявки", callback_data="payments")
    builder.button(text="Личный кабинет", callback_data="account")
    builder.button(text="Главное меню", callback_data="menu")
    if is_admin(user_id):
        builder.button(text="Оператор", callback_data="admin")
    builder.adjust(1, 2, 1)
    return builder.as_markup()


def build_yoomoney_checkout_menu(payment_url: str, user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Оплатить", url=payment_url)
    builder.button(text="Мои заявки", callback_data="payments")
    builder.button(text="Главное меню", callback_data="menu")
    if is_admin(user_id):
        builder.button(text="Оператор", callback_data="admin")
    builder.adjust(1, 2, 1)
    return builder.as_markup()


def build_user_payment_detail_menu(
    payment: dict,
    user_id: int,
    confirmation_url: str | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if payment.get("payment_status") == "pending":
        builder.button(
            text="Обновить статус", callback_data=f"user_payment:refresh:{payment['payment_id']}"
        )
    if confirmation_url:
        provider_family = get_payment_provider_family(payment)
        open_text = "Оплатить" if provider_family == "yoomoney" else "Оплатить через СБП"
        builder.button(text=open_text, url=confirmation_url)
    builder.button(text="Мои заявки", callback_data="payments")
    builder.button(text="Главное меню", callback_data="menu")
    if is_admin(user_id):
        builder.button(text="Оператор", callback_data="admin")
    builder.adjust(1, 1, 1, 1)
    return builder.as_markup()


def build_admin_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Общая сводка", callback_data="admin:stats")
    builder.button(text="Здоровье VPN", callback_data="admin:vpn")
    builder.button(text="Техпанель", callback_data="admin:runtime")
    builder.button(text="Anti-Abuse", callback_data="admin:abuse")
    builder.button(text="Пользователи", callback_data="admin:users")
    builder.button(text="Платежи на проверке", callback_data="admin:payments")
    builder.button(text="Обработанные заявки", callback_data="admin:payments_done")
    builder.button(text="Проверить платежи сейчас", callback_data="admin:payments_sync")
    builder.button(text="Активировать по ID", callback_data="admin:user_lookup")
    builder.button(text="Выпустить без Telegram", callback_data="admin:offline")
    builder.button(text="Пользователь", callback_data="admin:user_help")
    builder.button(text="Рассылка", callback_data="admin:broadcast_templates")
    builder.button(text="Доходы", callback_data="admin:revenue")
    builder.button(text="Памятка", callback_data="admin:help")
    builder.button(text="Главное меню", callback_data="menu")
    builder.adjust(2, 2, 2, 2, 2, 2, 1)
    return builder.as_markup()


def build_admin_runtime_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Обновить сейчас", callback_data="admin:runtime:refresh")
    builder.button(text="Текст для клиента", callback_data="admin:runtime:reply")
    builder.button(text="Обновить здоровье VPN", callback_data="admin:runtime:health")
    builder.button(text="Синхронизировать устройства", callback_data="admin:runtime:devices")
    builder.button(text="Починить резерв 2083", callback_data="admin:runtime:secondary")
    builder.button(text="Проверить платежи", callback_data="admin:payments_sync")
    builder.button(text="Назад", callback_data="admin")
    builder.adjust(1, 1, 1, 1, 1)
    return builder.as_markup()


def build_admin_payment_queue_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    pending = get_pending_payments(limit=10)
    for payment in pending:
        username = (
            f"@{payment['username']}" if payment.get("username") else f"user {payment['user_id']}"
        )
        amount = f"{payment.get('amount', 0):.0f}"
        builder.button(
            text=f"#{payment['payment_id']} {username} • {amount} {payment.get('currency') or 'RUB'}",
            callback_data=f"admin_payment:view:{payment['payment_id']}",
        )
    builder.button(text="Оператор", callback_data="admin")
    builder.adjust(1)
    return builder.as_markup()


def build_admin_payment_menu(payment_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Подтвердить вручную", callback_data=f"admin_payment:approve_prompt:{payment_id}"
    )
    builder.button(text="Отклонить", callback_data=f"admin_payment:reject:{payment_id}")
    builder.button(text="Назад к очереди", callback_data="admin:payments")
    builder.button(text="Оператор", callback_data="admin")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def build_admin_payment_confirm_menu(payment_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Да, подтвердить", callback_data=f"admin_payment:approve:{payment_id}")
    builder.button(text="Назад к платежу", callback_data=f"admin_payment:view:{payment_id}")
    builder.button(text="К очереди", callback_data="admin:payments")
    builder.adjust(1, 1, 1)
    return builder.as_markup()


def build_admin_user_menu(target_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Продлить 1м", callback_data=f"admin_user:activate:{target_user_id}:basic_1m"
    )
    builder.button(
        text="Продлить 3м", callback_data=f"admin_user:activate:{target_user_id}:basic_3m"
    )
    builder.button(
        text="Продлить 6м", callback_data=f"admin_user:activate:{target_user_id}:basic_6m"
    )
    builder.button(
        text="Продлить 12м", callback_data=f"admin_user:activate:{target_user_id}:basic_12m"
    )
    builder.button(text="Устройства", callback_data=f"admin_user:devices:{target_user_id}")
    builder.button(text="Платежи", callback_data=f"admin_user:payments:{target_user_id}")
    builder.button(text="События", callback_data=f"admin_user:activity:{target_user_id}")
    builder.button(text="Отправить пользователю", callback_data=f"admin_user:deliver:{target_user_id}")
    builder.button(
        text="Профиль: Default/NL",
        callback_data=f"admin_user:profile:{target_user_id}:{DELIVERY_PROFILE_DEFAULT_NL}",
    )
    builder.button(
        text="Профиль: Android Stealth",
        callback_data=f"admin_user:profile:{target_user_id}:{DELIVERY_PROFILE_ANDROID_STEALTH_SPB}",
    )
    builder.button(
        text="Профиль: Fallback/NL",
        callback_data=f"admin_user:profile:{target_user_id}:{DELIVERY_PROFILE_FALLBACK_NL}",
    )
    builder.button(text="Удалить профиль", callback_data=f"admin_user:delete_prompt:{target_user_id}")
    builder.button(text="Обновить карточку", callback_data=f"admin_user:view:{target_user_id}")
    builder.button(text="Оператор", callback_data="admin")
    builder.adjust(2, 2, 2, 2, 2, 1)
    return builder.as_markup()


def build_admin_activation_menu(target_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="1м", callback_data=f"admin_user:activate:{target_user_id}:basic_1m")
    builder.button(text="3м", callback_data=f"admin_user:activate:{target_user_id}:basic_3m")
    builder.button(text="6м", callback_data=f"admin_user:activate:{target_user_id}:basic_6m")
    builder.button(text="12м", callback_data=f"admin_user:activate:{target_user_id}:basic_12m")
    builder.button(text="Полная карточка", callback_data=f"admin_user:view:{target_user_id}")
    builder.button(text="Оператор", callback_data="admin")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def build_admin_offline_issue_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Триал", callback_data="admin:offline:issue:trial")
    builder.button(text="1м", callback_data="admin:offline:issue:basic_1m")
    builder.button(text="3м", callback_data="admin:offline:issue:basic_3m")
    builder.button(text="6м", callback_data="admin:offline:issue:basic_6m")
    builder.button(text="12м", callback_data="admin:offline:issue:basic_12m")
    builder.button(text="Назад", callback_data="admin")
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def build_admin_offline_issued_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Выпустить ещё", callback_data="admin:offline")
    builder.button(text="Оператор", callback_data="admin")
    builder.adjust(1, 1)
    return builder.as_markup()


def build_admin_user_delete_confirm_menu(target_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Да, удалить профиль",
        callback_data=f"admin_user:delete_confirm:{target_user_id}",
    )
    builder.button(text="Назад к карточке", callback_data=f"admin_user:view:{target_user_id}")
    builder.button(text="Оператор", callback_data="admin")
    builder.adjust(1, 1, 1)
    return builder.as_markup()


def build_admin_users_menu(admin_user_id: int, limit: int = 20) -> InlineKeyboardMarkup:
    state = ADMIN_USER_BROWSER_STATE.get(admin_user_id, {})
    status = state.get("status", "all")
    search = state.get("search", "")
    offset = int(state.get("offset", "0"))
    page_size = int(state.get("page_size", str(ADMIN_USERS_PAGE_SIZE)))
    rows = get_recent_users(limit=page_size + 1, status=status, search=search, offset=offset)
    page_rows = rows[:page_size]
    has_next = len(rows) > page_size
    builder = InlineKeyboardBuilder()
    builder.button(text="Все", callback_data="admin:users:filter:all")
    builder.button(text="Active", callback_data="admin:users:filter:active")
    builder.button(text="Expired", callback_data="admin:users:filter:expired")
    builder.button(text="Trial", callback_data="admin:users:filter:trial")
    builder.button(text="Поиск", callback_data="admin:users:search")
    for user in page_rows:
        username = f"@{user['username']}" if user.get("username") else "без username"
        row_status = "active" if user.get("is_active") else "expired"
        builder.button(
            text=f"{user['user_id']} • {username} • {row_status}",
            callback_data=f"admin_user:quick:{user['user_id']}",
        )
    if offset > 0:
        prev_offset = max(offset - page_size, 0)
        builder.button(text="← Назад", callback_data=f"admin:users:page:{prev_offset}")
    if has_next:
        next_offset = offset + page_size
        builder.button(text="Вперёд →", callback_data=f"admin:users:page:{next_offset}")
    if search:
        builder.button(text="Сбросить поиск", callback_data="admin:users:search_clear")
    builder.button(text="Активировать по ID", callback_data="admin:user_lookup")
    builder.button(text="Оператор", callback_data="admin")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def build_admin_user_devices_menu(target_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    devices = get_user_devices(target_user_id)
    for device in devices:
        status_marker = "•" if device.get("status") == "active" else "×"
        builder.button(
            text=f"{status_marker} {device['device_name']}",
            callback_data=f"admin_user:device:{target_user_id}:{device['device_id']}",
        )
    builder.button(text="Назад к карточке", callback_data=f"admin_user:view:{target_user_id}")
    builder.button(text="Оператор", callback_data="admin")
    builder.adjust(1)
    return builder.as_markup()


def build_admin_user_device_menu(
    target_user_id: int, device_id: int, active: bool = True
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if active:
        builder.button(
            text="Отключить устройство",
            callback_data=f"admin_user:revoke_device:{target_user_id}:{device_id}",
        )
    builder.button(text="Назад к устройствам", callback_data=f"admin_user:devices:{target_user_id}")
    builder.button(text="Назад к карточке", callback_data=f"admin_user:view:{target_user_id}")
    builder.adjust(1)
    return builder.as_markup()


def build_guide_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Android", callback_data="guide:android")
    builder.button(text="iPhone / iPad", callback_data="guide:iphone")
    builder.button(text="Windows", callback_data="guide:windows")
    builder.button(text="Mac", callback_data="guide:mac")
    builder.button(text="Linux", callback_data="guide:linux")
    builder.button(text="Другое / QR", callback_data="guide:qr")
    builder.button(text="Главное меню", callback_data="menu")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def build_guide_platform_menu(platform: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if platform == "android":
        builder.button(text="Hiddify", url=HIDDIFY_DOWNLOAD_URL)
        builder.button(text="v2rayNG", url=V2RAYNG_PLAY_URL)
    elif platform == "iphone":
        builder.button(text="Streisand", url=STREISAND_APPSTORE_URL)
        builder.button(text="Happ", url=HAPP_APPSTORE_URL)
        builder.button(text="v2RayTun", url=V2RAYTUN_APPSTORE_URL)
    elif platform == "windows":
        builder.button(text="Hiddify", url=HIDDIFY_DOWNLOAD_URL)
        builder.button(text="v2rayN", url=V2RAYN_DOWNLOAD_URL)
    elif platform == "mac":
        builder.button(text="Hiddify", url=HIDDIFY_DOWNLOAD_URL)
    elif platform == "linux":
        builder.button(text="Hiddify", url=HIDDIFY_DOWNLOAD_URL)
    else:
        builder.button(text="Hiddify", url=HIDDIFY_DOWNLOAD_URL)
    builder.button(text="Назад", callback_data="guide")
    builder.button(text="Главное меню", callback_data="menu")
    builder.adjust(2, 1, 2)
    return builder.as_markup()


def build_devices_menu(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    state, user = get_user_state(user_id)
    devices = list_user_devices(user_id)
    limit = get_device_limit(user)

    for device in devices:
        status_marker = "•" if device.get("status") == "active" else "×"
        builder.button(
            text=f"{status_marker} {device['device_name']}",
            callback_data=f"device:show:{device['device_id']}",
        )

    if state != "new":
        if len(devices) < limit:
            builder.button(text="Добавить устройство", callback_data="device:add")
        elif user and resolve_plan_key(str(user.get("plan", "trial"))) != "trial":
            if get_extra_device_slots_value(user, user_id) < MAX_EXTRA_DEVICE_SLOTS:
                builder.button(text="Докупить слот (+1)", callback_data="buy:addon:device_slot_1")

    builder.button(text="Главное меню", callback_data="menu")
    builder.adjust(1)
    return builder.as_markup()


def is_device_slot_locked(device: dict | None) -> bool:
    return bool(device and device.get("first_seen_at"))


def format_device_timestamp(value: str | None, default: str = "ещё не зафиксировано") -> str:
    if not value:
        return default
    return value[:16].replace("T", " ")


def build_device_detail_menu(
    device_id: int, active: bool = True, locked: bool = False
) -> InlineKeyboardMarkup:
    device = get_device(device_id)
    primary = get_primary_device(device["user_id"]) if device else None
    is_primary = bool(primary and int(primary["device_id"]) == int(device_id))
    builder = InlineKeyboardBuilder()
    if active:
        builder.button(text="Получить профиль", callback_data=f"device:config:{device_id}")
        builder.button(text="Поделиться", callback_data=f"device:share:{device_id}")
        builder.button(text="Переименовать", callback_data=f"device:rename:{device_id}")
        if not is_primary:
            builder.button(
                text="Сделать основным", callback_data=f"device:make_primary:{device_id}"
            )
        if locked:
            builder.button(text="Заменить устройство", callback_data=f"device:replace:{device_id}")
        builder.button(text="Отключить устройство", callback_data=f"device:remove:{device_id}")
    builder.button(text="Назад к устройствам", callback_data="devices")
    builder.button(text="Главное меню", callback_data="menu")
    builder.adjust(1)
    return builder.as_markup()


def build_device_added_menu(device_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Подключить это устройство", callback_data=f"device:config:{device_id}")
    builder.button(text="Открыть карточку", callback_data=f"device:show:{device_id}")
    builder.button(text="Вернуться к списку", callback_data="devices")
    builder.adjust(1)
    return builder.as_markup()


def build_device_connect_menu(device_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="iPhone", callback_data=f"device:connect:{device_id}:iphone")
    builder.button(text="Android", callback_data=f"device:connect:{device_id}:android")
    builder.button(text="Компьютер", callback_data=f"device:connect:{device_id}:desktop")
    builder.button(text="Открыть карточку", callback_data=f"device:show:{device_id}")
    builder.button(text="Назад", callback_data=f"device:added:{device_id}")
    builder.adjust(2, 1, 1, 1)
    return builder.as_markup()


def build_device_platform_menu(device_id: int, platform: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if platform == "iphone":
        builder.button(text="Streisand", url=STREISAND_APPSTORE_URL)
        builder.button(text="Happ", url=HAPP_APPSTORE_URL)
    elif platform == "android":
        builder.button(text="Hiddify", url=HIDDIFY_DOWNLOAD_URL)
        builder.button(text="v2rayNG", url=V2RAYNG_PLAY_URL)
    else:
        builder.button(text="Hiddify", url=HIDDIFY_DOWNLOAD_URL)
        builder.button(text="v2rayN", url=V2RAYN_DOWNLOAD_URL)
    builder.button(
        text="Подключить ещё раз", callback_data=f"device:connect:{device_id}:{platform}"
    )
    builder.button(
        text="Выбрать другую платформу", callback_data=f"device:connect_menu:{device_id}"
    )
    builder.button(text="Открыть карточку", callback_data=f"device:show:{device_id}")
    builder.adjust(2, 1, 1, 1)
    return builder.as_markup()


def build_device_type_menu(user_id: int) -> InlineKeyboardMarkup:
    next_child_name = build_next_device_name(user_id, "child_phone")
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Мой телефон", callback_data="device:add:my_phone")
    builder.button(text="💻 Мой компьютер", callback_data="device:add:my_pc")
    builder.button(text=f"👶 {next_child_name}", callback_data="device:add:child_phone")
    builder.button(text="📟 Планшет", callback_data="device:add:tablet")
    builder.button(text="Другое", callback_data="device:add:other")
    builder.button(text="Назад к устройствам", callback_data="devices")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def render_device_type_text(user_id: int) -> str:
    next_child_name = build_next_device_name(user_id, "child_phone")
    return (
        f"{BOT_BRAND}\n\n"
        "Кто будет пользоваться этим устройством?\n\n"
        "Выбери понятное имя по умолчанию.\n"
        f"Например: «Мой телефон» или «{next_child_name}»."
    )


def _sudo_env() -> dict[str, str]:
    """Build env dict for subprocesses that need runtime paths."""
    env = os.environ.copy()
    rpk = os.environ.get("REALITY_PUBLIC_KEY", "")
    if rpk:
        env["REALITY_PUBLIC_KEY"] = rpk
    env["GHOST_ACCESS_DB_PATH"] = GHOST_ACCESS_DB_PATH
    env["DEVICE_ACTIVITY_STATE_FILE"] = DEVICE_ACTIVITY_STATE_FILE
    return env


def load_vless_profile(port: int) -> dict[str, str]:
    result = subprocess.run(
        [
            "python3",
            XRAY_CLIENT_MANAGER,
            "show-profile",
            "--port",
            str(port),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=_sudo_env(),
    )
    return json.loads(result.stdout)


def load_reality_profile() -> dict[str, str]:
    if PROFILE_VPN_SERVER != VPN_SERVER:
        return {
            "flow": "xtls-rprx-vision",
            "type": "tcp",
            "server_name": SPB_REALITY_SERVER_NAME,
            "fingerprint": SPB_REALITY_FINGERPRINT,
            "public_key": SPB_REALITY_PUBLIC_KEY,
            "short_id": SPB_REALITY_SHORT_ID,
        }
    return load_vless_profile(VPN_PORT)


def load_secondary_reality_profile() -> dict[str, str]:
    return load_vless_profile(SECONDARY_VPN_PORT)


def load_nl_beta_reality_profile() -> dict[str, str]:
    return {
        "flow": "xtls-rprx-vision",
        "type": "tcp",
        "server_name": NL_BETA_REALITY_SERVER_NAME,
        "fingerprint": NL_BETA_REALITY_FINGERPRINT,
        "public_key": NL_BETA_REALITY_PUBLIC_KEY,
        "short_id": NL_BETA_REALITY_SHORT_ID,
    }


def get_smart_sub_link(user_uuid: str) -> str:
    """Returns the Smart Subscription URL for the user."""
    base_url = os.getenv("BASE_URL", f"http://{VPN_SERVER}:8000")
    return f"{base_url}/sub/{user_uuid}"

def _generate_reality_link_for_port(
    user_uuid: str,
    port: int,
    profile: dict[str, str],
    label: str | None = None,
    *,
    host: str | None = None,
) -> str:
    fragment = quote(label or "x0tta6bl4-Access", safe="")
    endpoint = (host or PROFILE_VPN_SERVER).strip() or PROFILE_VPN_SERVER
    return (
        f"<REDACTED_VPN_URI>"
        "?security=reality"
        "&encryption=none"
        f"&flow={profile['flow']}"
        f"&type={profile['type']}"
        f"&sni={profile['server_name']}"
        f"&fp={profile['fingerprint']}"
        f"&pbk={profile['public_key']}"
        f"&sid={profile['short_id']}"
        f"#{fragment}"
    )


def generate_vless_link(user_uuid: str, label: str | None = None) -> str:
    return _generate_reality_link_for_port(user_uuid, VPN_PORT, load_reality_profile(), label=label)


def generate_secondary_reality_link(user_uuid: str, label: str | None = None) -> str:
    return _generate_reality_link_for_port(
        user_uuid,
        SECONDARY_VPN_PORT,
        load_secondary_reality_profile(),
        label=label or "x0tta6bl4-Access-Alt",
    )


def generate_nl_beta_reality_link(user_uuid: str, label: str | None = None) -> str:
    return _generate_reality_link_for_port(
        user_uuid,
        NL_BETA_VPN_PORT,
        load_nl_beta_reality_profile(),
        label=label or "x0tta6bl4-Access-NL-Fallback",
        host=NL_BETA_VPN_SERVER,
    )


def generate_spb_reality_link(user_uuid: str, label: str | None = None) -> str:
    fragment = quote(label or "x0tta6bl4-SPB", safe="")
    return (
        f"<REDACTED_VPN_URI>"
        "?security=reality"
        "&encryption=none"
        f"&flow={SPB_REALITY_FLOW}"
        f"&type={SPB_REALITY_NETWORK}"
        f"&sni={SPB_REALITY_SERVER_NAME}"
        f"&fp={SPB_REALITY_FINGERPRINT}"
        f"&pbk={SPB_REALITY_PUBLIC_KEY}"
        f"&sid={SPB_REALITY_SHORT_ID}"
        f"#{fragment}"
    )


def generate_xhttp_link(user_uuid: str, label: str | None = None) -> str:
    profile = load_vless_profile(8443)
    path = profile.get("path", "/xhttp")
    fragment = quote(label or "x0tta6bl4-Access-Alt", safe="")
    return (
        f"<REDACTED_VPN_URI>"
        "?security=tls"
        "&encryption=none"
        f"&type={profile['type']}"
        f"&path={path}"
        "&allowInsecure=1"
        f"#{fragment}"
    )


def build_transport_catalog(
    user_uuid: str,
    *,
    base_label: str | None = None,
    include_fallbacks: bool = False,
) -> list[dict[str, str | int]]:
    root = (base_label or "x0tta6bl4-Access").strip()
    catalog: list[dict[str, str | int]] = [
        {
            "kind": "primary_reality",
            "title": f"Основной {VPN_PORT}",
            "port": VPN_PORT,
            "link": generate_vless_link(user_uuid, label=root),
        }
    ]
    if include_fallbacks and ENABLE_SECONDARY_REALITY_FALLBACK:
        catalog.append(
            {
                "kind": "secondary_reality",
                "title": f"Резерв {SECONDARY_VPN_PORT}",
                "port": SECONDARY_VPN_PORT,
                "link": generate_secondary_reality_link(
                    user_uuid,
                    label=build_fallback_label(root),
                ),
            }
        )
    if include_fallbacks and ENABLE_XHTTP_FALLBACK:
        catalog.append(
            {
                "kind": "xhttp",
                "title": "XHTTP 8443",
                "port": 8443,
                "link": generate_xhttp_link(user_uuid, label=f"{root} XHTTP"),
            }
        )
    return catalog


def render_transport_bundle_text(
    user_uuid: str,
    *,
    base_label: str | None = None,
    include_fallbacks: bool = False,
) -> str:
    lines = [f"{BOT_BRAND}", "", "Основной профиль для Happ / Hiddify / v2rayN:"]
    for item in build_transport_catalog(
        user_uuid,
        base_label=base_label,
        include_fallbacks=include_fallbacks,
    ):
        lines.extend(
            [
                "",
                f"{item['title']}:",
                f"<code>{html.escape(str(item['link']))}</code>",
            ]
        )
    lines.extend(
        [
            "",
            "Используй один основной профиль. Если он не открывается после переимпорта, это уже операторская диагностика.",
        ]
    )
    return "\n".join(lines)


def generate_fallback_link(user_uuid: str, label: str | None = None) -> str:
    if not EXPOSE_FALLBACK_TRANSPORTS:
        return ""
    if ENABLE_SECONDARY_REALITY_FALLBACK:
        return generate_secondary_reality_link(user_uuid, label=label)
    if ENABLE_XHTTP_FALLBACK:
        return generate_xhttp_link(user_uuid, label=label)
    return ""


def fallback_delivery_button_text() -> str:
    if ENABLE_SECONDARY_REALITY_FALLBACK:
        return f"Резерв {SECONDARY_VPN_PORT}"
    return "Если не работает"


def fallback_profile_title() -> str:
    if ENABLE_SECONDARY_REALITY_FALLBACK:
        return f"резервный профиль {SECONDARY_VPN_PORT}"
    if ENABLE_XHTTP_FALLBACK:
        return "резервный профиль"
    return "резервный профиль"


def build_fallback_label(base_label: str | None = None) -> str:
    root = (base_label or "x0tta6bl4-Access").strip()
    if ENABLE_SECONDARY_REALITY_FALLBACK:
        return f"{root} Reserve-{SECONDARY_VPN_PORT}"
    if ENABLE_XHTTP_FALLBACK:
        return f"{root} Reserve"
    return f"{root} Alt"


def create_yoomoney_url(amount: int, user_id: int, plan_key: str) -> str | None:
    if not YOOMONEY_RECEIVER:
        return None

    payload = {
        "receiver": YOOMONEY_RECEIVER,
        "quickpay-form": "shop",
        "targets": f"{BOT_BRAND} {render_purchase_label(plan_key)}",
        "sum": amount,
        "label": f"ghost_{user_id}_{plan_key}",
    }
    return f"https://yoomoney.ru/quickpay/confirm.xml?{urlencode(payload)}"


def yookassa_configured() -> bool:
    return bool(YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY and YOOKASSA_RETURN_URL)


def get_active_payment_provider() -> str:
    if YOOMONEY_RECEIVER:
        return "yoomoney"
    if yookassa_configured():
        return "yookassa"
    if cardlink_configured():
        return "cardlink"
    return "none"


def build_yookassa_auth_header() -> str:
    token = base64.b64encode(f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}".encode("utf-8")).decode(
        "ascii"
    )
    return f"Basic {token}"


def automatic_payment_verification_enabled() -> bool:
    provider = get_active_payment_provider()
    return provider in ("cardlink", "yookassa") or (
        provider == "yoomoney" and bool(YOOMONEY_API_TOKEN)
    )


def create_yookassa_sbp_payment(user_id: int, plan_key: str) -> dict:
    if not yookassa_configured():
        raise RuntimeError("YOOKASSA credentials are not configured")
    plan = get_purchase_config(plan_key)
    if not plan:
        raise RuntimeError(f"Unknown purchase key: {plan_key}")
    payload = {
        "amount": {
            "value": f"{plan['amount']:.2f}",
            "currency": "RUB",
        },
        "payment_method_data": {
            "type": "sbp",
        },
        "confirmation": {
            "type": "redirect",
            "return_url": YOOKASSA_RETURN_URL,
        },
        "capture": True,
        "description": f"{BOT_BRAND} {render_purchase_label(plan_key)}",
        "metadata": {
            "user_id": str(user_id),
            "plan_key": plan_key,
        },
    }
    request = Request(
        "https://api.yookassa.ru/v3/payments",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": build_yookassa_auth_header(),
            "Idempotence-Key": str(uuid.uuid4()),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_yookassa_payment(payment_id: str) -> dict:
    request = Request(
        f"https://api.yookassa.ru/v3/payments/{payment_id}",
        headers={
            "Authorization": build_yookassa_auth_header(),
            "Content-Type": "application/json",
        },
        method="GET",
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def get_latest_pending_yookassa_payment(user_id: int, plan_key: str) -> dict | None:
    for payment in get_recent_payments_for_user(user_id, limit=10):
        if payment.get("payment_status") != "pending":
            continue
        if parse_payment_purchase_key(payment) != plan_key:
            continue
        if not (payment.get("payment_provider") or "").startswith("yookassa_sbp:"):
            continue
        return payment
    return None


def get_reusable_yookassa_payment(
    user_id: int, plan_key: str
) -> tuple[dict, dict] | tuple[None, None]:
    payment = get_latest_pending_yookassa_payment(user_id, plan_key)
    if not payment:
        return None, None
    payment_id = parse_yookassa_payment_id(payment)
    if not payment_id:
        return None, None
    try:
        remote_payment = fetch_yookassa_payment(payment_id)
    except Exception as exc:
        logger.warning(
            "failed to fetch reusable yookassa payment user_id=%s plan=%s: %s",
            user_id,
            plan_key,
            exc,
        )
        return payment, None
    if remote_payment.get("status") in {"pending", "waiting_for_capture", "succeeded"}:
        return payment, remote_payment
    return payment, remote_payment


def cardlink_configured() -> bool:
    return bool(CARDLINK_API_TOKEN and CARDLINK_SHOP_ID)


def create_cardlink_payment(user_id: int, plan_key: str) -> dict:
    """Create a CardLink bill and return {bill_id, payment_url}."""
    if not cardlink_configured():
        raise RuntimeError("CARDLINK credentials are not configured")
    plan = get_purchase_config(plan_key)
    if not plan:
        raise RuntimeError(f"Unknown purchase key: {plan_key}")
    order_id = f"ghost_{user_id}_{plan_key}_{uuid.uuid4().hex[:8]}"
    payload = {
        "amount": plan["amount"],
        "shop_id": CARDLINK_SHOP_ID,
        "order_id": order_id,
        "description": f"{BOT_BRAND} — {render_purchase_label(plan_key)}",
        "currency_in": "RUB",
        "custom": json.dumps({"user_id": user_id, "plan_key": plan_key}),
        "payer_pays_commission": 0,
        "payment_method": "BANK_CARD",
    }
    request = Request(
        "https://cardlink.link/api/v1/bill/create",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {CARDLINK_API_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not data.get("success"):
        raise RuntimeError(f"CardLink bill create failed: {data}")
    return {
        "bill_id": data.get("bill_id", ""),
        "payment_url": data.get("link_page_url") or data.get("link_url", ""),
        "order_id": order_id,
    }


def verify_cardlink_signature(out_sum: str, inv_id: str, signature: str) -> bool:
    """Verify CardLink webhook signature: MD5(OutSum:InvId:apiToken)."""
    import hashlib

    expected = hashlib.md5(f"{out_sum}:{inv_id}:{CARDLINK_API_TOKEN}".encode()).hexdigest().upper()
    return expected == (signature or "").upper()


def parse_cardlink_order_id(payment: dict | None) -> str | None:
    if not payment:
        return None
    provider = payment.get("payment_provider") or ""
    if not provider.startswith("cardlink:"):
        return None
    parts = provider.split(":")
    if len(parts) < 2:
        return None
    return parts[1] or None


def get_latest_pending_payment(
    user_id: int,
    plan_key: str | None = None,
    provider_prefix: str | None = None,
) -> dict | None:
    for payment in get_recent_payments_for_user(user_id, limit=10):
        if payment.get("payment_status") != "pending":
            continue
        if plan_key and parse_payment_purchase_key(payment) != plan_key:
            continue
        if provider_prefix and not (payment.get("payment_provider") or "").startswith(
            provider_prefix
        ):
            continue
        return payment
    return None


def get_matching_cardlink_pending_payment(
    user_id: int, plan_key: str, order_id: str | None = None
) -> dict | None:
    recent = get_recent_payments_for_user(user_id, limit=10, include_internal=True)
    if order_id:
        for payment in recent:
            if payment.get("payment_status") != "pending":
                continue
            provider = payment.get("payment_provider") or ""
            if provider.startswith(f"cardlink:{order_id}:"):
                return payment
    return get_latest_pending_payment(user_id, plan_key=plan_key, provider_prefix="cardlink:")


def get_processed_cardlink_payment(user_id: int, order_id: str) -> dict | None:
    recent = get_recent_payments_for_user(user_id, limit=20, include_internal=True)
    for payment in recent:
        provider = payment.get("payment_provider") or ""
        if not provider.startswith("cardlink_"):
            continue
        if f":{order_id}:" in provider:
            return payment
    return None


def build_existing_pending_payment_menu(payment_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Открыть заявку", callback_data=f"user_payment:view:{payment_id}")
    builder.button(text="Мои заявки", callback_data="payments")
    builder.button(text="Назад", callback_data="buy")
    builder.adjust(1, 2)
    return builder.as_markup()


def parse_expires_at(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def load_device_activity_sync_state() -> dict | None:
    try:
        with open(DEVICE_ACTIVITY_STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as exc:
        logger.warning("failed to load device activity state: %s", exc)
        return None


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS


def resolve_plan_key(plan_value: str | None) -> str:
    value = (plan_value or "").strip()
    if not value:
        return "trial"
    if value in PLANS or value in DEVICE_LIMITS:
        return value
    alias = PLAN_ALIASES.get(value.lower())
    if alias:
        return alias

    value_lower = value.lower()
    for plan_key, plan in PLANS.items():
        if value_lower == plan["label"].strip().lower():
            return plan_key
    return value


def resolve_purchase_key(value: str | None) -> str:
    candidate = (value or "").strip()
    if candidate in PLANS or candidate in DEVICE_SLOT_ADDONS:
        return candidate
    return resolve_plan_key(candidate)


def is_device_slot_addon_key(purchase_key: str | None) -> bool:
    return (purchase_key or "").strip() in DEVICE_SLOT_ADDONS


def get_purchase_config(purchase_key: str) -> PlanConfig | DeviceSlotAddonConfig | None:
    key = resolve_purchase_key(purchase_key)
    if key in PLANS:
        return PLANS[key]
    return DEVICE_SLOT_ADDONS.get(key)


def get_extra_device_slots_value(user: dict | None, user_id: int | None = None) -> int:
    if user is not None:
        try:
            return max(0, int(user.get("extra_device_slots") or 0))
        except (AttributeError, TypeError, ValueError):
            return 0
    if user_id is None and user:
        try:
            user_id = int(user["user_id"])
        except (KeyError, TypeError, ValueError):
            user_id = None
    if user_id is None:
        return 0
    return get_user_extra_device_slots(int(user_id))


def get_device_limit(user: dict | None) -> int:
    if not user:
        return 1
    plan_key = resolve_plan_key(str(user.get("plan", "trial")))
    plan = PLANS.get(plan_key)
    extra_slots = get_extra_device_slots_value(user)
    if plan and isinstance(plan.get("devices"), int):
        return int(plan["devices"]) + extra_slots
    return DEVICE_LIMITS.get(plan_key, 1) + extra_slots


def build_device_email(user_id: int, user_uuid: str, device_name: str | None = None) -> str:
    user = get_user(user_id) or {}
    resolved_device_name = device_name
    if not resolved_device_name:
        devices = list_user_devices(user_id)
        target = next((d for d in devices if d.get("vpn_uuid") == user_uuid), None)
        resolved_device_name = target.get("device_name") if target else "device"
    username = user.get("username")
    return build_human_xray_email(user_id, username, resolved_device_name, user_uuid)


def render_user_payment_status(status: str | None) -> str:
    return USER_PAYMENT_STATUS_LABELS.get(status or "", status or "unknown")


def render_user_payment_provider(provider: str | None) -> str:
    value = (provider or "").strip()
    if value.startswith("yookassa"):
        return "ЮKassa"
    if value.startswith("yoomoney"):
        return "YooMoney"
    if value == "admin_grant":
        return "Оператор"
    return value or "—"


def render_plan_label(plan_key: str | None) -> str:
    value = (plan_key or "").strip()
    if not value:
        return "вручную"
    if value == "trial":
        return TRIAL_CTA_TEXT
    return PLANS.get(value, {}).get("label", value)


def render_purchase_label(purchase_key: str | None) -> str:
    value = resolve_purchase_key(purchase_key)
    if value in PLANS:
        return render_plan_label(value)
    if value in DEVICE_SLOT_ADDONS:
        return DEVICE_SLOT_ADDONS[value]["label"]
    return value or "вручную"


def render_payment_next_step(status: str | None) -> str:
    value = (status or "").strip()
    if value == "pending":
        return "Ожидай подтверждение."
    if value in {"approved", "completed"}:
        return "Оплата подтверждена. Жми «Подключить»."
    if value == "expired":
        return "Заявка истекла. Создай новую через «Купить подписку»."
    if value == "rejected":
        return "Заявка отклонена. Проверь оплату и создай новую."
    return "Открой «Купить подписку», если хочешь создать новую заявку."


def render_payment_refresh_result(kind: str) -> str:
    if kind == "confirmed":
        return "Оплата подтверждена"
    if kind == "canceled":
        return "Платёж отменён"
    return "Статус обновлён"


def subscription_base_url() -> str:
    if SUBSCRIPTION_BASE_URL:
        return SUBSCRIPTION_BASE_URL
    return f"http://{VPN_SERVER}:{SUBSCRIPTION_HTTP_PORT}"


def web_access_base_url() -> str:
    if WEB_ACCESS_BASE_URL:
        return WEB_ACCESS_BASE_URL
    return subscription_base_url()


def build_subscription_url(user_id: int) -> str:
    token = ensure_user_subscription_token(user_id)
    return f"{subscription_base_url()}/sub/{token}"


def build_subscription_url_from_token(token: str) -> str:
    return f"{subscription_base_url()}/sub/{token}"


def build_access_portal_url(user_id: int) -> str:
    token = ensure_user_subscription_token(user_id)
    return build_access_portal_url_from_token(token)


def build_access_portal_url_from_token(token: str) -> str:
    return f"{web_access_base_url()}/access/{token}"


def build_android_stealth_bundle_url(user_id: int) -> str:
    token = ensure_user_subscription_token(user_id)
    return build_android_stealth_bundle_url_from_token(token)


def build_android_stealth_bundle_url_from_token(token: str) -> str:
    return f"{subscription_base_url()}/bundle/{token}/android-stealth.json"


def normalize_transport_preference(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"main", "fallback"}:
        return normalized
    return ""


def resolve_delivery_profile(user: dict | None) -> str:
    raw_profile = str((user or {}).get("delivery_profile") or "").strip().lower()
    if raw_profile in {
        DELIVERY_PROFILE_DEFAULT_NL,
        DELIVERY_PROFILE_ANDROID_STEALTH_SPB,
        DELIVERY_PROFILE_FALLBACK_NL,
    }:
        return raw_profile
    if bool((user or {}).get("stealth_mode_enabled")):
        return DELIVERY_PROFILE_ANDROID_STEALTH_SPB
    return DELIVERY_PROFILE_DEFAULT_NL


def resolve_entry_node(user: dict | None) -> str:
    profile = resolve_delivery_profile(user)
    if profile == DELIVERY_PROFILE_ANDROID_STEALTH_SPB:
        return ENTRY_NODE_SPB
    raw_entry = str((user or {}).get("entry_node") or "").strip().lower()
    if raw_entry in {ENTRY_NODE_NL, ENTRY_NODE_SPB}:
        return raw_entry
    return ENTRY_NODE_NL


def resolve_client_family(user: dict | None) -> str:
    profile = resolve_delivery_profile(user)
    if profile == DELIVERY_PROFILE_ANDROID_STEALTH_SPB:
        return CLIENT_FAMILY_ANDROID_STEALTH
    raw_family = str((user or {}).get("client_family") or "").strip().lower()
    if raw_family == CLIENT_FAMILY_ANDROID_STEALTH:
        return CLIENT_FAMILY_ANDROID_STEALTH
    return CLIENT_FAMILY_GENERIC


def is_android_stealth_profile(user: dict | None) -> bool:
    return resolve_delivery_profile(user) == DELIVERY_PROFILE_ANDROID_STEALTH_SPB


def build_delivery_connect_url(user: dict) -> str:
    user_id = int(user["user_id"])
    if is_android_stealth_profile(user):
        return build_android_stealth_bundle_url(user_id)
    return build_subscription_url(user_id)


def render_delivery_profile_label(profile: str) -> str:
    normalized = (profile or "").strip().lower()
    if normalized == DELIVERY_PROFILE_ANDROID_STEALTH_SPB:
        return "Android Stealth / SPB"
    if normalized == DELIVERY_PROFILE_FALLBACK_NL:
        return "Fallback / NL"
    return "Default / NL"


def apply_delivery_profile(user_id: int, profile: str) -> dict | None:
    normalized = (profile or "").strip().lower()
    if normalized == DELIVERY_PROFILE_ANDROID_STEALTH_SPB:
        update_user(
            user_id,
            delivery_profile=DELIVERY_PROFILE_ANDROID_STEALTH_SPB,
            entry_node=ENTRY_NODE_SPB,
            client_family=CLIENT_FAMILY_ANDROID_STEALTH,
            stealth_mode_enabled=True,
        )
    elif normalized == DELIVERY_PROFILE_FALLBACK_NL:
        update_user(
            user_id,
            delivery_profile=DELIVERY_PROFILE_FALLBACK_NL,
            entry_node=ENTRY_NODE_NL,
            client_family=CLIENT_FAMILY_GENERIC,
            stealth_mode_enabled=False,
        )
    else:
        update_user(
            user_id,
            delivery_profile=DELIVERY_PROFILE_DEFAULT_NL,
            entry_node=ENTRY_NODE_NL,
            client_family=CLIENT_FAMILY_GENERIC,
            stealth_mode_enabled=False,
        )
    return get_user(user_id)


def build_device_subscription_label(device: dict) -> str:
    device_name = (device.get("device_name") or "Device").strip()
    return f"{BOT_BRAND} • {device_name}"


def resolve_user_preferred_transport(
    user: dict | None, health_policy: dict[str, str] | None = None
) -> str:
    user_override = normalize_transport_preference((user or {}).get("transport_preference"))
    if user_override:
        return user_override
    preferred_transport = normalize_transport_preference(
        (health_policy or {}).get("preferred_transport", "main")
    )
    return preferred_transport or "main"


def apply_transport_mode_choice(user_id: int, mode: str) -> tuple[bool, str]:
    normalized = (mode or "").strip().lower()
    if normalized in {"fallback", "fast", "warp"}:
        update_user(user_id, transport_preference="fallback")
        log_activity(user_id, "transport_preference_changed:fallback")
        return (
            True,
            (
                f"{BOT_BRAND}\n\n"
                "⚡ Быстрый Telegram включён\n\n"
                f"В подписке резерв {SECONDARY_VPN_PORT} теперь закреплён первым. "
                "Это помогает, когда Telegram медленнее на основном маршруте."
            ),
        )
    if normalized in {"auto", "main", "direct"}:
        update_user(user_id, transport_preference="")
        log_activity(user_id, "transport_preference_changed:auto")
        return (
            True,
            (
                f"{BOT_BRAND}\n\n"
                "🌐 Автоматический режим включён\n\n"
                f"Бот снова сам выбирает порядок {VPN_PORT}/{SECONDARY_VPN_PORT} "
                "по состоянию маршрутов."
            ),
        )
    return False, ""


def ensure_subscription_devices(user: dict) -> list[dict]:
    user_id = int(user["user_id"])
    devices = list_user_devices(user_id)
    if devices:
        return devices

    expires_at = parse_expires_at(user.get("expires_at"))
    if not expires_at or datetime.now() > expires_at:
        return []

    try:
        device = create_next_device(user_id, device_type="my_phone")
        logger.warning(
            "subscription self-heal: restored active device user_id=%s device_id=%s",
            user_id,
            device.get("device_id"),
        )
    except Exception as exc:
        logger.warning("subscription self-heal failed user_id=%s: %s", user_id, exc)
        return []

    sync_primary_device(user_id, int(device["device_id"]))
    return list_user_devices(user_id)


def build_subscription_links_for_user(
    user: dict, health_policy: dict[str, str] | None = None
) -> list[str]:
    devices = ensure_subscription_devices(user)
    primary = get_primary_device(int(user["user_id"]))
    ordered: list[dict] = []
    if primary:
        ordered.append(primary)
    ordered.extend(
        device
        for device in devices
        if not primary or int(device["device_id"]) != int(primary["device_id"])
    )
    if not ordered and user.get("vpn_uuid"):
        ordered.append(
            {
                "device_name": "Основное устройство",
                "vpn_uuid": user["vpn_uuid"],
            }
        )
    links: list[str] = []
    preferred_transport = resolve_user_preferred_transport(user, health_policy)
    fallback_enabled = ENABLE_SECONDARY_REALITY_FALLBACK or ENABLE_XHTTP_FALLBACK
    for device in ordered:
        label = build_device_subscription_label(device)
        main_link = generate_vless_link(device["vpn_uuid"], label=label)
        fallback_link = (
            generate_fallback_link(device["vpn_uuid"], label=f"{label} Alt")
            if fallback_enabled
            else ""
        )
        if preferred_transport == "fallback" and fallback_link:
            links.append(fallback_link)
            links.append(main_link)
            continue

        links.append(main_link)
        if fallback_link:
            links.append(fallback_link)
    return links


def build_subscription_links_for_uuid(
    vpn_uuid: str,
    *,
    label_root: str,
    health_policy: dict[str, str] | None = None,
    user: dict | None = None,
) -> list[str]:
    preferred_transport = resolve_user_preferred_transport(user, health_policy)
    fallback_enabled = ENABLE_SECONDARY_REALITY_FALLBACK or ENABLE_XHTTP_FALLBACK
    main_link = generate_vless_link(vpn_uuid, label=label_root)
    fallback_link = (
        generate_fallback_link(vpn_uuid, label=build_fallback_label(label_root))
        if fallback_enabled
        else ""
    )
    if preferred_transport == "fallback" and fallback_link:
        return [fallback_link, main_link]
    if fallback_link:
        return [main_link, fallback_link]
    return [main_link]


def build_subscription_payload(
    user: dict, *, raw: bool = False, health_policy: dict[str, str] | None = None
) -> str:
    payload = "\n".join(build_subscription_links_for_user(user, health_policy=health_policy))
    if raw:
        return payload
    return base64.b64encode(payload.encode("utf-8")).decode("ascii")


def build_subscription_payload_for_offline(
    offline: dict,
    *,
    raw: bool = False,
    health_policy: dict[str, str] | None = None,
) -> str:
    label_root = (offline.get("label") or f"{BOT_BRAND} • Offline").strip()
    vpn_uuid = str(offline["vpn_uuid"])
    delivery_profile = str(offline.get("delivery_profile") or "").strip()
    entry_node = str(offline.get("entry_node") or "").strip()
    if delivery_profile == DELIVERY_PROFILE_ANDROID_STEALTH_SPB or entry_node == ENTRY_NODE_SPB:
        payload = generate_spb_reality_link(vpn_uuid, label=label_root)
    else:
        payload = "\n".join(
            build_subscription_links_for_uuid(
                vpn_uuid,
                label_root=label_root,
                health_policy=health_policy,
            )
        )
    if raw:
        return payload
    return base64.b64encode(payload.encode("utf-8")).decode("ascii")


def _resolve_android_stealth_identity(user: dict) -> dict[str, str]:
    devices = ensure_subscription_devices(user)
    primary = get_primary_device(int(user["user_id"]))
    ordered: list[dict] = []
    if primary:
        ordered.append(primary)
    ordered.extend(
        device
        for device in devices
        if not primary or int(device["device_id"]) != int(primary["device_id"])
    )
    if ordered:
        device = ordered[0]
        return {
            "uuid": str(device["vpn_uuid"]),
            "label": build_device_subscription_label(device),
        }
    if user.get("vpn_uuid"):
        return {
            "uuid": str(user["vpn_uuid"]),
            "label": f"{BOT_BRAND} • Android Stealth",
        }
    raise RuntimeError("android_stealth_requires_active_device")


def _build_android_stealth_entry(
    *,
    entry_id: str,
    role: str,
    server: str,
    port: int,
    user_uuid: str,
    profile: dict[str, str],
    label: str,
) -> dict[str, object]:
    return {
        "id": entry_id,
        "role": role,
        "transport": "vless_reality",
        "server": server,
        "port": port,
        "uuid": user_uuid,
        "network": profile["type"],
        "security": "reality",
        "flow": profile["flow"],
        "server_name": profile["server_name"],
        "fingerprint": profile["fingerprint"],
        "public_key": profile["public_key"],
        "short_id": profile["short_id"],
        "uri": _generate_reality_link_for_port(
            user_uuid,
            port,
            profile,
            label=label,
            host=server,
        ),
    }


def build_android_stealth_bundle(
    user: dict, *, health_policy: dict[str, str] | None = None
) -> dict[str, object]:
    identity = _resolve_android_stealth_identity(user)
    expires_at = parse_expires_at(user.get("expires_at"))
    health_policy = health_policy or build_subscription_health_policy()
    primary_label = f"{identity['label']} • SPB"
    fallback_label = f"{identity['label']} • NL Fallback"
    routing: dict[str, object] = {
        "ru_private_destinations": "direct",
        "foreign_destinations": "ghost_backend_via_nl",
    }
    entries = [
        _build_android_stealth_entry(
            entry_id="spb-primary",
            role="primary",
            server=PROFILE_VPN_SERVER,
            port=VPN_PORT,
            user_uuid=identity["uuid"],
            profile=load_reality_profile(),
            label=primary_label,
        )
    ]
    if ENABLE_ANDROID_STEALTH_NL_BETA_FALLBACK:
        routing["fallback_path"] = f"{NL_BETA_VPN_SERVER}:{NL_BETA_VPN_PORT}"
        entries.append(
            _build_android_stealth_entry(
                entry_id="nl-fallback-2443",
                role="fallback",
                server=NL_BETA_VPN_SERVER,
                port=NL_BETA_VPN_PORT,
                user_uuid=identity["uuid"],
                profile=load_nl_beta_reality_profile(),
                label=fallback_label,
            )
        )

    return {
        "schema_version": "ghost-access-android-stealth-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "profile": {
            "delivery_profile": DELIVERY_PROFILE_ANDROID_STEALTH_SPB,
            "entry_node": resolve_entry_node(user),
            "client_family": resolve_client_family(user),
            "mode": "allowlist_only",
        },
        "subscription": {
            "bundle_url": build_android_stealth_bundle_url(int(user["user_id"])),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "health_status": health_policy.get("health_status", "unknown"),
            "preferred_transport": health_policy.get("preferred_transport", "main"),
        },
        "android": {
            "vpn_scope": "allowlist_only",
            "allowed_packages": list(ANDROID_STEALTH_ALLOWED_PACKAGES),
            "non_allowed_apps": "direct",
            "dns": {
                "mode": "split",
                "vpn_dns_servers": list(ANDROID_STEALTH_VPN_DNS_SERVERS),
                "non_vpn_dns": "system",
                "direct_for_non_vpn_apps": True,
            },
        },
        "routing": routing,
        "entries": entries,
    }


def _default_vpn_service_agent_latest_path() -> Path:
    if VPN_SERVICE_AGENT_LATEST_PATH:
        return Path(VPN_SERVICE_AGENT_LATEST_PATH)
    candidates = [
        Path("/home/x0ttta6bl4/.local/state/vpn-service-access-agent/latest.json"),
        Path.home() / ".local/state/vpn-service-access-agent/latest.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def load_vpn_service_agent_payload() -> tuple[dict | None, bool, str]:
    path = _default_vpn_service_agent_latest_path()
    now = time.time()
    cached_path = str(_VPN_SERVICE_AGENT_CACHE.get("path") or "")
    if (
        _VPN_SERVICE_AGENT_CACHE.get("payload") is not None
        and cached_path == str(path)
        and now - float(_VPN_SERVICE_AGENT_CACHE.get("loaded_at") or 0.0)
        < VPN_SERVICE_AGENT_CACHE_SECONDS
    ):
        payload = _VPN_SERVICE_AGENT_CACHE.get("payload")
    else:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None, True, f"missing:{path}"
        except Exception as exc:
            logger.warning("failed to load vpn service agent payload from %s: %s", path, exc)
            return None, True, f"error:{path}"
        _VPN_SERVICE_AGENT_CACHE["loaded_at"] = now
        _VPN_SERVICE_AGENT_CACHE["path"] = str(path)
        _VPN_SERVICE_AGENT_CACHE["payload"] = payload

    generated_at = (payload or {}).get("generated_at") or ""
    try:
        generated_dt = datetime.strptime(generated_at, "%Y-%m-%dT%H:%M:%SZ")
        stale = (
            datetime.now(UTC).replace(tzinfo=None) - generated_dt
        ).total_seconds() > VPN_SERVICE_AGENT_STALE_SECONDS
    except Exception:
        stale = True
    return payload, stale, str(path)


def load_recent_warp_timeout_signal() -> dict[str, object]:
    now = time.time()
    cached_payload = _WARP_TIMEOUT_SIGNAL_CACHE.get("payload")
    if (
        cached_payload is not None
        and now - float(_WARP_TIMEOUT_SIGNAL_CACHE.get("loaded_at") or 0.0)
        < WARP_TIMEOUT_SIGNAL_CACHE_SECONDS
    ):
        return dict(cached_payload)

    since_expr = f"{WARP_TIMEOUT_SIGNAL_WINDOW_MINUTES} minutes ago"
    try:
        completed = subprocess.run(
            [
                "journalctl",
                "-u",
                "warp-svc",
                "--since",
                since_expr,
                "--no-pager",
                "-o",
                "short-iso",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
            env=_sudo_env(),
        )
        output = completed.stdout or ""
        timed_out_count = output.count("TimedOut")
        eof_count = output.count("UnexpectedEof")
        status = (
            "degraded"
            if timed_out_count >= WARP_TIMEOUT_SIGNAL_THRESHOLD
            or eof_count >= WARP_EOF_SIGNAL_THRESHOLD
            else "ok"
        )
        payload = {
            "status": status,
            "window_minutes": WARP_TIMEOUT_SIGNAL_WINDOW_MINUTES,
            "timed_out_count": timed_out_count,
            "unexpected_eof_count": eof_count,
            "checked_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    except Exception as exc:
        payload = {
            "status": "unknown",
            "window_minutes": WARP_TIMEOUT_SIGNAL_WINDOW_MINUTES,
            "timed_out_count": 0,
            "unexpected_eof_count": 0,
            "error": str(exc),
            "checked_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    _WARP_TIMEOUT_SIGNAL_CACHE["loaded_at"] = now
    _WARP_TIMEOUT_SIGNAL_CACHE["payload"] = dict(payload)
    return payload


def remember_vpn_delivery_sample(payload: dict | None) -> list[dict[str, object]]:
    samples = _VPN_DELIVERY_SAMPLE_CACHE.setdefault("samples", [])
    if not isinstance(samples, list):
        samples = []
        _VPN_DELIVERY_SAMPLE_CACHE["samples"] = samples

    vpn_delivery = (payload or {}).get("vpn_delivery") or {}
    reality_canary = vpn_delivery.get("reality_canary") or {}
    secondary_reality_canary = vpn_delivery.get("secondary_reality_canary") or {}
    generated_at = str((payload or {}).get("generated_at") or "")
    if not generated_at:
        return list(samples)
    if any(sample.get("generated_at") == generated_at for sample in samples if isinstance(sample, dict)):
        return list(samples)

    sample = {
        "generated_at": generated_at,
        "reality_ok": bool(reality_canary.get("ok")),
        "reality_total_s": float(reality_canary.get("total_s") or 0.0),
        "secondary_ok": bool(secondary_reality_canary.get("ok")),
        "secondary_total_s": float(secondary_reality_canary.get("total_s") or 0.0),
    }
    samples.append(sample)
    if len(samples) > 5:
        del samples[:-5]
    return list(samples)


def should_prefer_fallback_from_latency(samples: list[dict[str, object]]) -> bool:
    valid_samples = [
        sample
        for sample in samples
        if sample.get("reality_ok") and sample.get("secondary_ok")
    ]
    if len(valid_samples) < 3:
        return False
    recent = valid_samples[-3:]
    primary_values = [float(sample.get("reality_total_s") or 0.0) for sample in recent]
    secondary_values = [float(sample.get("secondary_total_s") or 0.0) for sample in recent]
    primary_median = statistics.median(primary_values)
    secondary_median = statistics.median(secondary_values)
    materially_faster_count = sum(
        1
        for primary, secondary in zip(primary_values, secondary_values)
        if (secondary + 0.25) < primary
    )
    return materially_faster_count >= 2 and (secondary_median + 0.25) < primary_median


def should_prefer_fallback_from_transport_summary(
    transport_summary: dict[str, object] | None,
    samples: list[dict[str, object]],
) -> bool:
    summary = transport_summary or {}
    if str(summary.get("best_path") or "") != "secondary":
        return False
    try:
        delta = float(summary.get("main_vs_secondary_delta_s") or 0.0)
    except (TypeError, ValueError):
        delta = 0.0
    if delta < 0.25:
        return False
    return should_prefer_fallback_from_latency(samples)


def should_prefer_fallback_for_telegram_media(
    transport_summary: dict[str, object] | None,
    telegram_media: dict[str, object] | None,
) -> bool:
    summary = transport_summary or {}
    media = telegram_media or {}
    if str(media.get("status") or "") != "degraded":
        return False
    if str(summary.get("best_path") or "") != "secondary":
        return False
    try:
        delta = float(summary.get("main_vs_secondary_delta_s") or 0.0)
    except (TypeError, ValueError):
        delta = 0.0
    return delta >= -0.05


def _service_has_recommendation(service: dict | None, prefix: str) -> bool:
    if not service:
        return False
    return any(
        isinstance(rec, str) and rec.startswith(prefix)
        for rec in (service.get("recommendations") or [])
    )


def _merge_health_status(current: str, candidate: str) -> str:
    rank = {"unknown": 0, "ok": 1, "healthy": 1, "advisory": 2, "degraded": 3, "stale": 4}
    return candidate if rank.get(candidate, 0) > rank.get(current, 0) else current


def build_subscription_health_policy() -> dict[str, str]:
    payload, stale, source_path = load_vpn_service_agent_payload()
    delivery_samples = remember_vpn_delivery_sample(payload)
    policy = {
        "profile_update_interval": "2",
        "health_status": "ok",
        "transport_health_status": "unknown",
        "subscription_health_status": "unknown",
        "preferred_transport": "main",
        "health_source": source_path,
        "health_generated_at": "",
    }
    if not payload:
        policy["health_status"] = "unknown"
        return policy

    policy["health_generated_at"] = str(payload.get("generated_at") or "")
    services = payload.get("services") or []
    global_recommendations = payload.get("global_recommendations") or []
    vpn_delivery = payload.get("vpn_delivery") or {}
    telegram_media = payload.get("telegram_media") or (vpn_delivery.get("telegram_media") or {})
    transport_summary = payload.get("transport_summary") or {}
    transport_paths = (transport_summary.get("paths") or {}) if isinstance(transport_summary, dict) else {}
    tcp_probe = vpn_delivery.get("tcp_probe") or {}
    xui_inbound = vpn_delivery.get("xui_inbound") or {}
    reality_canary = vpn_delivery.get("reality_canary") or {}
    secondary_xui_inbound = vpn_delivery.get("secondary_xui_inbound") or {}
    secondary_reality_canary = vpn_delivery.get("secondary_reality_canary") or {}
    subscription_edge = next(
        (service for service in services if service.get("service_id") == "subscription-edge"), None
    )
    degraded_services = [
        service
        for service in services
        if any(
            isinstance(rec, str) and (rec.startswith("route:") or rec.startswith("stability:"))
            for rec in (service.get("recommendations") or [])
        )
    ]
    warp_signal = load_recent_warp_timeout_signal()
    policy["warp_recent_status"] = str(warp_signal.get("status") or "unknown")
    policy["warp_recent_timed_out_count"] = str(warp_signal.get("timed_out_count") or 0)
    policy["warp_recent_unexpected_eof_count"] = str(
        warp_signal.get("unexpected_eof_count") or 0
    )
    policy["warp_recent_window_minutes"] = str(warp_signal.get("window_minutes") or 0)
    policy["foreign_egress_status"] = policy["warp_recent_status"]
    policy["quic_status"] = "blocked" if payload.get("quic_reject_present") else "ok"
    policy["telegram_media_status"] = str(telegram_media.get("status") or "unknown")
    if telegram_media.get("best_target"):
        policy["telegram_media_best_target"] = str(telegram_media.get("best_target"))
    if telegram_media.get("best_latency_s") is not None:
        policy["telegram_media_best_latency_s"] = f"{float(telegram_media.get('best_latency_s') or 0):.3f}"
    if telegram_media.get("worst_target"):
        policy["telegram_media_worst_target"] = str(telegram_media.get("worst_target"))
    if telegram_media.get("worst_latency_s") is not None:
        policy["telegram_media_worst_latency_s"] = f"{float(telegram_media.get('worst_latency_s') or 0):.3f}"
    if telegram_media.get("latency_spread_s") is not None:
        policy["telegram_media_latency_spread_s"] = f"{float(telegram_media.get('latency_spread_s') or 0):.3f}"

    announce: str | None = None
    if reality_canary.get("total_s") is not None:
        policy["reality_canary_total_s"] = f"{float(reality_canary.get('total_s') or 0):.3f}"
    if reality_canary.get("http_code") is not None:
        policy["reality_canary_http_code"] = str(reality_canary.get("http_code"))
    if secondary_reality_canary.get("total_s") is not None:
        policy["secondary_reality_canary_total_s"] = (
            f"{float(secondary_reality_canary.get('total_s') or 0):.3f}"
        )
    if secondary_reality_canary.get("http_code") is not None:
        policy["secondary_reality_canary_http_code"] = str(
            secondary_reality_canary.get("http_code")
        )
    if delivery_samples:
        policy["delivery_sample_count"] = str(len(delivery_samples))
    if transport_summary.get("status"):
        policy["transport_health_status"] = str(transport_summary.get("status") or "unknown")
    if transport_summary.get("best_path"):
        policy["best_path"] = str(transport_summary.get("best_path"))
    if transport_summary.get("main_vs_secondary_delta_s") is not None:
        policy["main_vs_secondary_delta_s"] = str(transport_summary.get("main_vs_secondary_delta_s"))
    for path_name, header_key in (
        ("main", "primary_path_latency_s"),
        ("secondary", "secondary_path_latency_s"),
        ("fallback_nl", "fallback_nl_path_latency_s"),
    ):
        latency = ((transport_paths.get(path_name) or {}).get("latency_s"))
        if latency is not None:
            policy[header_key] = f"{float(latency):.3f}"
    if subscription_edge:
        subscription_status = "healthy"
        direct_probe = (subscription_edge.get("availability") or {}).get("direct") or {}
        if not bool(direct_probe.get("ok")) or _service_has_recommendation(subscription_edge, "stability:"):
            subscription_status = "degraded"
        elif _service_has_recommendation(subscription_edge, "speed:"):
            subscription_status = "advisory"
        policy["subscription_health_status"] = subscription_status
        policy["subscription_best_mode"] = str(subscription_edge.get("best_mode") or "unknown")
        if direct_probe.get("total_s") is not None:
            policy["subscription_direct_total_s"] = f"{float(direct_probe.get('total_s') or 0):.3f}"
    else:
        policy["subscription_health_status"] = "unknown"

    if stale:
        policy["profile_update_interval"] = "2"
        policy["health_status"] = "stale"
        policy["transport_health_status"] = "stale"
        policy["subscription_health_status"] = "stale"
        announce = "Проверка маршрутов устарела. Подписка обновляется чаще до стабилизации."
    elif reality_canary and reality_canary.get("ok") is False:
        policy["profile_update_interval"] = "2"
        policy["health_status"] = "degraded"
        policy["transport_health_status"] = "degraded"
        if ENABLE_SECONDARY_REALITY_FALLBACK and secondary_reality_canary.get("ok"):
            policy["preferred_transport"] = "fallback"
            announce = "Основной транспорт нестабилен. Переключаю на резервный."
        elif ENABLE_XHTTP_FALLBACK:
            policy["preferred_transport"] = "fallback"
            announce = "Основной транспорт нестабилен. Переключаю на резервный."
        else:
            announce = "Подключение сейчас проверяется повторно. Подписка обновляется чаще."
    elif (
        ENABLE_SECONDARY_REALITY_FALLBACK
        and secondary_reality_canary.get("ok")
        and should_prefer_fallback_from_transport_summary(transport_summary, delivery_samples)
    ):
        policy["profile_update_interval"] = "5"
        policy["health_status"] = "advisory"
        policy["transport_health_status"] = "advisory"
        policy["preferred_transport"] = "fallback"
        announce = (
            "Резервный транспорт стабильно быстрее по последним проверкам. "
            "Временно ставлю его первым."
        )
    elif (
        reality_canary
        and reality_canary.get("ok")
        and float(reality_canary.get("total_s") or 0) > 1.2
    ):
        policy["profile_update_interval"] = "5"
        policy["health_status"] = "advisory"
        policy["transport_health_status"] = "advisory"
        if (
            ENABLE_SECONDARY_REALITY_FALLBACK
            and secondary_reality_canary.get("ok")
            and should_prefer_fallback_from_latency(delivery_samples)
        ):
            policy["preferred_transport"] = "fallback"
            announce = (
                "Основной транспорт медленнее уже несколько проверок подряд. "
                "Временно ставлю резервный первым."
            )
        else:
            announce = (
                "Подключение работает, но текущая задержка похожа на разовый всплеск. "
                "Основной маршрут пока не переключаю."
            )
    elif tcp_probe and not tcp_probe.get("ok"):
        policy["profile_update_interval"] = "2"
        policy["health_status"] = "degraded"
        policy["transport_health_status"] = "degraded"
        announce = "Сервер доступа отвечает нестабильно. Подписка обновляется чаще."
    elif xui_inbound and (
        not xui_inbound.get("ok")
        or (
            xui_inbound.get("client_count") is not None
            and int(xui_inbound.get("client_count") or 0) <= 0
        )
    ):
        policy["profile_update_interval"] = "2"
        policy["health_status"] = "degraded"
        policy["transport_health_status"] = "degraded"
        if (
            ENABLE_SECONDARY_REALITY_FALLBACK
            and secondary_xui_inbound.get("ok")
            and secondary_reality_canary.get("ok")
        ):
            policy["preferred_transport"] = "fallback"
            announce = "Основной транспорт восстанавливается. Временно использую резервный."
        else:
            announce = "Проверка профилей показала проблему. Идёт восстановление."
    elif payload.get("quic_reject_present"):
        policy["profile_update_interval"] = "2"
        policy["health_status"] = "advisory"
        announce = "YouTube может стартовать медленнее. Идёт обновление маршрута."
    elif subscription_edge and any(
        isinstance(rec, str) and rec.startswith("stability:")
        for rec in (subscription_edge.get("recommendations") or [])
    ):
        policy["profile_update_interval"] = "2"
        policy["health_status"] = "degraded"
        policy["subscription_health_status"] = "degraded"
        announce = "Ссылка подписки сейчас отвечает нестабильно. Идёт повторная проверка."
    elif subscription_edge and any(
        isinstance(rec, str) and rec.startswith("speed:")
        for rec in (subscription_edge.get("recommendations") or [])
    ):
        policy["profile_update_interval"] = "5"
        policy["health_status"] = "advisory"
        policy["subscription_health_status"] = "advisory"
        announce = "Ссылка подписки отвечает медленнее обычного. Транспорт пока не переключаю."
    elif str(telegram_media.get("status") or "") == "degraded":
        policy["profile_update_interval"] = "2"
        policy["health_status"] = "degraded"
        if (
            ENABLE_SECONDARY_REALITY_FALLBACK
            and secondary_reality_canary.get("ok")
            and should_prefer_fallback_for_telegram_media(transport_summary, telegram_media)
        ):
            policy["preferred_transport"] = "fallback"
            announce = (
                "Telegram-медиа сейчас идёт медленнее обычного с нашего узла. "
                "Текстовые сообщения и подключение живы, но фото и видео могут загружаться дольше. "
                "Временно ставлю резервный маршрут первым."
            )
        else:
            announce = (
                "Telegram-медиа сейчас идёт медленнее обычного с нашего узла. "
                "Текстовые сообщения и подключение живы, но фото и видео могут загружаться дольше."
            )
    elif str(telegram_media.get("status") or "") == "advisory":
        policy["profile_update_interval"] = "5"
        policy["health_status"] = "advisory"
        announce = (
            "Часть Telegram-медиа узлов отвечает медленнее обычного. "
            "Если фото или видео открываются с задержкой, это уже видно на стороне маршрута."
        )
    elif warp_signal.get("status") == "degraded":
        policy["profile_update_interval"] = "2"
        policy["health_status"] = "advisory"
        announce = (
            "Маршрут через WARP сейчас нестабилен. Telegram работает напрямую, "
            "но YouTube и часть зарубежных сайтов могут открываться хуже обычного."
        )
    elif degraded_services:
        policy["profile_update_interval"] = "2"
        policy["health_status"] = "degraded"
        names = ", ".join(service.get("service_id", "service") for service in degraded_services[:2])
        announce = f"Часть сервисов идёт через резервный маршрут: {names}."

    if policy["transport_health_status"] == "unknown":
        transport_status = str(transport_summary.get("status") or "unknown")
        if transport_status != "unknown":
            policy["transport_health_status"] = transport_status
    if policy["subscription_health_status"] == "unknown":
        policy["subscription_health_status"] = "healthy" if subscription_edge else "unknown"
    if policy["transport_health_status"] == "stale":
        policy["health_status"] = _merge_health_status(policy["health_status"], "stale")
    elif policy["transport_health_status"] == "degraded":
        policy["health_status"] = _merge_health_status(policy["health_status"], "degraded")
    elif policy["transport_health_status"] == "advisory":
        policy["health_status"] = _merge_health_status(policy["health_status"], "advisory")
    if policy["subscription_health_status"] == "degraded":
        policy["health_status"] = _merge_health_status(policy["health_status"], "degraded")
    elif policy["subscription_health_status"] == "advisory":
        policy["health_status"] = _merge_health_status(policy["health_status"], "advisory")

    if announce:
        policy["announce"] = announce
    return policy


def render_subscription_text(user: dict) -> str:
    expires_at = parse_expires_at(user.get("expires_at"))
    expiry_text = expires_at.strftime("%d.%m.%Y %H:%M") if expires_at else "—"
    devices = list_user_devices(int(user["user_id"]))
    delivery_url = build_delivery_connect_url(user)
    delivery_profile = resolve_delivery_profile(user)
    if delivery_profile == DELIVERY_PROFILE_ANDROID_STEALTH_SPB:
        return (
            f"{BOT_BRAND}\n\n"
            "Android Stealth bundle:\n"
            f"<code>{html.escape(delivery_url)}</code>\n\n"
            f"Устройств: {len(devices)}\n"
            f"До: {expiry_text}\n"
            "Профиль: Android Stealth / SPB\n\n"
            "Это отдельный Android-only JSON bundle.\n"
            "Разрешённые foreign-приложения идут через SPB → Ghost → NL, остальные приложения остаются direct."
        )

    sub_url = build_subscription_url(int(user["user_id"]))
    return (
        f"{BOT_BRAND}\n\n"
        "Твоя ссылка подписки:\n"
        f"<code>{html.escape(sub_url)}</code>\n\n"
        f"Устройств: {len(devices)}\n"
        f"До: {expiry_text}\n"
        "Эта ссылка постоянная — профиль обновляется автоматически."
    )


def render_subscription_iphone_help(user_id: int) -> str:
    sub_url = build_subscription_url(user_id)
    return (
        f"{BOT_BRAND}\n\n"
        "iPhone / iPad\n\n"
        "Быстрый путь:\n"
        "1. Установи Happ или Streisand\n"
        "2. Нажми «Подключить» в боте\n"
        "3. Импортируй QR или ссылку\n"
        "4. Разреши добавить конфигурацию\n\n"
        "Если файл не открывается, вставь саму ссылку:\n\n"
        f"<code>{html.escape(sub_url)}</code>"
    )


def render_connect_fallback_help(fallback_link: str) -> str:
    if not fallback_link:
        return (
            f"{BOT_BRAND}\n\n"
            "Резервный профиль сейчас не настроен.\n\n"
            "Открой «Помощь» или напиши в поддержку."
        )
    return (
        f"{BOT_BRAND}\n\n"
        f"Если основной {VPN_PORT} режется оператором или не открывает Telegram / YouTube:\n\n"
        f"1. Импортируй этот резерв {SECONDARY_VPN_PORT}\n"
        "2. Включи его вместо основного\n\n"
        "Это нормальный резерв для российских сетей.\n\n"
        f"<code>{html.escape(fallback_link)}</code>"
    )


class XrayError(RuntimeError):
    """Raised when xray client management subprocess fails."""


def _run_xray_cmd(args: list[str], action: str) -> None:
    """Run an xray management command with graceful error handling."""
    try:
        subprocess.run(
            args,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
            env=_sudo_env(),
        )
    except subprocess.CalledProcessError as exc:
        logger.error("xray %s failed (rc=%d): %s", action, exc.returncode, exc.stdout)
        raise XrayError(
            f"Ошибка управления профилем ({action}). Попробуй позже или обратись к администратору."
        ) from exc
    except subprocess.TimeoutExpired:
        logger.error("xray %s timed out", action)
        raise XrayError(
            f"Таймаут операции ({action}). Попробуй позже или обратись к администратору."
        )


def _run_xray_cmd_output(args: list[str], action: str) -> tuple[int, str]:
    try:
        result = subprocess.run(
            args,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=XRAY_RUNTIME_CMD_TIMEOUT_SECONDS,
            env=_sudo_env(),
        )
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        logger.warning("xray %s timed out after %ss", action, XRAY_RUNTIME_CMD_TIMEOUT_SECONDS)
        return 124, output.strip()
    output = (result.stdout or "").strip()
    if result.returncode != 0:
        logger.warning("xray %s non-zero rc=%d output=%s", action, result.returncode, output)
    return result.returncode, output


def check_xray_port_alive(port: int = VPN_PORT, timeout: float = 3.0) -> bool:
    """TCP connect check — True if xray is accepting connections on given port."""
    try:
        with socket.create_connection((VPN_SERVER, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def check_xray_ports_health() -> dict[int, bool]:
    """Check all production xray ports. Returns {port: alive}."""
    ports = [VPN_PORT]
    if ENABLE_SECONDARY_REALITY_FALLBACK:
        ports.append(SECONDARY_VPN_PORT)
    if ENABLE_XHTTP_FALLBACK:
        ports.append(8443)
    return {port: check_xray_port_alive(port) for port in ports}


def _load_xray_runtime_ports() -> tuple[str | None, dict[int, str]]:
    if XRAY_RUNTIME_API_SERVER and XRAY_RUNTIME_TAGS:
        try:
            raw_tags = json.loads(XRAY_RUNTIME_TAGS)
            inbound_tags = {int(port): str(tag) for port, tag in raw_tags.items() if str(tag).strip()}
            return XRAY_RUNTIME_API_SERVER, inbound_tags
        except Exception as exc:
            logger.warning("failed to parse XRAY_RUNTIME_TAGS override: %s", exc)

    try:
        with open(XRAY_RUNTIME_CONFIG_PATH, "r", encoding="utf-8") as fh:
            config = json.load(fh)
    except Exception as exc:
        logger.warning("failed to read xray runtime config %s: %s", XRAY_RUNTIME_CONFIG_PATH, exc)
        return None, {}

    api_server = None
    inbound_tags: dict[int, str] = {}
    for inbound in config.get("inbounds", []):
        tag = inbound.get("tag") or ""
        port = inbound.get("port")
        if tag == "api" and inbound.get("listen") and port:
            api_server = f"{inbound.get('listen')}:{port}"
        if isinstance(port, int) and tag:
            inbound_tags[port] = tag
    return api_server, inbound_tags


def _run_runtime_user_manager(args: list[str], action: str) -> bool:
    rc, output = _run_xray_cmd_output(
        ["python3", XRAY_RUNTIME_USER_MANAGER, *args],
        action=action,
    )
    if rc != 0:
        logger.warning("runtime user manager failed action=%s output=%s", action, output)
        return False
    return True


def try_add_xray_client_runtime(
    user_uuid: str,
    email: str | None,
    user_id: int,
    ports: list[int],
    flow_by_port: dict[int, str],
) -> bool:
    if not email:
        return False
    api_server, inbound_tags = _load_xray_runtime_ports()
    if not api_server:
        return False
    attempted = False
    for port in ports:
        inbound_tag = inbound_tags.get(port)
        if not inbound_tag:
            continue
        attempted = True
        flow = flow_by_port.get(port, "xtls-rprx-vision")
        ok = _run_runtime_user_manager(
            [
                "--server",
                api_server,
                "add-user",
                "--tag",
                inbound_tag,
                "--email",
                email,
                "--uuid",
                user_uuid,
                "--flow",
                flow,
            ],
            action=f"runtime-add-user:{port}",
        )
        if not ok:
            return False
        logger.info("runtime added user email=%s port=%s flow=%s", email, port, flow)
    return attempted


def try_remove_xray_client_runtime(email: str | None, ports: list[int]) -> bool:
    if not email:
        return False
    api_server, inbound_tags = _load_xray_runtime_ports()
    if not api_server:
        return False
    attempted = False
    for port in ports:
        inbound_tag = inbound_tags.get(port)
        if not inbound_tag:
            continue
        attempted = True
        ok = _run_runtime_user_manager(
            [
                "--server",
                api_server,
                "remove-user",
                "--tag",
                inbound_tag,
                "--email",
                email,
            ],
            action=f"runtime-remove-user:{port}",
        )
        if ok:
            logger.info("runtime removed user email=%s port=%s", email, port)
        else:
            logger.warning("runtime remove fallback needed email=%s port=%s", email, port)
            return False
    return attempted


async def _debounced_xray_reload() -> None:
    global _XRAY_RELOAD_TASK
    try:
        await asyncio.sleep(XRAY_RELOAD_DEBOUNCE_SECONDS)
        reasons = sorted(_XRAY_RELOAD_REASONS)
        _XRAY_RELOAD_REASONS.clear()
        logger.info("reloading xray after queued changes: %s", ", ".join(reasons) or "unspecified")
        await asyncio.to_thread(
            _run_xray_cmd,
            ["pkill", "-f", "xray-linux-amd64.real"],
            "restart-xray-batch",
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("debounced xray reload failed: %s", exc)
    finally:
        _XRAY_RELOAD_TASK = None


def schedule_xray_reload(reason: str) -> None:
    global _XRAY_RELOAD_TASK
    _XRAY_RELOAD_REASONS.add(reason)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        try:
            _run_xray_cmd(["pkill", "-f", "xray-linux-amd64.real"], action="restart-xray")
        except XrayError as exc:
            logger.warning("immediate xray reload failed outside event loop: %s", exc)
        return
    if _XRAY_RELOAD_TASK and not _XRAY_RELOAD_TASK.done():
        _XRAY_RELOAD_TASK.cancel()
    _XRAY_RELOAD_TASK = loop.create_task(_debounced_xray_reload())


def ensure_xray_client(user_id: int, user_uuid: str, email: str | None = None) -> None:
    started = time.monotonic()
    email = email or build_device_email(user_id, user_uuid)
    runtime_ports = [VPN_PORT]
    flow_by_port = {VPN_PORT: "xtls-rprx-vision"}
    _run_xray_cmd(
        [
            "python3",
            XRAY_CLIENT_MANAGER,
            "ensure-client",
            "--port",
            str(VPN_PORT),
            "--uuid",
            user_uuid,
            "--email",
            email,
            "--flow",
            "xtls-rprx-vision",
            "--tg-id",
            str(user_id),
        ],
        action="ensure-client:reality",
    )
    if ENABLE_SECONDARY_REALITY_FALLBACK:
        runtime_ports.append(SECONDARY_VPN_PORT)
        flow_by_port[SECONDARY_VPN_PORT] = "xtls-rprx-vision"
        _run_xray_cmd(
            [
                "python3",
                XRAY_CLIENT_MANAGER,
                "ensure-client",
                "--port",
                str(SECONDARY_VPN_PORT),
                "--uuid",
                user_uuid,
                "--email",
                email,
                "--flow",
                "xtls-rprx-vision",
                "--tg-id",
                str(user_id),
            ],
            action="ensure-client:secondary-reality",
        )
    if ENABLE_XHTTP_FALLBACK:
        runtime_ports.append(8443)
        flow_by_port[8443] = ""
        _run_xray_cmd(
            [
                "python3",
                XRAY_CLIENT_MANAGER,
                "ensure-client",
                "--port",
                "8443",
                "--uuid",
                user_uuid,
                "--email",
                email,
                "--flow",
                "",
            ],
            action="ensure-client:xhttp",
        )
    runtime_ok = try_add_xray_client_runtime(user_uuid, email, user_id, runtime_ports, flow_by_port)
    if not runtime_ok:
        schedule_xray_reload(f"ensure:{email}")
    logger.info(
        "ensure_xray_client email=%s runtime_ok=%s elapsed=%.3fs",
        email,
        runtime_ok,
        time.monotonic() - started,
    )


def remove_xray_client(user_uuid: str, email: str | None = None) -> None:
    started = time.monotonic()
    ports = [VPN_PORT]
    if ENABLE_SECONDARY_REALITY_FALLBACK:
        ports.append(SECONDARY_VPN_PORT)
    if ENABLE_XHTTP_FALLBACK:
        ports.append(8443)
    for port in ports:
        _run_xray_cmd(
            [
                "python3",
                XRAY_CLIENT_MANAGER,
                "remove-client",
                "--port",
                str(port),
                "--uuid",
                user_uuid,
                "--email",
                email or "",
            ],
            action=f"remove-client:{port}",
        )
    runtime_ok = try_remove_xray_client_runtime(email, ports)
    if not runtime_ok:
        schedule_xray_reload(f"remove:{email or user_uuid}")
    logger.info(
        "remove_xray_client email=%s runtime_ok=%s elapsed=%.3fs",
        email or user_uuid,
        runtime_ok,
        time.monotonic() - started,
    )


def list_user_devices(user_id: int) -> list[dict]:
    ensure_legacy_primary_device(user_id)
    return get_user_devices(user_id)


def sync_primary_device(user_id: int, preferred_device_id: int | None = None) -> dict | None:
    ensure_legacy_primary_device(user_id)
    user = get_user(user_id)
    devices = get_user_devices(user_id)
    if not devices:
        if user and (user.get("vpn_uuid") or user.get("vpn_config")):
            update_user(user_id, vpn_uuid="", vpn_config="")
        return None

    selected = None
    if preferred_device_id is not None:
        selected = next(
            (device for device in devices if int(device["device_id"]) == int(preferred_device_id)),
            None,
        )
    if not selected and user and user.get("vpn_uuid"):
        selected = next(
            (device for device in devices if device.get("vpn_uuid") == user.get("vpn_uuid")), None
        )
    if not selected:
        selected = devices[0]

    main_link = generate_vless_link(selected["vpn_uuid"])
    updates: dict[str, object] = {}
    if not user or user.get("vpn_uuid") != selected["vpn_uuid"]:
        updates["vpn_uuid"] = selected["vpn_uuid"]
    if not user or user.get("vpn_config") != main_link:
        updates["vpn_config"] = main_link
    if updates:
        update_user(user_id, **updates)
    return selected


def get_primary_device(user_id: int) -> dict | None:
    return sync_primary_device(user_id)


def is_primary_device(device: dict | None) -> bool:
    if not device:
        return False
    primary = get_primary_device(int(device["user_id"]))
    return bool(primary and int(primary["device_id"]) == int(device["device_id"]))


def build_next_device_name(user_id: int, device_type: str) -> str:
    devices = get_user_devices(user_id, include_revoked=True)
    same_type = [device for device in devices if device.get("device_type") == device_type]
    idx = len(same_type) + 1

    if device_type == "my_phone":
        return "Мой телефон" if idx == 1 else f"Телефон {idx}"
    if device_type == "my_pc":
        return "Мой компьютер" if idx == 1 else f"Компьютер {idx}"
    if device_type == "child_phone":
        return f"Телефон ребенка {idx}"
    if device_type == "tablet":
        return "Планшет" if idx == 1 else f"Планшет {idx}"
    if device_type == "other":
        return f"Устройство {idx}"

    label = DEVICE_TYPE_LABELS.get(device_type, DEVICE_TYPE_LABELS["other"])
    if not DEVICE_TYPE_NUMBERING.get(device_type, True) and not same_type:
        return label
    return f"{label} {idx}"


def build_device_rename_presets(user_id: int) -> list[tuple[str, str]]:
    next_child_name = build_next_device_name(user_id, "child_phone")
    return [
        ("📱 Мой телефон", "Мой телефон"),
        ("💻 Мой компьютер", "Мой компьютер"),
        (f"👶 {next_child_name}", next_child_name),
        ("📟 Планшет", "Планшет"),
        ("🏠 Домашний компьютер", "Домашний компьютер"),
        ("💼 Рабочий ноутбук", "Рабочий ноутбук"),
    ]


def normalize_device_name_input(raw: str) -> str:
    return " ".join((raw or "").strip().split())[:48]


def apply_device_rename(
    user_id: int,
    device_id: int,
    new_name: str,
    *,
    device_type: str | None = None,
) -> tuple[dict, str]:
    device = get_device(device_id)
    if not device or device["user_id"] != user_id:
        raise RuntimeError("Устройство не найдено.")

    cleaned = normalize_device_name_input(new_name)
    if len(cleaned) < 2:
        raise RuntimeError("Имя слишком короткое.")

    devices = list_user_devices(user_id)
    same_name = [d for d in devices if d["device_name"] == cleaned and d["device_id"] != device_id]
    final_name = f"{cleaned} {len(same_name) + 1}" if same_name else cleaned

    update_device(device_id, device_name=final_name, device_type=device_type if device_type else None)
    updated = get_device(device_id)
    if not updated:
        raise RuntimeError("Устройство не найдено.")

    new_email = build_device_email(user_id, updated["vpn_uuid"])
    ensure_xray_client(user_id, updated["vpn_uuid"], new_email)
    update_device(device_id, xray_email=new_email)
    updated = get_device(device_id) or updated
    return updated, final_name


try:
    from src.core.bot_intelligence_bridge import bridge
except ImportError:
    class _FallbackBridge:
        async def get_best_server_config(self, user_id: int) -> dict[str, int]:
            return {"recommended_port": 443}

        async def poll_healing_events(self) -> list[dict]:
            return []

    bridge = _FallbackBridge()

def create_next_device(user_id: int, device_type: str = "my_phone") -> dict:
    user = get_user(user_id)
    if not user:
        raise RuntimeError("User not found")

    devices = list_user_devices(user_id)
    limit = get_device_limit(user)
    if len(devices) >= limit:
        raise RuntimeError("Device limit reached")

    user_uuid = str(uuid.uuid4())
    device_name = build_next_device_name(user_id, device_type)
    xray_email = build_device_email(user_id, user_uuid, device_name=device_name)
    device = create_device(
        user_id=user_id,
        device_name=device_name,
        device_type=device_type,
        vpn_uuid=user_uuid,
        xray_email=xray_email,
        profile_kind="reality",
    )
    try:
        ensure_xray_client(user_id, user_uuid, xray_email)
    except Exception:
        delete_device(int(device["device_id"]))
        raise
    sync_primary_device(user_id)
    log_activity(user_id, f"device_added:{device_name}")
    return device

async def intelligence_notification_task(bot: Bot):
    """Background task to notify users about network healing events."""
    logger.info("Starting Intelligence Notification Task...")
    while True:
        try:
            events = await bridge.poll_healing_events()
            for event in events:
                # Notify all active users or just the ones affected?
                # For now, we notify based on broadcast logic or skip if info is too noisy.
                if event["severity"] == "critical":
                    msg = (
                        f"🛡 **System Auto-Healing Active**\n\n"
                        f"Action: `{event['type']}`\n"
                        f"Reason: {event['reason']}\n\n"
                        f"_The mesh network is adapting to stay online._"
                    )
                    # For demo: logging instead of actual spam to all users
                    logger.info(f"AI NOTIFICATION: {msg}")

            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Error in intelligence notification task: {e}")
            await asyncio.sleep(60)


def _restore_subscription_snapshot(user_id: int, snapshot: dict[str, object]) -> None:
    if not snapshot.get("existed"):
        delete_user_account(user_id)
        return

    update_user(
        user_id,
        plan=snapshot["plan"] if isinstance(snapshot.get("plan"), str) else None,
        expires_at=snapshot["expires_at"]
        if isinstance(snapshot.get("expires_at"), datetime)
        else None,
        vpn_uuid=str(snapshot.get("vpn_uuid") or ""),
        vpn_config=str(snapshot.get("vpn_config") or ""),
        trial_used=bool(snapshot.get("trial_used")),
    )


def ensure_user_trial(user_id: int, username: str | None) -> dict | None:
    """Activate trial for new users. Returns None if trial already used."""
    user = get_user(user_id)

    # Block repeated trial activation
    if has_trial_claim(user_id):
        if user and user.get("trial_used"):
            expires_at = parse_expires_at(user.get("expires_at"))
            if expires_at and datetime.now() < expires_at and user.get("plan") == "trial":
                return user
        return None

    if user and user.get("trial_used"):
        # Allow if trial is currently active (return existing user)
        expires_at = parse_expires_at(user.get("expires_at"))
        if expires_at and datetime.now() < expires_at and user.get("plan") == "trial":
            return user
        # Trial was used and expired — no second trial
        return None

    expires_at = datetime.now() + timedelta(days=TRIAL_DAYS)
    snapshot = {
        "existed": bool(user),
        "plan": (user or {}).get("plan"),
        "expires_at": parse_expires_at((user or {}).get("expires_at")),
        "vpn_uuid": (user or {}).get("vpn_uuid") or "",
        "vpn_config": (user or {}).get("vpn_config") or "",
        "trial_used": bool((user or {}).get("trial_used")),
    }

    if not user:
        create_user(
            user_id=user_id,
            username=username,
            plan="trial",
            expires_at=expires_at,
            trial_used=False,
        )

    try:
        device = create_next_device(user_id, device_type="unknown")
    except Exception:
        _restore_subscription_snapshot(user_id, snapshot)
        raise

    vpn_config = generate_vless_link(device["vpn_uuid"])
    update_user(
        user_id,
        plan="trial",
        expires_at=expires_at,
        vpn_uuid=device["vpn_uuid"],
        vpn_config=vpn_config,
        trial_used=True,
    )
    log_activity(user_id, "trial_activated")
    ensure_trial_claim(user_id)

    referrer_user_id = mark_referral_trial_started(user_id)
    if referrer_user_id:
        granted_days = grant_referral_bonus_days(
            referrer_user_id,
            REFERRAL_TRIAL_BONUS_DAYS,
            cap_days=REFERRAL_BONUS_CAP_DAYS,
        )
        if granted_days > 0:
            logger.info(
                "granted referral trial bonus to user_id=%s days=%s referred_user_id=%s",
                referrer_user_id,
                granted_days,
                user_id,
            )

    fresh = get_user(user_id)
    if not fresh:
        raise RuntimeError(f"Failed to load user {user_id} after trial activation")
    return fresh


def activate_paid_plan(
    user_id: int,
    username: str | None,
    plan_key: str,
    provider: str = "yoomoney_manual",
    *,
    record_billing: bool = True,
    reward_referral: bool = True,
) -> dict:
    if plan_key not in PLANS:
        raise ValueError(f"Unknown plan: {plan_key}")

    plan = PLANS[plan_key]
    user = get_user(user_id)

    now = datetime.now()
    current_expiry = parse_expires_at((user or {}).get("expires_at"))
    base_time = current_expiry if current_expiry and current_expiry > now else now
    expires_at = base_time + timedelta(days=plan["days"])

    snapshot = {
        "existed": bool(user),
        "plan": (user or {}).get("plan"),
        "expires_at": parse_expires_at((user or {}).get("expires_at")),
        "vpn_uuid": (user or {}).get("vpn_uuid") or "",
        "vpn_config": (user or {}).get("vpn_config") or "",
        "trial_used": bool((user or {}).get("trial_used")),
    }

    if not user:
        create_user(
            user_id=user_id,
            username=username,
            plan=plan_key,
            expires_at=expires_at,
            trial_used=False,
        )

    try:
        devices = list_user_devices(user_id)
        if not devices:
            device = create_next_device(user_id, device_type="unknown")
        else:
            device = devices[0]
            ensure_xray_client(user_id, device["vpn_uuid"], device.get("xray_email"))
    except Exception:
        _restore_subscription_snapshot(user_id, snapshot)
        raise

    vpn_config = generate_vless_link(device["vpn_uuid"])
    update_user(
        user_id,
        plan=plan_key,
        expires_at=expires_at,
        vpn_uuid=device["vpn_uuid"],
        vpn_config=vpn_config,
    )
    log_activity(user_id, f"plan_activated_{plan_key}" if snapshot["existed"] else f"plan_created_{plan_key}")

    if record_billing:
        record_payment(
            user_id=user_id,
            amount=plan["amount"],
            currency="RUB",
            provider=provider,
            status="completed",
        )
    if record_billing and reward_referral:
        referrer_user_id = mark_referral_paid(
            referred_user_id=user_id,
            amount=plan["amount"],
            currency="RUB",
        )
        if referrer_user_id:
            granted_days = grant_referral_bonus_days(
                referrer_user_id,
                REFERRAL_BONUS_DAYS,
                cap_days=REFERRAL_BONUS_CAP_DAYS,
            )
            if granted_days > 0:
                logger.info(
                    "granted referral bonus to user_id=%s days=%s referred_user_id=%s",
                    referrer_user_id,
                    granted_days,
                    user_id,
                )

    fresh = get_user(user_id)
    if not fresh:
        raise RuntimeError(f"Failed to load user {user_id} after activation")
    return fresh


def claim_operator_issued_subscription(user_id: int, username: str | None, claim_code: str) -> dict:
    claimed = claim_offline_subscription(claim_code, user_id, username)
    user = get_user(user_id)
    if not user:
        raise RuntimeError(f"Failed to load user {user_id} after offline claim")

    devices = list_user_devices(user_id)
    if not devices:
        raise RuntimeError(f"Offline claim {claim_code} created no device for user {user_id}")

    device = devices[0]
    ensure_xray_client(user_id, device["vpn_uuid"], device.get("xray_email"))
    vpn_config = generate_vless_link(device["vpn_uuid"])
    update_user(
        user_id,
        plan=claimed["plan"],
        vpn_uuid=device["vpn_uuid"],
        vpn_config=vpn_config,
    )
    fresh = get_user(user_id)
    if not fresh:
        raise RuntimeError(f"Failed to refresh user {user_id} after offline claim")
    return fresh


def generate_offline_claim_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    suffix = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"OFFLINE-{suffix}"


def resolve_offline_issue_plan(plan_key: str) -> dict[str, object]:
    normalized = PLAN_ALIASES.get((plan_key or "").strip(), (plan_key or "").strip())
    if normalized == "trial":
        return {
            "plan_key": "trial",
            "days": TRIAL_DAYS,
            "label": TRIAL_CTA_TEXT,
        }

    plan = PLANS.get(normalized)
    if not plan:
        raise ValueError(f"Unknown offline plan: {plan_key}")

    return {
        "plan_key": normalized,
        "days": int(plan["days"]),
        "label": render_plan_label(normalized),
    }


def issue_operator_offline_subscription(plan_key: str) -> dict[str, object]:
    plan = resolve_offline_issue_plan(plan_key)

    expires_at = datetime.now() + timedelta(days=int(plan["days"]))
    last_error: Exception | None = None
    for _ in range(8):
        claim_code = generate_offline_claim_code()
        subscription_token = secrets.token_urlsafe(24)
        vpn_uuid = str(uuid.uuid4())
        xray_email = f"offline-{claim_code.lower()}@x0tta6bl4"
        label_suffix = claim_code.split("-", 1)[1]
        label = f"{BOT_BRAND}-Offline-{label_suffix}"
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO offline_subscriptions (
                        claim_code, subscription_token, vpn_uuid, xray_email, plan, days, expires_at, label
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        claim_code,
                        subscription_token,
                        vpn_uuid,
                        xray_email,
                        str(plan["plan_key"]),
                        int(plan["days"]),
                        expires_at.isoformat(),
                        label,
                    ),
                )
        except Exception as exc:
            last_error = exc
            continue

        try:
            ensure_xray_client(0, vpn_uuid, xray_email)
        except Exception:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM offline_subscriptions WHERE claim_code = ?",
                    (claim_code,),
                )
            raise
        main_link = generate_vless_link(vpn_uuid, label=label)
        fallback_link = generate_fallback_link(vpn_uuid, label=build_fallback_label(label))
        return {
            "claim_code": claim_code,
            "subscription_token": subscription_token,
            "subscription_url": build_subscription_url_from_token(subscription_token),
            "vpn_uuid": vpn_uuid,
            "xray_email": xray_email,
            "plan_key": str(plan["plan_key"]),
            "expires_at": expires_at,
            "main_link": main_link,
            "fallback_link": fallback_link,
        }

    if last_error:
        raise RuntimeError(f"failed to issue offline subscription: {last_error}") from last_error
    raise RuntimeError("failed to issue offline subscription")


def get_active_user(user_id: int):
    user = get_user(user_id)
    if not user:
        return None
    expires_at = parse_expires_at(user.get("expires_at"))
    if not expires_at or datetime.now() > expires_at:
        return None
    return user


def get_device_links(device: dict) -> tuple[str, str]:
    label = build_device_subscription_label(device)
    main_link = generate_vless_link(device["vpn_uuid"], label=label)
    fallback_link = generate_fallback_link(device["vpn_uuid"], label=build_fallback_label(label))
    return main_link, fallback_link


def get_user_links(user: dict) -> tuple[str, str]:
    device = sync_primary_device(user["user_id"])
    target_uuid = device["vpn_uuid"] if device else user["vpn_uuid"]
    catalog = build_transport_catalog(
        target_uuid,
        base_label=BOT_BRAND,
        include_fallbacks=EXPOSE_FALLBACK_TRANSPORTS,
    )
    main_link = str(catalog[0]["link"])
    fallback_link = str(catalog[1]["link"]) if len(catalog) > 1 else ""
    if user.get("vpn_config") != main_link:
        update_user(user["user_id"], vpn_config=main_link)
        user["vpn_config"] = main_link
    return main_link, fallback_link


def render_devices_text(user_id: int) -> str:
    state, user = get_user_state(user_id)
    if state == "new":
        return (
            f"{BOT_BRAND}\n\nУстройства появятся после активации теста.\n\nЖми «{TRIAL_CTA_TEXT}»."
        )

    devices = list_user_devices(user_id)
    limit = get_device_limit(user)
    lines = [f"{BOT_BRAND}", "", f"Мои устройства ({len(devices)}/{limit})"]

    if not devices:
        lines.extend(
            [
                "",
                "Пока нет устройств. Нажми «Добавить устройство».",
                "",
                "Примеры: Мой телефон, Мой компьютер, Телефон ребёнка 1.",
            ]
        )
    else:
        lines.append("")
        for index, device in enumerate(devices, 1):
            marker = "★" if is_primary_device(device) else "•"
            online = ""
            if device.get("last_seen_at"):
                online = f" — был онлайн {format_device_timestamp(device.get('last_seen_at'))}"
            lines.append(f"{marker} {index}/{limit} {device['device_name']}{online}")

    if len(devices) < limit:
        free = limit - len(devices)
        lines.extend(["", f"Свободно слотов: {free}"])
    lines.extend(["", "Выбери устройство или добавь новое."])
    return "\n".join(lines)


def render_devices_result_text(user_id: int, notice: str) -> str:
    base = render_devices_text(user_id)
    return f"{BOT_BRAND}\n\n{notice}\n\n" + base.replace(f"{BOT_BRAND}\n\n", "", 1)


def render_device_added_text(device: dict) -> str:
    return (
        f"{BOT_BRAND}\n\n"
        f"Готово: добавлено «{device['device_name']}».\n\n"
        "Теперь просто нажми «Подключить это устройство»."
    )


def render_device_connect_menu_text(device: dict) -> str:
    return f"{BOT_BRAND}\n\nПодключить «{device['device_name']}»\n\nГде ты хочешь его открыть?"


def render_device_platform_text(device: dict, platform: str) -> str:
    if platform == "iphone":
        title = "iPhone"
        help_text = (
            "1. Установи Streisand или Happ\n"
            "2. Ниже уже отправлен QR и чистая ссылка\n"
            "3. Если ссылка не открылась, сканируй QR"
        )
    elif platform == "android":
        title = "Android"
        help_text = (
            "1. Установи Hiddify или v2rayNG\n"
            "2. Ниже уже отправлен QR и чистая ссылка\n"
            "3. После импорта включи VPN / TUN режим для всех приложений\n"
            "4. Если ссылка не открылась, сканируй QR"
        )
    else:
        title = "Компьютер"
        help_text = (
            "1. На Windows удобно v2rayN или Hiddify\n"
            "2. На Mac и Linux удобнее Hiddify\n"
            "3. Ниже уже отправлен QR и чистая ссылка"
        )
    return f"{BOT_BRAND}\n\n{device['device_name']} • {title}\n\n{help_text}"


def render_device_detail_text(device: dict) -> str:
    device_type = DEVICE_TYPE_LABELS.get(
        device.get("device_type"), device.get("device_type", "unknown")
    )
    created_at = format_device_timestamp(device.get("created_at"), default="—")
    first_seen = format_device_timestamp(device.get("first_seen_at"))
    last_seen = format_device_timestamp(device.get("last_seen_at"))
    last_handshake = format_device_timestamp(device.get("last_handshake_at"))
    last_ip = device.get("last_ip") or "—"
    locked = is_device_slot_locked(device)
    role = "основное" if is_primary_device(device) else "дополнительное"
    binding = "привязан" if locked else "не привязан"
    hint = (
        "Чтобы перенести на другой телефон/ПК — жми «Заменить устройство»."
        if locked
        else "После первого подключения устройство будет привязано к этому слоту."
    )
    return (
        f"{BOT_BRAND}\n\n"
        f"{device['device_name']}\n\n"
        f"Статус: {device['status']}\n"
        f"Тип: {device_type}\n"
        f"Роль: {role}\n"
        f"Привязка: {binding}\n"
        f"Создано: {created_at}\n"
        f"Первый вход: {first_seen}\n"
        f"Последний вход: {last_seen}\n"
        f"Handshake: {last_handshake}\n"
        f"IP: {last_ip}\n\n"
        f"{hint}"
    )


def render_status_text(user_id: int) -> str:
    summary = render_state_summary(user_id)
    if summary["state"] in {"new", "expired"}:
        expiry_line = ""
        if summary["expiry"] != "—":
            expiry_line = f"\nИстекла: {summary['expiry']}"
        return (
            f"{BOT_BRAND}\n\n"
            f"{summary['headline']}.{expiry_line}\n\n"
            f"{summary['next_step']}"
            f"{summary['pending_hint']}"
        )
    return (
        f"{BOT_BRAND}\n\n"
        f"{summary['headline']}\n"
        f"Тариф: {summary['plan']}\n"
        f"До: {summary['expiry']}\n"
        f"Сервер: {VPN_SERVER}:{VPN_PORT}\n\n"
        f"{summary['next_step']}"
        f"{summary['pending_hint']}"
    )


def format_time_left(expires_at: datetime | None) -> str:
    if not expires_at:
        return "неизвестно"
    delta = expires_at - datetime.now()
    if delta.total_seconds() <= 0:
        return "истекло"
    days = delta.days
    hours = delta.seconds // 3600
    if days > 0:
        return f"{days} дн. {hours} ч."
    return f"{hours} ч."


def render_pending_hint(user_id: int, prefix: str = "Есть незавершённая заявка") -> str:
    latest_pending = get_latest_pending_payment(user_id)
    if not latest_pending:
        return ""
    return f"\n\n{prefix} #{latest_pending['payment_id']}."


def render_user_plan_value(user: dict | None) -> str:
    if not user:
        return "—"
    return render_plan_label(user.get("plan"))


def render_user_expiry_value(user: dict | None) -> tuple[datetime | None, str]:
    expires_at = parse_expires_at((user or {}).get("expires_at"))
    return expires_at, expires_at.strftime("%d.%m.%Y %H:%M") if expires_at else "—"


def render_state_summary(
    user_id: int, pending_prefix: str = "Есть незавершённая заявка"
) -> dict[str, str]:
    state, user = get_user_state(user_id)
    expires_at, exp = render_user_expiry_value(user)
    time_left = format_time_left(expires_at)
    plan = render_user_plan_value(user)
    pending_hint = render_pending_hint(user_id, prefix=pending_prefix)

    if state == "new":
        return {
            "state": state,
            "headline": "Подписки нет",
            "plan": "—",
            "expiry": "—",
            "time_left": "—",
            "next_step": f"Жми «{TRIAL_CTA_TEXT}».",
            "pending_hint": pending_hint,
        }
    if state == "expired":
        return {
            "state": state,
            "headline": "Подписка не активна",
            "plan": plan,
            "expiry": exp,
            "time_left": "истекло",
            "next_step": "Жми «Купить подписку».",
            "pending_hint": pending_hint,
        }
    if state == "trial_active":
        return {
            "state": state,
            "headline": "Тест активен",
            "plan": plan,
            "expiry": exp,
            "time_left": time_left,
            "next_step": "Жми «Подключить».",
            "pending_hint": pending_hint,
        }
    return {
        "state": state,
        "headline": "Подписка активна",
        "plan": plan,
        "expiry": exp,
        "time_left": time_left,
        "next_step": "Жми «Подключить».",
        "pending_hint": pending_hint,
    }


def render_plan_offer_lines() -> list[str]:
    base_monthly = PLANS["basic_1m"]["amount"]
    lines: list[str] = []
    for pk in PLANS:
        p = PLANS[pk]
        dev = p.get("devices", DEVICE_LIMITS.get(pk, 1))
        per_month = round(p["amount"] / (p["days"] / 30))
        save_pct = round((1 - per_month / base_monthly) * 100) if per_month < base_monthly else 0
        save_tag = f" (-{save_pct}%)" if save_pct > 0 else ""
        lines.append(f"  {p['label']} — {p['amount']}₽ • {per_month}₽/мес{save_tag} • {dev} устр.")
    return lines


def render_payment_provider_intro(provider: str) -> list[str]:
    if provider == "yoomoney":
        return [
            "Жми на тариф — откроется оплата.",
            "Карта, SberPay или кошелёк YooMoney.",
            "Подписка включится автоматически.",
        ]
    if provider in {"yookassa", "cardlink"}:
        return [
            "Жми на тариф — откроется оплата.",
            "Подписка включится автоматически.",
        ]
    return [
        "Выбери тариф. Если нужна помощь — /repair.",
    ]


def render_post_config_text(has_fallback: bool) -> str:
    return (
        "Готово! QR и txt-файл выше.\n\n"
        "Отсканируй QR или открой txt в приложении.\n"
        "Если был старый профиль — сначала удали его.\n\n"
        "Не получается? Жми «Диагностика» или /guide."
    )


def render_device_config_sent_text(device: dict, has_fallback: bool, locked: bool) -> str:
    lines = [
        device["device_name"],
        "",
        render_post_config_text(has_fallback),
    ]
    if locked:
        lines.extend(
            [
                "",
                "Этот слот уже привязан.",
                "Для переноса на другой телефон или ПК жми «Заменить устройство».",
            ]
        )
    return "\n".join(lines)


def render_config_delivery_intro(expires_at: datetime | None, has_fallback: bool) -> str:
    exp = expires_at.strftime("%d.%m.%Y %H:%M") if expires_at else "—"
    return (
        f"{BOT_BRAND}\n\n"
        f"Доступ до {exp}.\n\n"
        "Ниже QR-код и txt-файл.\n"
        "Открой любой из них в Hiddify, v2rayNG или другом приложении.\n"
        "Не знаешь какое скачать? Жми /guide"
    )


def render_inactive_subscription_text(user_id: int | None = None) -> str:
    lines = [
        f"{BOT_BRAND}",
        "",
        "Сейчас подписка не активна.",
        "Жми /trial или /buy.",
    ]
    if user_id is not None:
        lines.extend(["", f"Твой ID: {user_id}"])
    return "\n".join(lines)


def render_support_escalation_text(user: dict | None, user_id: int) -> str:
    if not user:
        return render_inactive_subscription_text(user_id=user_id)
    expires_at = parse_expires_at(user.get("expires_at"))
    exp = expires_at.strftime("%d.%m.%Y %H:%M") if expires_at else "—"
    contact_line = (
        f"Напиши @{SUPPORT_USERNAME} — отправь свой ID."
        if SUPPORT_USERNAME
        else "Отправь админу свой ID."
    )
    return (
        f"{BOT_BRAND}\n\n"
        "Нужна помощь админа.\n\n"
        f"Твой ID: {user_id}\n"
        f"Тариф: {render_user_plan_value(user)}\n"
        f"До: {exp}\n\n"
        f"{contact_line}"
    )


def render_device_replace_result(old_device: dict, replacement: dict) -> str:
    return (
        f"{BOT_BRAND}\n\n"
        f"Устройство «{old_device['device_name']}» заменено.\n"
        f"Новый слот: {replacement['device_name']}.\n"
        "Старый профиль отключён. Используй новый только на новом устройстве."
    )


def render_account_text(user_id: int) -> str:
    state, user = get_user_state(user_id)
    devices = list_user_devices(user_id) if state != "new" else []
    device_limit = get_device_limit(user)
    referral = get_referral_summary(user_id)
    recent_rewards = get_recent_referral_rewards(user_id, limit=3)
    summary = render_state_summary(user_id)
    pending_hint = summary["pending_hint"]
    extra_slots = get_extra_device_slots_value(user, user_id)

    if not user:
        return (
            f"{BOT_BRAND}\n\n"
            "Личный кабинет\n\n"
            f"ID: {user_id}\n"
            "Устройств: 0/1\n"
            f"{summary['headline']}\n\n"
            f"Приглашено: {referral['opens']} | оплатили: {referral['paid']}\n"
            f"Бонус: +{referral['bonus_days']} дней\n\n"
            f"{summary['next_step']}"
            f"{pending_hint}"
        )

    if state == "expired":
        return (
            f"{BOT_BRAND}\n\n"
            "Личный кабинет\n\n"
            f"ID: {user_id}\n"
            f"Тариф: {summary['plan']}\n"
            f"Истекла: {summary['expiry']}\n"
            f"Устройств: {len(devices)}/{device_limit}\n\n"
            f"Приглашено: {referral['opens']} | оплатили: {referral['paid']}\n"
            f"Бонус: +{referral['bonus_days']} дней\n\n"
            f"{summary['next_step']}"
            f"{pending_hint}"
        )

    hint = "Получи профиль или продли подписку."
    if state == "trial_active":
        hint = "Проверь подключение. Работает — оформи подписку."
    elif summary["time_left"] != "неизвестно":
        expires_at, _ = render_user_expiry_value(user)
        if expires_at and (expires_at - datetime.now()).days < 3:
            hint = "Скоро истекает. Продли заранее."

    lines = [
        f"{BOT_BRAND}",
        "",
        "Личный кабинет",
        "",
        f"ID: {user_id}",
        f"Тариф: {summary['plan']}",
        f"До: {summary['expiry']}",
        f"Осталось: {summary['time_left']}",
        f"Устройств: {len(devices)}/{device_limit}",
        f"Сервер: {VPN_SERVER}:{VPN_PORT}",
    ]
    if extra_slots > 0:
        lines.append(f"Докуплено слотов: +{extra_slots}")
    lines.extend(
        [
            "",
            f"Приглашено: {referral['opens']} | оплатили: {referral['paid']}",
            f"Бонус: +{referral['bonus_days']} дней",
        ]
    )
    if recent_rewards:
        lines.append("")
        for reward in recent_rewards:
            paid_at = (reward.get("paid_at") or "")[:16].replace("T", " ")
            lines.append(f"  +7 дней от user {reward['referred_user_id']} • {paid_at}")
    lines.extend(["", hint])
    if pending_hint:
        lines.append(pending_hint.strip())
    return "\n".join(lines)


def render_help_text() -> str:
    return (
        f"{BOT_BRAND}\n\n"
        "Быстрый путь:\n"
        f"1. Жми «{TRIAL_CTA_TEXT}» или «Купить подписку»\n"
        "2. Потом жми «Подключить»\n"
        "3. Импортируй QR или ссылку в приложение\n\n"
        "Основные разделы:\n"
        "- «Подключить» — ссылка и QR\n"
        "- «Кабинет» — устройства, оплаты и срок\n"
        "- «Помощь» — если не получается подключиться\n\n"
        "Основные команды:\n"
        "/start /config /buy /status /repair /guide /help"
    )


def render_guide_intro() -> str:
    return (
        f"{BOT_BRAND}\n\n"
        "Как подключиться\n\n"
        "1. Установи приложение\n"
        "2. Нажми «Подключить»\n"
        "3. Импортируй QR или ссылку\n"
        "4. Включи профиль\n\n"
        "Выбери платформу — покажу короткий путь без лишнего."
    )


def render_guide_text(platform: str) -> str:
    if platform == "android":
        return (
            f"{BOT_BRAND}\n\n"
            "Android\n\n"
            "Лучше всего: Hiddify.\n"
            "Если уже стоит v2rayNG, тоже подойдёт.\n\n"
            "1. Установи приложение по кнопке ниже\n"
            "2. В боте нажми «Подключить»\n"
            "3. Импортируй QR или ссылку\n"
            "4. Включи профиль и режим VPN / TUN для всех приложений\n"
            "5. Не включай split tunneling для Google, Gemini и Chrome\n\n"
            "Для Gemini / Google app важен именно полный VPN, а не выборочный прокси.\n\n"
            "Не работает? Жми /repair"
        )
    if platform == "windows":
        return (
            f"{BOT_BRAND}\n\n"
            "Windows\n\n"
            "Лучше всего: Hiddify или v2rayN.\n\n"
            "1. Установи приложение по кнопке ниже\n"
            "2. В боте нажми «Подключить»\n"
            "3. Импортируй QR или ссылку\n"
            "4. Включи профиль\n\n"
            "Не работает? Жми /repair"
        )
    if platform == "linux":
        return (
            f"{BOT_BRAND}\n\n"
            "Linux\n\n"
            "Лучше всего: Hiddify.\n"
            "Если нужен desktop-клиент, подойдёт NekoRay.\n\n"
            "1. Установи приложение по кнопке ниже\n"
            "2. В боте нажми «Подключить»\n"
            "3. Импортируй QR или ссылку\n"
            "4. Включи профиль\n\n"
            "Для терминала можно использовать /json.\n"
            "Не работает? Жми /repair"
        )
    if platform == "iphone":
        return (
            f"{BOT_BRAND}\n\n"
            "iPhone / iPad\n\n"
            "Лучше всего: Happ или Streisand.\n"
            "Если уже есть Shadowrocket, тоже подойдёт.\n\n"
            "1. Установи приложение по кнопке ниже\n"
            "2. В боте нажми «Подключить»\n"
            "3. Импортируй QR или ссылку\n"
            "4. Разреши добавить конфигурацию\n"
            "5. Включи профиль как полный VPN\n\n"
            "Для Gemini / Google app не используй split tunneling и локальные bypass-списки.\n\n"
            "Если клиент не принимает файл, используй QR или саму ссылку.\n"
            "Не работает? Жми /repair"
        )
    if platform == "mac":
        return (
            f"{BOT_BRAND}\n\n"
            "Mac\n\n"
            "Лучше всего: Hiddify.\n\n"
            "1. Установи приложение по кнопке ниже\n"
            "2. В боте нажми «Подключить»\n"
            "3. Импортируй QR или ссылку\n"
            "4. Включи профиль\n\n"
            "Не работает? Жми /repair"
        )
    return (
        f"{BOT_BRAND}\n\n"
        "Подключение по QR\n\n"
        "Подойдёт любой совместимый клиент.\n\n"
        "1. Установи приложение по кнопкам ниже\n"
        "2. Нажми «Подключить»\n"
        "3. Отсканируй QR или вставь ссылку\n"
        "4. Если старый профиль мешает, удали его\n\n"
        "Не работает? Жми /repair"
    )


def build_invite_link(user_id: int) -> str:
    return f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"


def render_invite_text(user_id: int) -> str:
    invite_link = build_invite_link(user_id)
    summary = get_referral_summary(user_id)
    recent_rewards = get_recent_referral_rewards(user_id, limit=5)
    remaining_bonus_days = (
        max(REFERRAL_BONUS_CAP_DAYS - int(summary["bonus_days"]), 0)
        if REFERRAL_BONUS_CAP_DAYS
        else 0
    )
    lines = [
        f"{BOT_BRAND}",
        "",
        "Пригласи друга — получай бонусные дни",
        "",
        "Твоя ссылка:",
        f"{invite_link}",
        "",
        "Сценарий:",
        "1. Друг открывает бота по ссылке",
        f"2. Если берёт {TRIAL_DAYS_TEXT.lower()} — тебе +{REFERRAL_TRIAL_BONUS_DAYS} день",
        f"3. После первой оплаты тебе ещё +{REFERRAL_BONUS_DAYS} дней",
    ]
    if summary["opens"] > 0 or summary["trial"] > 0 or summary["paid"] > 0:
        lines.extend(
            [
                "",
                f"Переходов: {summary['opens']}",
                f"Взяли тест: {summary['trial']}",
                f"Оплатили: {summary['paid']}",
                f"Заработано: +{summary['bonus_days']} дней",
            ]
        )
        if REFERRAL_BONUS_CAP_DAYS:
            lines.append(f"До лимита осталось: {remaining_bonus_days} дней")
    if recent_rewards:
        lines.append("")
        for reward in recent_rewards:
            paid_at = (reward.get("paid_at") or "")[:16].replace("T", " ")
            lines.append(f"  +7 дней от user {reward['referred_user_id']} • {paid_at}")
    return "\n".join(lines)


def render_rewards_text(user_id: int) -> str:
    summary = get_referral_summary(user_id)
    recent_rewards = get_recent_referral_rewards(user_id, limit=10)
    remaining_bonus_days = (
        max(REFERRAL_BONUS_CAP_DAYS - int(summary["bonus_days"]), 0)
        if REFERRAL_BONUS_CAP_DAYS
        else 0
    )
    lines = [
        f"{BOT_BRAND}",
        "",
        "Бонусы",
        "",
        f"Накоплено: +{summary['bonus_days']} дней",
        f"Переходов по ссылке: {summary['opens']}",
        f"Взяли тест: {summary['trial']}",
        f"Друзей оплатили: {summary['paid']}",
        "",
        f"За тест: +{REFERRAL_TRIAL_BONUS_DAYS} день • за оплату: +{REFERRAL_BONUS_DAYS} дней (макс. {REFERRAL_BONUS_CAP_DAYS}).",
    ]
    if REFERRAL_BONUS_CAP_DAYS:
        lines.append(f"До лимита осталось: {remaining_bonus_days} дней")
    if recent_rewards:
        lines.append("")
        for reward in recent_rewards:
            paid_at = (reward.get("paid_at") or "")[:16].replace("T", " ")
            amount = reward.get("first_payment_amount") or 0
            currency = reward.get("first_payment_currency") or "RUB"
            lines.append(f"  +7 дней • {amount:.0f} {currency} • {paid_at}")
    else:
        lines.extend(["", "Начислений пока нет."])
    lines.extend(["", "Пригласи друга через /invite"])
    return "\n".join(lines)


def render_top_referrers_block(limit: int = 5) -> str:
    leaders = get_top_referrers(limit=limit)
    if not leaders:
        return "Топ рефереров: пока нет данных"

    lines = ["Топ рефереров:"]
    for index, leader in enumerate(leaders, 1):
        display_name = (
            f"@{leader['referrer_username']}"
            if leader.get("referrer_username")
            else f"user {leader['referrer_user_id']}"
        )
        lines.append(
            f"{index}. {display_name} • paid {int(leader['paid'] or 0)} • opens {int(leader['opens'] or 0)} • {float(leader['revenue'] or 0):.0f} ₽"
        )
    return "\n".join(lines)


def render_recent_referrals_block(limit: int = 5) -> str:
    items = get_recent_referrals(limit=limit)
    if not items:
        return "Последние рефералы: пока нет данных"

    lines = ["Последние рефералы:"]
    for item in items:
        referrer = (
            f"@{item['referrer_username']}"
            if item.get("referrer_username")
            else f"user {item['referrer_user_id']}"
        )
        referred = (
            f"@{item['referred_username']}"
            if item.get("referred_username")
            else f"user {item['referred_user_id']}"
        )
        if item.get("paid_at"):
            when = str(item.get("paid_at") or "")[:16].replace("T", " ")
            amount = float(item.get("first_payment_amount") or 0)
            currency = item.get("first_payment_currency") or "RUB"
            status = f"paid • {amount:.0f} {currency}"
        elif item.get("trial_bonus_awarded_at"):
            when = str(item.get("trial_bonus_awarded_at") or "")[:16].replace("T", " ")
            status = f"trial • +{REFERRAL_TRIAL_BONUS_DAYS}д"
        else:
            when = str(item.get("opened_at") or "")[:16].replace("T", " ")
            status = "opened"
        lines.append(f"- {referrer} → {referred} • {status} • {when}")
    return "\n".join(lines)


def render_payment_status_block() -> str:
    summary = get_payment_status_summary()
    quality_24h = get_payment_queue_quality_24h()
    quality_prev_24h = get_payment_queue_quality_prev_24h()
    pending_older_1h = int(summary.get("pending_older_1h", 0) or 0)
    created_24h = int(quality_24h.get("created", 0) or 0)
    breached_1h_24h = int(quality_24h.get("reminded_1h", 0) or 0)
    auto_approved_24h = int(quality_24h.get("auto_approved", 0) or 0)
    manual_approved_24h = int(quality_24h.get("manual_approved", 0) or 0)
    total_approved_24h = auto_approved_24h + manual_approved_24h
    sla_under_1h_24h = 100.0
    if created_24h:
        sla_under_1h_24h = max(0.0, ((created_24h - breached_1h_24h) / created_24h) * 100.0)
    automation_ratio_24h = 0.0
    if total_approved_24h:
        automation_ratio_24h = (auto_approved_24h / total_approved_24h) * 100.0
    created_prev_24h = int(quality_prev_24h.get("created", 0) or 0)
    breached_1h_prev_24h = int(quality_prev_24h.get("reminded_1h", 0) or 0)
    auto_approved_prev_24h = int(quality_prev_24h.get("auto_approved", 0) or 0)
    manual_approved_prev_24h = int(quality_prev_24h.get("manual_approved", 0) or 0)
    total_approved_prev_24h = auto_approved_prev_24h + manual_approved_prev_24h
    sla_under_1h_prev_24h = 100.0
    if created_prev_24h:
        sla_under_1h_prev_24h = max(
            0.0, ((created_prev_24h - breached_1h_prev_24h) / created_prev_24h) * 100.0
        )
    automation_ratio_prev_24h = 0.0
    if total_approved_prev_24h:
        automation_ratio_prev_24h = (auto_approved_prev_24h / total_approved_prev_24h) * 100.0
    sla_delta = sla_under_1h_24h - sla_under_1h_prev_24h
    automation_delta = automation_ratio_24h - automation_ratio_prev_24h
    payment_verdict = "healthy"
    payment_verdict_reason = "очередь под контролем"
    if pending_older_1h >= PAYMENT_QUEUE_ALERT_THRESHOLD and (
        sla_delta < 0 or automation_delta < 0
    ):
        payment_verdict = "critical"
        payment_verdict_reason = "есть зависший хвост >1ч и метрики ухудшаются"
    elif pending_older_1h >= PAYMENT_QUEUE_ALERT_THRESHOLD or sla_delta < 0 or automation_delta < 0:
        payment_verdict = "warning"
        if pending_older_1h >= PAYMENT_QUEUE_ALERT_THRESHOLD:
            payment_verdict_reason = "есть pending-хвост >1ч"
        elif sla_delta < 0:
            payment_verdict_reason = "просел SLA <1ч"
        else:
            payment_verdict_reason = "просела доля авто-подтверждений"
    lines = ["Платежи:"]
    for status, label in (
        ("pending", "pending queue"),
        ("approved", "claims approved"),
        ("rejected", "claims rejected"),
        ("completed", "revenue booked"),
        ("expired", "claims expired"),
    ):
        item = summary.get(status, {"count": 0, "total": 0.0})
        lines.append(f"- {label}: {item['count']} • {item['total']:.0f} ₽")
    lines.append(f"- pending >10м: {summary.get('pending_older_10m', 0)}")
    lines.append(f"- reminded 10м: {summary.get('pending_reminded_10m', 0)}")
    lines.append(f"- pending >1ч: {summary.get('pending_older_1h', 0)}")
    lines.append(f"- reminded 1ч: {summary.get('pending_reminded_1h', 0)}")
    lines.extend(
        [
            "",
            "Queue quality 24ч:",
            f"- created: {created_24h}",
            f"- reminders 10м: {quality_24h.get('reminded_10m', 0)}",
            f"- reminders 1ч: {quality_24h.get('reminded_1h', 0)}",
            f"- expired: {quality_24h.get('expired', 0)}",
            f"- approved: {quality_24h.get('approved', 0)}",
            f"- approved auto: {auto_approved_24h}",
            f"- approved manual: {manual_approved_24h}",
            f"- approved after 1ч: {quality_24h.get('delayed_approved', 0)}",
            f"- SLA <1ч: {sla_under_1h_24h:.0f}%",
            f"- automation ratio: {automation_ratio_24h:.0f}%",
            "",
            "Trend vs prev 24ч:",
            f"- SLA delta: {sla_delta:+.0f} п.п.",
            f"- automation delta: {automation_delta:+.0f} п.п.",
            "",
            f"Verdict: {payment_verdict}",
            f"Reason: {payment_verdict_reason}",
        ]
    )
    return "\n".join(lines)


def render_rate_limit_block() -> str:
    stats = get_rate_limit_stats()
    if not stats["total"]:
        return "Rate-limit срабатываний: 0"

    lines = [f"Rate-limit срабатываний: {stats['total']}"]
    if stats["top_actions"]:
        lines.append("Самые шумные действия:")
        for item in stats["top_actions"]:
            lines.append(f"- {item['action_name']}: {item['hits']}")
    return "\n".join(lines)


def render_subscription_rate_limit_block(limit: int = 5, window_hours: int = 24) -> str:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM activity_log
            WHERE action = 'subscription_rate_limited'
              AND timestamp >= datetime('now', ?)
            """,
            (f"-{int(window_hours)} hours",),
        )
        total_row = cursor.fetchone()
        total = int((total_row["cnt"] if total_row else 0) or 0)
        if total <= 0:
            return "Лимит подписки (/sub): 0"

        cursor.execute(
            """
            SELECT
                al.user_id,
                u.username,
                COUNT(*) AS hits,
                MAX(al.timestamp) AS last_seen
            FROM activity_log al
            LEFT JOIN users u ON u.user_id = al.user_id
            WHERE al.action = 'subscription_rate_limited'
              AND al.timestamp >= datetime('now', ?)
            GROUP BY al.user_id, u.username
            ORDER BY hits DESC, last_seen DESC
            LIMIT ?
            """,
            (f"-{int(window_hours)} hours", int(limit)),
        )
        rows = cursor.fetchall()

    lines = [f"Лимит подписки (/sub): {total} за {window_hours}ч"]
    if rows:
        lines.append("Последние срабатывания:")
        for row in rows:
            username = f"@{row['username']}" if row["username"] else "—"
            lines.append(
                f"- {row['user_id']} • {username} • {row['hits']} • {row['last_seen'] or '—'}"
            )
    return "\n".join(lines)


def render_noisy_users_block(limit: int = 5) -> str:
    users = get_top_rate_limited_users(limit=limit)
    if not users:
        return "Шумные user_id: пока нет данных"

    lines = ["Шумные user_id:"]
    for item in users:
        display_name = f"@{item['username']}" if item.get("username") else f"user {item['user_id']}"
        lines.append(f"- {display_name}: {item['hits']}")
    return "\n".join(lines)


def render_suspicious_users_block(limit: int = 5) -> str:
    users = get_suspicious_users(limit=limit, threshold=SUSPICIOUS_RATE_LIMIT_THRESHOLD)
    if not users:
        return "Подозрительные user_id: пока нет данных"

    lines = [f"Подозрительные user_id (порог {SUSPICIOUS_RATE_LIMIT_THRESHOLD}/24ч):"]
    for item in users:
        display_name = f"@{item['username']}" if item.get("username") else f"user {item['user_id']}"
        lines.append(f"- {display_name}: {item['hits']}")
    return "\n".join(lines)


def render_buy_text(user_id: int | None = None) -> str:
    state = "new"
    user = None
    recommended_key = "basic_1m"
    latest_pending = None
    payment_provider = get_active_payment_provider()
    if user_id is not None:
        state, user = get_user_state(user_id)
        recommended_key = get_recommended_plan_key(user_id)
        latest_pending = get_latest_pending_payment(user_id)
    recommended_plan = PLANS[recommended_key]
    lines = [
        f"{BOT_BRAND}",
        "",
        "Тарифы",
        "",
    ]
    lines.extend(render_plan_offer_lines())
    lines.append("")
    lines.extend(render_payment_provider_intro(payment_provider))
    if state == "trial_active" and user:
        expires_at = parse_expires_at(user.get("expires_at"))
        if expires_at:
            lines.append(
                f"\nТест до {expires_at.strftime('%d.%m.%Y')}. Оформи подписку, чтобы не потерять доступ."
            )
    elif state == "paid_active" and user:
        expires_at = parse_expires_at(user.get("expires_at"))
        if expires_at:
            lines.append(
                f"\nПодписка до {expires_at.strftime('%d.%m.%Y')}. При продлении дни прибавятся."
            )
    elif state == "expired":
        lines.append("\nПодписка истекла. Выбери тариф — доступ включится сразу.")
    if latest_pending:
        lines.extend(
            [
                "",
                f"Незавершённая заявка: #{latest_pending['payment_id']}.",
                "Можешь продолжить её.",
            ]
        )
    return "\n".join(lines)


def render_buy_waiting_text(user_id: int) -> str:
    return (
        f"{BOT_BRAND}\n\n"
        "Выбери оплаченный тариф.\n"
        "Я создам заявку на проверку.\n\n"
        f"Твой ID: {user_id}\n\n"
        "После подтверждения жми «Подключить»."
    )


def render_user_payments_text(user_id: int) -> str:
    payments = get_recent_payments_for_user(user_id, limit=8)
    lines = [
        f"{BOT_BRAND}",
        "",
        "Мои заявки и оплаты",
        "",
        f"Telegram ID: {user_id}",
    ]
    if not payments:
        lines.extend(
            [
                "Пока пусто.",
                "",
                "Открой «Купить подписку», оплати тариф и вернись сюда.",
            ]
        )
        return "\n".join(lines)

    latest_status = None
    lines.append("")
    for payment in payments:
        amount = f"{payment.get('amount', 0):.0f}"
        status = payment.get("payment_status") or "unknown"
        status_label = render_user_payment_status(status)
        latest_status = latest_status or status
        plan_key = parse_payment_purchase_key(payment) or "manual"
        plan_label = render_purchase_label(plan_key)
        created_at = str(payment.get("payment_date") or "—")[:16]
        lines.append(
            f"- #{payment['payment_id']} • {amount} {payment.get('currency') or 'RUB'} • "
            f"{plan_label} • {status_label} • {created_at}"
        )

    pending_count = sum(
        1 for payment in payments if (payment.get("payment_status") or "") == "pending"
    )
    lines.append("")
    if pending_count:
        lines.append(f"Ждут проверки: {pending_count}")
    lines.append(render_payment_next_step("pending" if pending_count else latest_status))
    return "\n".join(lines)


def render_user_payment_detail_text(payment: dict, remote_payment: dict | None = None) -> str:
    amount = f"{payment.get('amount', 0):.0f}"
    status = payment.get("payment_status") or "unknown"
    status_label = render_user_payment_status(status)
    plan_key = parse_payment_purchase_key(payment) or "manual"
    plan_label = render_purchase_label(plan_key)
    provider = payment.get("payment_provider") or "—"
    provider_label = render_user_payment_provider(provider)
    created_at = str(payment.get("payment_date") or "—")[:16]
    lines = [
        f"{BOT_BRAND}",
        "",
        f"Заявка #{payment['payment_id']}",
        "",
        f"Покупка: {plan_label}",
        f"Сумма: {amount} {payment.get('currency') or 'RUB'}",
        f"Статус: {status_label}",
        f"Провайдер: {provider_label}",
        f"Создано: {created_at}",
    ]
    if remote_payment:
        remote_status = remote_payment.get("status") or "unknown"
        lines.append(f"Статус у провайдера: {remote_status}")
    lines.append("")
    if status == "pending":
        lines.append("Нажми «Оплатить» или «Обновить статус».")
    else:
        lines.append(render_payment_next_step(status))
    return "\n".join(lines)


async def send_user_payment_detail(message: Message, user_id: int, payment: dict) -> None:
    remote_payment = None
    confirmation_url = None
    if parse_yookassa_payment_id(payment):
        try:
            remote_payment = fetch_yookassa_payment(parse_yookassa_payment_id(payment))
            confirmation_url = (
                (remote_payment.get("confirmation") or {}).get("confirmation_url")
            ) or None
        except Exception as exc:
            logger.warning(
                "failed to fetch yookassa payment detail payment_id=%s: %s",
                payment.get("payment_id"),
                exc,
            )
    elif get_payment_provider_family(payment) == "yoomoney":
        plan_key = parse_payment_purchase_key(payment)
        if plan_key:
            try:
                confirmation_url = create_yoomoney_url(
                    int(float(payment.get("amount") or 0)), user_id, plan_key
                )
            except Exception as exc:
                logger.warning(
                    "failed to build yoomoney detail url payment_id=%s: %s",
                    payment.get("payment_id"),
                    exc,
                )
    await message.answer(
        render_user_payment_detail_text(payment, remote_payment=remote_payment),
        reply_markup=build_user_payment_detail_menu(payment, user_id, confirmation_url),
    )


def render_admin_usage() -> str:
    return (
        "Админ-команды:\n"
        "/activate <user_id> <plan>\n"
        "/admin_user <user_id>\n\n"
        "Примеры:\n"
        "/activate 2018432227 basic_12m\n"
        "/activate 2018432227 - basic_12m\n\n"
        "Планы:\n"
        "basic_1m, basic_3m, basic_6m, basic_12m"
    )


def render_admin_help_text() -> str:
    return (
        f"{BOT_BRAND} — оператор\n\n"
        "Быстрый вход:\n"
        "/admin - открыть операторское меню\n\n"
        "Основные команды:\n"
        "/stats - сводка по пользователям, рефералам и anti-abuse\n"
        "/stats_abuse - отдельная anti-abuse сводка\n"
        "/admin_user <user_id> - открыть карточку пользователя\n"
        "/activate <user_id> <plan_key> - активировать или продлить подписку\n"
        "Кнопка «Выпустить без Telegram» - выдать ссылку и claim-код без user_id\n"
        "/broadcast [аудитория] текст - рассылка (all/active/paid/trial/expired)\n"
        "/promo - управление промокодами\n"
        "/refund <payment_id> [причина] - возврат средств\n"
        "/revenue - доходы, churn, LTV\n"
        "/whoami - показать свой Telegram ID\n"
        "/invite - открыть свою ссылку приглашения\n\n"
        "Операционный минимум:\n"
        "1. Проверить /stats\n"
        "2. Если Telegram уже есть — активировать пользователя через /activate\n"
        "3. Если Telegram ещё нет — выпустить offline-подписку кнопкой в меню\n"
        "4. Попросить пользователя открыть /config или /start OFFLINE-XXXXXX после привязки\n\n"
        "Документация:\n"
        "- docs/vpn/BOT_OPERATOR_RUNBOOK.md\n"
        "- docs/vpn/BOT_RUNTIME_SETTINGS.md"
    )


def render_admin_panel_text() -> str:
    return (
        f"{BOT_BRAND} — оператор\n\n"
        "Быстрые действия:\n"
        "- Общая сводка\n"
        "- Anti-Abuse сводка\n"
        "- Платежи на проверке\n"
        "- Обработанные заявки\n"
        "- Карточка пользователя по user_id\n"
        "- Выпуск подписки без Telegram\n"
        "- Памятка по ручным операциям\n\n"
        "Используй кнопки ниже."
    )


def render_admin_user_lookup_text() -> str:
    return (
        f"{BOT_BRAND} — оператор\n\n"
        "Отправь user_id одним сообщением.\n\n"
        "Я открою карточку пользователя и покажу кнопки продления.\n\n"
        "Пример:\n"
        "2018432227"
    )


def render_admin_offline_issue_text() -> str:
    return (
        f"{BOT_BRAND} — выпуск без Telegram\n\n"
        f"Выбери тариф ниже. Триал тоже можно выпустить: {TRIAL_CTA_TEXT.lower()}.\n\n"
        "Бот сразу создаст offline-подписку, зарегистрирует клиента в xray и пришлёт:\n"
        "• subscription URL\n"
        "• основной профиль 443\n"
        "• claim-код для будущей привязки к Telegram\n\n"
        "Клиенту сейчас можно отправить только ссылку.\n"
        "Когда появится Telegram — он откроет бота и отправит:\n"
        " /start OFFLINE-XXXXXX"
    )


def render_admin_offline_issued_text(subscription: dict[str, object]) -> str:
    claim_code = str(subscription["claim_code"])
    plan_label = render_plan_label(str(subscription["plan_key"]))
    expires_at = subscription.get("expires_at")
    expiry_text = (
        expires_at.strftime("%d.%m.%Y %H:%M")
        if isinstance(expires_at, datetime)
        else "—"
    )
    subscription_url = html.escape(str(subscription["subscription_url"]))
    main_link = html.escape(str(subscription["main_link"]))
    fallback_link = html.escape(str(subscription.get("fallback_link") or ""))
    lines = [
        f"{BOT_BRAND} — offline-подписка выпущена",
        "",
        f"Тариф: {plan_label}",
        f"Доступ до: {expiry_text}",
        f"Claim-код: <code>{html.escape(claim_code)}</code>",
        "",
        "Отправь клиенту подписку:",
        f"<code>{subscription_url}</code>",
    ]
    if main_link:
        lines.extend(
            [
                "",
                "Если импорт подписки у клиента не сработает, можно выдать прямой профиль вручную:",
                f"<code>{main_link}</code>",
            ]
        )
    if fallback_link:
        lines.extend(["", "Операторский резервный профиль:", f"<code>{fallback_link}</code>"])
    lines.extend(
        [
            "",
            "Если клиент позже поставит Telegram, пусть отправит боту:",
            f"<code>/start {html.escape(claim_code)}</code>",
        ]
    )
    return "\n".join(lines)


def render_admin_users_text(admin_user_id: int, limit: int = 20) -> str:
    state = ADMIN_USER_BROWSER_STATE.get(admin_user_id, {})
    status = state.get("status", "all")
    search = state.get("search", "")
    offset = int(state.get("offset", "0"))
    page_size = int(state.get("page_size", str(ADMIN_USERS_PAGE_SIZE)))
    users = get_recent_users(limit=page_size + 1, status=status, search=search, offset=offset)
    page_rows = users[:page_size]
    page_number = (offset // page_size) + 1
    lines = [
        f"{BOT_BRAND} — пользователи",
        "",
        "Последние и активные пользователи:",
        "",
    ]
    if status != "all":
        lines.append(f"Фильтр: {status}")
    if search:
        lines.append(f"Поиск: {search}")
    if status != "all" or search:
        lines.append("")
    lines.append(f"Страница: {page_number}")
    lines.append("")
    if not page_rows:
        lines.append("Ничего не найдено.")
        return "\n".join(lines)
    for user in page_rows:
        username = f"@{user['username']}" if user.get("username") else "—"
        plan = render_plan_label(user.get("plan") or "") if user.get("plan") else "—"
        expires_at = parse_expires_at(user.get("expires_at"))
        exp = expires_at.strftime("%d.%m %H:%M") if expires_at else "—"
        status = "active" if user.get("is_active") else "expired"
        lines.append(f"{user['user_id']} • {username} • {plan} • {status} • до {exp}")
    lines.extend(["", "Жми на пользователя ниже."])
    return "\n".join(lines)


def parse_activate_args(raw_args: str | None) -> tuple[int | None, str | None]:
    parts = [part for part in (raw_args or "").split() if part != "-"]
    if len(parts) < 2:
        return None, None
    user_raw, plan_key = parts[0], parts[1]
    if not user_raw.isdigit():
        return None, plan_key
    return int(user_raw), plan_key


def render_admin_user_text(target_user_id: int) -> str:
    user = get_user(target_user_id)
    devices = get_user_devices(target_user_id)
    active_devices = [device for device in devices if device.get("status") == "active"]
    if not user:
        return (
            f"{BOT_BRAND} — пользователь\n\n"
            f"user_id: {target_user_id}\n"
            "Запись в базе не найдена.\n\n"
            "Можно сразу активировать платный план кнопками ниже."
        )

    expires_at = parse_expires_at(user.get("expires_at"))
    username = user.get("username") or "—"
    lines = [
        f"{BOT_BRAND} — пользователь",
        "",
        f"user_id: {target_user_id}",
        f"username: @{username}" if username != "—" else "username: —",
        f"план: {user.get('plan') or '—'}",
        f"trial_used: {'да' if user.get('trial_used') else 'нет'}",
        f"активно до: {expires_at.strftime('%d.%m.%Y %H:%M') if expires_at else '—'}",
        f"устройств active: {len(active_devices)}",
        f"delivery_profile: {render_delivery_profile_label(resolve_delivery_profile(user))}",
        f"entry_node: {resolve_entry_node(user)}",
        f"client_family: {resolve_client_family(user)}",
    ]
    if user.get("vpn_uuid"):
        lines.append(f"vpn_uuid: {user['vpn_uuid']}")
    lines.append(f"connect_url: {build_delivery_connect_url(user)}")
    return "\n".join(lines)


def render_admin_activation_text(target_user_id: int) -> str:
    user = get_user(target_user_id)
    if not user:
        return (
            f"{BOT_BRAND} — активация\n\n"
            f"user_id: {target_user_id}\n"
            "Пользователь в базе ещё не создан.\n\n"
            "Выбери тариф ниже. Бот создаст запись и сразу активирует план."
        )

    expires_at = parse_expires_at(user.get("expires_at"))
    username = user.get("username") or "—"
    username_line = f"username: @{username}" if username != "—" else "username: —"
    return (
        f"{BOT_BRAND} — активация\n\n"
        f"user_id: {target_user_id}\n"
        f"{username_line}\n"
        f"план: {render_plan_label(user.get('plan') or '') if user.get('plan') else '—'}\n"
        f"активно до: {expires_at.strftime('%d.%m.%Y %H:%M') if expires_at else '—'}\n\n"
        "Выбери тариф для активации или продления."
    )


def render_admin_user_devices_text(target_user_id: int) -> str:
    user = get_user(target_user_id)
    devices = get_user_devices(target_user_id)
    lines = [
        f"{BOT_BRAND} — устройства пользователя",
        "",
        f"user_id: {target_user_id}",
        f"username: @{user.get('username')}" if user and user.get("username") else "username: —",
    ]
    if not devices:
        lines.extend(["", "Устройств пока нет."])
        return "\n".join(lines)
    lines.append("")
    for device in devices:
        created_at = device.get("created_at") or "—"
        lines.append(
            f"- #{device['device_id']} {device['device_name']} | {device.get('status', 'unknown')} | создано {created_at}"
        )
    return "\n".join(lines)


def render_admin_user_device_text(target_user_id: int, device: dict) -> str:
    return (
        f"{BOT_BRAND} — устройство\n\n"
        f"user_id: {target_user_id}\n"
        f"device_id: {device['device_id']}\n"
        f"имя: {device['device_name']}\n"
        f"тип: {device.get('device_type') or '—'}\n"
        f"статус: {device.get('status') or '—'}\n"
        f"создано: {device.get('created_at') or '—'}\n"
        f"last_seen: {device.get('last_seen_at') or '—'}\n"
        f"last_ip: {device.get('last_ip') or '—'}\n"
        f"vpn_uuid: {device.get('vpn_uuid') or '—'}"
    )


def render_admin_user_payments_text(target_user_id: int) -> str:
    user = get_user(target_user_id)
    payments = get_recent_payments_for_user(target_user_id, limit=5, include_internal=True)
    lines = [
        f"{BOT_BRAND} — платежи пользователя",
        "",
        f"user_id: {target_user_id}",
        f"username: @{user.get('username')}" if user and user.get("username") else "username: —",
        "",
    ]
    if not payments:
        lines.append("Платежей пока нет.")
        return "\n".join(lines)
    for payment in payments:
        amount = f"{payment.get('amount', 0):.0f}" if payment.get("amount") is not None else "0"
        lines.append(
            f"- #{payment['payment_id']} {amount} {payment.get('currency') or '—'} | "
            f"{payment.get('payment_status') or '—'} | {payment.get('payment_provider') or '—'} | "
            f"{payment.get('payment_date') or '—'}"
        )
    return "\n".join(lines)


def render_admin_user_activity_text(target_user_id: int) -> str:
    user = get_user(target_user_id)
    events = get_recent_activity_for_user(target_user_id, limit=10)
    lines = [
        f"{BOT_BRAND} — события пользователя",
        "",
        f"user_id: {target_user_id}",
        f"username: @{user.get('username')}" if user and user.get("username") else "username: —",
        "",
    ]
    if not events:
        lines.append("Событий пока нет.")
        return "\n".join(lines)
    for event in events:
        lines.append(
            f"- #{event['log_id']} {event.get('action') or '—'} | {event.get('timestamp') or '—'}"
        )
    return "\n".join(lines)


def parse_payment_plan_key(payment: dict | None) -> str | None:
    if not payment:
        return None
    provider = payment.get("payment_provider") or ""
    candidate = provider.split(":")[-1]
    return candidate if candidate in PLANS else None


def parse_payment_purchase_key(payment: dict | None) -> str | None:
    if not payment:
        return None
    provider = payment.get("payment_provider") or ""
    candidate = provider.split(":")[-1]
    if candidate in PLANS or candidate in DEVICE_SLOT_ADDONS:
        return candidate
    return None


def parse_yookassa_payment_id(payment: dict | None) -> str | None:
    if not payment:
        return None
    provider = payment.get("payment_provider") or ""
    if not provider.startswith("yookassa_sbp:"):
        return None
    parts = provider.split(":")
    if len(parts) < 3:
        return None
    return parts[1]


def get_payment_provider_family(payment: dict | None) -> str:
    if not payment:
        return "unknown"
    provider = payment.get("payment_provider") or ""
    if provider.startswith("yookassa_sbp:"):
        return "yookassa"
    if provider.startswith("yoomoney"):
        return "yoomoney"
    if provider.startswith("cardlink:"):
        return "cardlink"
    if provider == "admin_grant":
        return "admin"
    return "unknown"


def build_completed_provider(payment: dict, payment_id: int, plan_key: str, mode: str) -> str:
    family = get_payment_provider_family(payment)
    if family == "yookassa":
        return f"yookassa_{mode}:{payment_id}:{plan_key}"
    if family == "cardlink":
        order_id = parse_cardlink_order_id(payment) or "unknown"
        return f"cardlink_{mode}:{order_id}:{payment_id}:{plan_key}"
    return f"yoomoney_{mode}:{payment_id}:{plan_key}"


def match_successful_pending_payment(payment: dict) -> dict | None:
    family = get_payment_provider_family(payment)
    if family == "yookassa":
        return match_successful_yookassa_payment(payment)
    if family == "yoomoney":
        return match_successful_yoomoney_operation(payment)
    return None


def render_pending_payments_text() -> str:
    pending = get_pending_payments(limit=10)
    if not pending:
        return f"{BOT_BRAND} — платежи на проверке\n\nОчередь пуста."

    lines = [f"{BOT_BRAND} — платежи на проверке", ""]
    for payment in pending:
        username = (
            f"@{payment['username']}" if payment.get("username") else f"user {payment['user_id']}"
        )
        purchase_key = parse_payment_purchase_key(payment) or "unknown"
        plan_label = render_purchase_label(purchase_key)
        lines.append(
            f"- #{payment['payment_id']} {username} • {payment.get('amount', 0):.0f} "
            f"{payment.get('currency') or 'RUB'} • {plan_label} • {payment.get('payment_date') or '—'}"
        )
    return "\n".join(lines)


def render_processed_payments_text() -> str:
    processed = get_processed_payments(limit=15)
    if not processed:
        return f"{BOT_BRAND} — обработанные заявки\n\nИстория пока пуста."

    lines = [f"{BOT_BRAND} — обработанные заявки", ""]
    for payment in processed:
        username = (
            f"@{payment['username']}" if payment.get("username") else f"user {payment['user_id']}"
        )
        purchase_key = parse_payment_purchase_key(payment) or "unknown"
        plan_label = render_purchase_label(purchase_key)
        lines.append(
            f"- #{payment['payment_id']} {username} • {payment.get('amount', 0):.0f} "
            f"{payment.get('currency') or 'RUB'} • {plan_label} • {payment.get('payment_status') or '—'}"
        )
    return "\n".join(lines)


def render_admin_payment_text(payment_id: int) -> str:
    payment = get_payment(payment_id)
    if not payment:
        return f"{BOT_BRAND} — платёж\n\nПлатёж не найден."
    plan_key = parse_payment_purchase_key(payment) or "unknown"
    plan_label = render_purchase_label(plan_key)
    return (
        f"{BOT_BRAND} — платёж\n\n"
        f"payment_id: {payment_id}\n"
        f"user_id: {payment.get('user_id')}\n"
        f"сумма: {payment.get('amount', 0):.0f} {payment.get('currency') or 'RUB'}\n"
        f"provider: {payment.get('payment_provider') or '—'}\n"
        f"plan_key: {plan_key}\n"
        f"plan: {plan_label}\n"
        f"status: {payment.get('payment_status') or '—'}\n"
        f"created_at: {payment.get('payment_date') or '—'}"
    )


async def notify_admins(
    bot: Bot,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    exclude_user_ids: set[int] | None = None,
) -> None:
    excluded = exclude_user_ids or set()
    for admin_user_id in ADMIN_USER_IDS:
        if admin_user_id in excluded:
            continue
        try:
            await bot.send_message(
                admin_user_id,
                text,
                reply_markup=reply_markup,
            )
        except Exception as exc:
            logger.warning("failed to notify admin user_id=%s: %s", admin_user_id, exc)


async def notify_admins_about_payment(bot: Bot, payment_id: int, prefix: str) -> None:
    payment = get_payment(payment_id)
    excluded: set[int] = set()
    if payment and payment.get("user_id") is not None:
        try:
            excluded.add(int(payment["user_id"]))
        except (TypeError, ValueError):
            pass
    await notify_admins(
        bot,
        f"{prefix}\n\n{render_admin_payment_text(payment_id)}",
        reply_markup=build_admin_payment_menu(payment_id),
        exclude_user_ids=excluded,
    )


def build_yoomoney_label(user_id: int, plan_key: str) -> str:
    return f"ghost_{user_id}_{plan_key}"


def _amount_matches_yoomoney_credit(expected_amount: float, credited_amount: float) -> bool:
    try:
        expected = Decimal(str(expected_amount))
        credited = Decimal(str(credited_amount))
    except Exception:
        return False

    if abs(expected - credited) <= Decimal("0.01"):
        return True

    # Quickpay card deposits may appear in operation-history as the receiver's
    # net credited amount after the standard 3% fee, while the local payment
    # record stores the gross checkout amount.
    credited_after_fee = (expected * Decimal("0.97")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    return abs(credited_after_fee - credited) <= Decimal("0.01")


def fetch_yoomoney_operations(label: str, from_dt: datetime | None = None) -> list[dict]:
    if not automatic_payment_verification_enabled():
        return []

    payload = {"label": label, "records": "10"}
    if from_dt:
        payload["from"] = from_dt.isoformat()

    body = urlencode(payload).encode("utf-8")
    request = Request(
        "https://yoomoney.ru/api/operation-history",
        data=body,
        headers={
            "Authorization": f"Bearer {YOOMONEY_API_TOKEN}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data.get("operations") or []


def match_successful_yoomoney_operation(payment: dict) -> dict | None:
    plan_key = parse_payment_purchase_key(payment)
    if not plan_key:
        return None
    label = build_yoomoney_label(int(payment["user_id"]), plan_key)
    payment_date_raw = payment.get("payment_date")
    from_dt = None
    if payment_date_raw:
        try:
            from_dt = datetime.fromisoformat(str(payment_date_raw).replace(" ", "T")) - timedelta(
                days=1
            )
        except ValueError:
            from_dt = None
    try:
        operations = fetch_yoomoney_operations(label, from_dt=from_dt)
    except Exception as exc:
        logger.warning(
            "failed to fetch yoomoney operations for payment_id=%s: %s",
            payment.get("payment_id"),
            exc,
        )
        return None

    expected_amount = float(payment.get("amount") or 0)
    for operation in operations:
        if operation.get("status") != "success":
            continue
        try:
            amount = float(operation.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        if not _amount_matches_yoomoney_credit(expected_amount, amount):
            continue
        if (operation.get("label") or "") != label:
            continue
        return operation
    return None


def match_successful_yookassa_payment(payment: dict) -> dict | None:
    payment_id = parse_yookassa_payment_id(payment)
    if not payment_id or not yookassa_configured():
        return None
    try:
        remote_payment = fetch_yookassa_payment(payment_id)
    except Exception as exc:
        logger.warning(
            "failed to fetch yookassa payment for payment_id=%s: %s", payment.get("payment_id"), exc
        )
        return None
    if remote_payment.get("status") != "succeeded":
        return None
    try:
        remote_amount = float(((remote_payment.get("amount") or {}).get("value")) or 0)
    except (TypeError, ValueError):
        remote_amount = 0.0
    expected_amount = float(payment.get("amount") or 0)
    if abs(remote_amount - expected_amount) > 0.01:
        return None
    return remote_payment


def get_yookassa_remote_payment_state(payment: dict) -> tuple[str | None, dict | None]:
    payment_id = parse_yookassa_payment_id(payment)
    if not payment_id or not yookassa_configured():
        return None, None
    try:
        remote_payment = fetch_yookassa_payment(payment_id)
    except Exception as exc:
        logger.warning(
            "failed to fetch yookassa payment state for payment_id=%s: %s",
            payment.get("payment_id"),
            exc,
        )
        return None, None

    status = str(remote_payment.get("status") or "").strip() or None
    if status != "succeeded":
        return status, remote_payment

    try:
        remote_amount = float(((remote_payment.get("amount") or {}).get("value")) or 0)
    except (TypeError, ValueError):
        remote_amount = 0.0
    expected_amount = float(payment.get("amount") or 0)
    if abs(remote_amount - expected_amount) > 0.01:
        logger.warning(
            "yookassa amount mismatch for payment_id=%s remote=%.2f expected=%.2f",
            payment.get("payment_id"),
            remote_amount,
            expected_amount,
        )
        return "amount_mismatch", remote_payment
    return status, remote_payment


async def approve_pending_payment_with_provider(
    bot: Bot,
    payment: dict,
    plan_key: str,
    completed_provider: str,
    notify_user: bool = True,
) -> dict | None:
    payment_id = int(payment["payment_id"])
    user_id = int(payment["user_id"])
    if not transition_pending_payment(payment_id, "approved"):
        return None
    if is_device_slot_addon_key(plan_key):
        addon = DEVICE_SLOT_ADDONS[plan_key]
        total_slots = add_user_extra_device_slots(
            user_id,
            addon["slots"],
            reason=f"device_slot_addon_approved:{plan_key}",
        )
        record_payment(
            user_id,
            float(payment.get("amount") or addon["amount"]),
            str(payment.get("currency") or "RUB"),
            provider=completed_provider,
            status="completed",
        )
        log_activity(user_id, f"payment_auto_approved_{plan_key}")
        if notify_user:
            try:
                await bot.send_message(
                    user_id,
                    f"{BOT_BRAND}\n\n"
                    "Оплата подтверждена.\n"
                    f"Покупка: {render_purchase_label(plan_key)}\n"
                    f"Теперь докуплено слотов: +{total_slots}",
                    reply_markup=build_devices_menu(user_id),
                )
            except Exception as exc:
                logger.warning("failed to notify add-on user_id=%s: %s", user_id, exc)
        await notify_admins_about_payment(
            bot,
            payment_id,
            f"{BOT_BRAND} — допслот подтверждён",
        )
        return get_user(user_id)
    try:
        activated_user = activate_paid_plan(
            user_id,
            None,
            plan_key,
            provider=completed_provider,
        )
    except XrayError as exc:
        update_payment_status(payment_id, "pending")
        logger.warning("approval xray failure for payment_id=%s: %s", payment_id, exc)
        raise

    expires_at = parse_expires_at(activated_user.get("expires_at"))
    log_activity(user_id, f"payment_auto_approved_{plan_key}")
    plan_label = render_purchase_label(plan_key)
    if notify_user:
        try:
            await bot.send_message(
                user_id,
                f"{BOT_BRAND}\n\n"
                "Оплата подтверждена.\n"
                f"Покупка: {plan_label}\n"
                f"До: {expires_at.strftime('%d.%m.%Y %H:%M') if expires_at else '—'}",
                reply_markup=build_payment_success_menu(),
            )
        except Exception as exc:
            logger.warning("failed to notify auto-approved user_id=%s: %s", user_id, exc)
    await notify_admins_about_payment(
        bot,
        payment_id,
        f"{BOT_BRAND} — платёж подтверждён автоматически",
    )
    return activated_user


async def reconcile_pending_payments(bot: Bot) -> int:
    approved_count = 0
    for payment in get_pending_payments(limit=50):
        plan_key = parse_payment_purchase_key(payment)
        if not plan_key:
            continue
        family = get_payment_provider_family(payment)
        if family == "yookassa":
            remote_status, remote_payment = get_yookassa_remote_payment_state(payment)
            if remote_status == "canceled":
                payment_id = int(payment["payment_id"])
                if transition_pending_payment(payment_id, "rejected"):
                    user_id = int(payment["user_id"])
                    try:
                        await bot.send_message(
                            user_id,
                            f"{BOT_BRAND}\n\n"
                            "Платёж был отменён на стороне ЮKassa.\n\n"
                            "Если хочешь оплатить — открой «Купить подписку» и создай новую заявку.",
                            reply_markup=build_buy_menu(user_id),
                        )
                    except Exception as exc:
                        logger.warning(
                            "failed to notify canceled yookassa payment user_id=%s: %s",
                            user_id,
                            exc,
                        )
                continue
            matched_operation = remote_payment if remote_status == "succeeded" else None
        elif family == "yoomoney":
            matched_operation = match_successful_yoomoney_operation(payment)
        else:
            continue
        if not matched_operation:
            continue
        try:
            auto_provider = build_completed_provider(
                payment, int(payment["payment_id"]), plan_key, "auto"
            )
            activated_user = await approve_pending_payment_with_provider(
                bot,
                payment,
                plan_key,
                auto_provider,
            )
        except XrayError:
            continue
        if not activated_user:
            continue
        approved_count += 1
    return approved_count


async def send_pending_payment_reminders(bot: Bot) -> int:
    reminded_count = 0
    reminder_specs = [
        {
            "minutes": 10,
            "prefix": "payment_pending_reminder_10m:",
            "user_text": (
                "Твоя заявка всё ещё на проверке.\n"
                "Обычно это занимает несколько минут.\n\n"
                "Жми /payments или напиши админу."
            ),
            "notify_admins": False,
        },
        {
            "minutes": 60,
            "prefix": "payment_pending_reminder_1h:",
            "user_text": (
                "Заявка ждёт уже свыше часа.\n"
                "Если перевод прошёл — напиши админу.\n"
                "Или создай новую заявку через /buy позже."
            ),
            "notify_admins": True,
        },
    ]
    for spec in reminder_specs:
        payments = get_pending_payments_requiring_reminder(
            min_age_minutes=spec["minutes"],
            reminder_action_prefix=spec["prefix"],
            limit=50,
        )
        for payment in payments:
            payment_id = int(payment["payment_id"])
            user_id = int(payment["user_id"])
            fresh_payment = get_payment(payment_id)
            if not fresh_payment or fresh_payment.get("payment_status") != "pending":
                continue
            try:
                await bot.send_message(
                    user_id,
                    f"{BOT_BRAND}\n\n{spec['user_text']}\n\npayment_id: {payment_id}",
                    reply_markup=build_user_payments_menu(user_id),
                )
                log_activity(user_id, f"{spec['prefix']}{payment_id}")
                reminded_count += 1
            except Exception as exc:
                logger.warning(
                    "failed to send pending reminder minutes=%s payment_id=%s user_id=%s: %s",
                    spec["minutes"],
                    payment_id,
                    user_id,
                    exc,
                )
                continue
            if spec["notify_admins"]:
                await notify_admins_about_payment(
                    bot,
                    payment_id,
                    f"{BOT_BRAND} — заявка ждёт проверки больше {spec['minutes']} минут",
                )
    return reminded_count


async def maybe_alert_payment_queue_health(
    bot: Bot,
    last_signature: tuple[int, int] | None,
) -> tuple[int, int] | None:
    summary = get_payment_status_summary()
    older_1h = int(summary.get("pending_older_1h", 0) or 0)
    total_pending = int(summary.get("pending", {}).get("count", 0) or 0)
    if older_1h < PAYMENT_QUEUE_ALERT_THRESHOLD:
        return None

    signature = (older_1h, total_pending)
    if signature == last_signature:
        return last_signature

    await notify_admins(
        bot,
        f"{BOT_BRAND} — очередь платежей требует внимания\n\n"
        f"- pending: {total_pending}\n"
        f"- pending >1ч: {older_1h}\n"
        f"- reminded 1ч: {summary.get('pending_reminded_1h', 0)}\n"
        f"- threshold: {PAYMENT_QUEUE_ALERT_THRESHOLD}\n\n"
        "Открой операторское меню и проверь очередь платежей.",
        reply_markup=build_admin_menu(),
    )
    return signature


async def maybe_send_payment_queue_digest(
    bot: Bot,
    last_digest_at: datetime | None,
) -> datetime | None:
    summary = get_payment_status_summary()
    older_1h = int(summary.get("pending_older_1h", 0) or 0)
    if older_1h < PAYMENT_QUEUE_ALERT_THRESHOLD:
        return None

    now = datetime.now()
    if last_digest_at and (now - last_digest_at) < timedelta(minutes=PAYMENT_QUEUE_DIGEST_MINUTES):
        return last_digest_at

    await notify_admins(
        bot,
        f"{BOT_BRAND} — digest по очереди платежей\n\n"
        f"- pending: {summary.get('pending', {}).get('count', 0)}\n"
        f"- pending >10м: {summary.get('pending_older_10m', 0)}\n"
        f"- reminded 10м: {summary.get('pending_reminded_10m', 0)}\n"
        f"- pending >1ч: {summary.get('pending_older_1h', 0)}\n"
        f"- reminded 1ч: {summary.get('pending_reminded_1h', 0)}\n"
        f"- digest interval: {PAYMENT_QUEUE_DIGEST_MINUTES} мин\n\n"
        "Очередь всё ещё не разобрана. Проверь pending-платежи.",
        reply_markup=build_admin_menu(),
    )
    return now


def render_abuse_stats_text() -> str:
    return (
        f"{BOT_BRAND} — Anti-Abuse\n\n"
        f"{render_rate_limit_block()}\n\n"
        f"{render_subscription_rate_limit_block()}\n\n"
        f"{render_noisy_users_block()}\n\n"
        f"{render_suspicious_users_block()}\n\n"
        "Текущие лимиты:\n"
        f"- trial: {RATE_LIMITS['trial'][0]} за {RATE_LIMITS['trial'][1]} сек\n"
        f"- config: {RATE_LIMITS['config'][0]} за {RATE_LIMITS['config'][1]} сек\n"
        f"- repair: {RATE_LIMITS['repair'][0]} за {RATE_LIMITS['repair'][1]} сек\n"
        f"- invite: {RATE_LIMITS['invite'][0]} за {RATE_LIMITS['invite'][1]} сек\n\n"
        f"Порог подозрительности: {SUSPICIOUS_RATE_LIMIT_THRESHOLD} событий за 24ч"
    )


def render_admin_vpn_health_text() -> str:
    payload, stale, source_path = load_vpn_service_agent_payload()
    policy = build_subscription_health_policy()
    port_health = check_xray_ports_health()
    generated_at = "—"
    if payload and payload.get("generated_at"):
        generated_at = str(payload.get("generated_at"))

    vpn_delivery = (payload or {}).get("vpn_delivery") or {}
    tcp_probe = vpn_delivery.get("tcp_probe") or {}
    xui_inbound = vpn_delivery.get("xui_inbound") or {}
    reality_canary = vpn_delivery.get("reality_canary") or {}
    secondary_xui_inbound = vpn_delivery.get("secondary_xui_inbound") or {}
    secondary_reality_canary = vpn_delivery.get("secondary_reality_canary") or {}

    def yes_no(value: object) -> str:
        return "ok" if value else "fail"

    def canary_line(label: str, data: dict) -> str:
        if not data:
            return f"{label}: —"
        http_code = data.get("http_code")
        total_s = data.get("total_s")
        details = []
        details.append(yes_no(data.get("ok")))
        if http_code is not None:
            details.append(f"http={http_code}")
        if total_s is not None:
            details.append(f"t={float(total_s):.3f}s")
        return f"{label}: {' | '.join(details)}"

    subscription_edge = next(
        (
            service
            for service in ((payload or {}).get("services") or [])
            if service.get("service_id") == "subscription-edge"
        ),
        {},
    )
    warp_signal = load_recent_warp_timeout_signal()
    return (
        f"{BOT_BRAND} — Здоровье VPN\n\n"
        f"Общее состояние: {policy.get('health_status', 'unknown')}\n"
        f"Транспорт: {policy.get('transport_health_status', 'unknown')}\n"
        f"Подписка/доставка: {policy.get('subscription_health_status', 'unknown')}\n"
        f"Сейчас главный маршрут: {policy.get('preferred_transport', 'main')}\n"
        f"Лучший path по замерам: {policy.get('best_path', '—')}\n"
        f"Как часто обновлять подписку: {policy.get('profile_update_interval', '—')} мин\n"
        f"Последняя проверка: {generated_at}\n"
        f"Сводка устарела: {'да' if stale else 'нет'}\n\n"
        f"Порты сервера: 443={yes_no(port_health.get(443))}, 2083={yes_no(port_health.get(2083))}\n"
        f"Проверка TCP: {yes_no(tcp_probe.get('ok'))}\n"
        f"Клиенты на 443: {yes_no(xui_inbound.get('ok'))} | {xui_inbound.get('client_count', '—')}\n"
        f"Клиенты на 2083: {yes_no(secondary_xui_inbound.get('ok'))} | {secondary_xui_inbound.get('client_count', '—')}\n"
        f"{canary_line('Проверка Reality 443', reality_canary)}\n"
        f"{canary_line('Проверка Reality 2083', secondary_reality_canary)}\n\n"
        f"WARP recent: {warp_signal.get('status', 'unknown')} | "
        f"timeout={warp_signal.get('timed_out_count', 0)} | "
        f"eof={warp_signal.get('unexpected_eof_count', 0)} | "
        f"window={warp_signal.get('window_minutes', '—')}м\n"
        f"Подписка снаружи: {yes_no(subscription_edge.get('healthy', True))}\n"
        f"На локальном клиенте QUIC режется: {'да' if (payload or {}).get('quic_reject_present') else 'нет'}\n"
        + (
            f"\n\nЧто сказать пользователям:\n{policy['announce']}"
            if policy.get("announce")
            else ""
        )
        + f"\n\nИсточник: {source_path}"
    )


def render_admin_runtime_text() -> str:
    return (
        f"{BOT_BRAND} — Техпанель\n\n"
        "Здесь быстрые служебные действия.\n\n"
        "Что можно сделать:\n"
        "- Обновить всё сразу\n"
        "- Получить готовый текст для клиента\n"
        "- Обновить здоровье VPN\n"
        "- Синхронизировать устройства\n"
        "- Починить резервный порт 2083\n"
        "- Проверить платежи\n\n"
        "Это нужно, когда у пользователей что-то не работает."
    )


async def run_operator_json_command(
    cmd: list[str], timeout: int = 30
) -> tuple[bool, dict | None, str]:
    def _run() -> tuple[int, str]:
        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=timeout,
            env=_sudo_env(),
        )
        return completed.returncode, (completed.stdout or "").strip()

    try:
        rc, output = await asyncio.to_thread(_run)
    except Exception as exc:
        return False, None, str(exc)

    try:
        payload = json.loads(output) if output else None
    except Exception:
        payload = None

    return rc == 0, payload, output


def render_admin_runtime_refresh_result(
    health_text: str,
    devices_ok: bool,
    devices_payload: dict | None,
    devices_output: str,
    secondary_ok: bool,
    secondary_payload: dict | None,
    secondary_output: str,
) -> str:
    lines = [
        f"{BOT_BRAND} — Техпанель",
        "",
        "Готово. Быстрая проверка завершена.",
        "",
        "1. Здоровье VPN",
        health_text.replace(f"{BOT_BRAND} — Здоровье VPN\n\n", "", 1),
        "",
        "2. Устройства",
    ]
    if devices_ok and devices_payload is not None:
        lines.extend(
            [
                f"Нашлось: {devices_payload.get('matched', 0)}",
                f"Обновлено: {devices_payload.get('updated', 0)}",
                f"Пропущено: {devices_payload.get('skipped', 0)}",
            ]
        )
    else:
        details = (devices_output or "нет деталей")[:250]
        lines.extend(["Не удалось обновить активность устройств.", f"Детали: {details}"])

    lines.extend(["", "3. Резерв 2083"])
    if secondary_ok and secondary_payload is not None:
        lines.extend(
            [
                f"Устройств в базе: {secondary_payload.get('devices_seen', 0)}",
                f"Зеркалировано: {secondary_payload.get('mirrored', 0)}",
                f"Добавлено в runtime: {secondary_payload.get('runtime_added', 0)}",
                f"Ошибок: {len(secondary_payload.get('errors', []))}",
            ]
        )
    else:
        details = (secondary_output or "нет деталей")[:250]
        lines.extend(["Не удалось перепроверить резерв.", f"Детали: {details}"])

    return "\n".join(lines)


def render_admin_user_reply_text() -> str:
    policy = build_subscription_health_policy()
    status = policy.get("health_status", "unknown")
    transport = policy.get("preferred_transport", "main")
    announce = policy.get("announce", "").strip()

    if status == "ok":
        message = "Сейчас всё работает нормально. Можешь просто открыть приложение и подключиться ещё раз."
    elif status == "advisory":
        if transport == "fallback":
            message = "Сервис работает, но сейчас мы временно ведём трафик через резервный маршрут. Если подключение уже открыто, ничего делать не нужно."
        else:
            message = "Сервис работает, но сейчас может подключаться чуть медленнее обычного. Обычно помогает просто подождать и подключиться ещё раз."
    elif status == "degraded":
        if transport == "fallback":
            message = "Сейчас на основном маршруте есть проблема. Мы уже перевели подключение на резервный маршрут. Попробуй открыть приложение заново через 1-2 минуты."
        else:
            message = "Сейчас на нашей стороне есть проблема с подключением. Мы уже чиним. Попробуй ещё раз через 1-2 минуты."
    elif status == "stale":
        message = "Мы перепроверяем маршруты. Если прямо сейчас не подключается, попробуй ещё раз чуть позже."
    else:
        message = "Мы уже проверяем соединение. Если не подключается прямо сейчас, попробуй ещё раз через пару минут."

    if announce:
        message = f"{message}\n\nКоротко: {announce}"

    return f"{BOT_BRAND} — Текст для клиента\n\nМожно отправить почти как есть:\n\n{message}"


def build_repair_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="Не подключается", callback_data="diag:no_connect")
    builder.button(text="Telegram не работает", callback_data="diag:no_telegram")
    builder.button(text="YouTube не работает", callback_data="diag:no_youtube")
    builder.button(text="Gemini / Google AI", callback_data="diag:gemini")
    builder.button(text="Сайты не грузятся", callback_data="diag:no_sites")
    builder.button(text="Медленно работает", callback_data="diag:slow")
    builder.button(text="Не работает на мобильной сети", callback_data="diag:mobile")
    builder.button(text="Выдать профиль заново", callback_data="repair:main")
    builder.adjust(1, 1, 1, 1, 1, 1, 1, 1)
    return builder.as_markup()


def build_repair_followup_menu(kind: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Сработало", callback_data=f"repair_result:{kind}:worked")
    builder.button(text="Не сработало", callback_data=f"repair_result:{kind}:failed")
    builder.button(text="Назад в меню", callback_data="menu")
    builder.adjust(1, 1, 1)
    return builder.as_markup()


def render_repair_intro() -> str:
    return (
        f"{BOT_BRAND}\n\n"
        "Что случилось?\n"
        "Выбери проблему — агент проведёт диагностику\n"
        "и подберёт лучший конфиг."
    )


# ---------------------------------------------------------------------------
# Diagnostic agent — server-side checks + smart config selection
# ---------------------------------------------------------------------------

DIAG_TRANSPORTS: list[dict] = [
    {
        "port": VPN_PORT,
        "tag": "Основной 443",
        "label_suffix": "",
        "bypass_dpi": False,
        "note": "основной для России — 443 с VK-like маскировкой",
    },
    {
        "port": SECONDARY_VPN_PORT,
        "tag": "Резерв 2083",
        "label_suffix": " Reserve-2083",
        "bypass_dpi": True,
        "note": "первый резерв для РФ — 2083",
    },
    {
        "port": LEGACY_DIAGNOSTIC_VPN_PORT,
        "tag": "Диагностика 39829",
        "label_suffix": " Diagnostic-39829",
        "bypass_dpi": True,
        "note": "только для диагностики, не основной для массовой выдачи",
    },
]


def _diag_check_ports() -> dict[int, bool]:
    """TCP-check all diagnostic transport ports."""
    return {t["port"]: check_xray_port_alive(t["port"], timeout=3.0) for t in DIAG_TRANSPORTS}


def _diag_check_warp() -> bool:
    """Quick check if WARP socks proxy is reachable and forwarding."""
    try:
        with socket.create_connection(("127.0.0.1", 40000), timeout=2.0):
            return True
    except (OSError, TimeoutError):
        return False


async def _diag_check_warp_routing() -> dict[str, bool]:
    """Check if key destinations are reachable via selected probes on the VPS."""
    results = {}
    targets = {
        "youtube": "https://www.youtube.com",
        "gemini": "https://gemini.google.com",
        "aistudio": "https://aistudio.google.com",
    }
    for name, url in targets.items():
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl",
                "-s",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                "--socks5",
                "127.0.0.1:40000",
                "--max-time",
                "5",
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=8.0)
            code = (stdout or b"").decode().strip()
            results[name] = code in ("200", "301", "302", "303", "307")
        except Exception:
            results[name] = False
    return results


async def _diag_check_direct_http(url: str) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl",
            "-s",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code}",
            "--max-time",
            "5",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=8.0)
        code = (stdout or b"").decode().strip()
        return code in ("200", "301", "302", "303", "307")
    except Exception:
        return False


async def run_server_diagnostics() -> dict:
    """Run full server-side diagnostics. Returns structured result."""
    port_health = _diag_check_ports()
    warp_alive = _diag_check_warp()
    warp_routing = await _diag_check_warp_routing() if warp_alive else {}
    telegram_direct = await _diag_check_direct_http("https://t.me")
    return {
        "ports": port_health,
        "warp_alive": warp_alive,
        "warp_youtube": warp_routing.get("youtube", False),
        "warp_gemini": warp_routing.get("gemini", False),
        "warp_aistudio": warp_routing.get("aistudio", False),
        "telegram_direct": telegram_direct,
        "all_ports_up": all(port_health.values()),
        "any_bypass_port_up": any(
            port_health.get(t["port"], False) for t in DIAG_TRANSPORTS if t["bypass_dpi"]
        ),
    }


def _ensure_client_on_port(user_id: int, user_uuid: str, port: int, email: str) -> None:
    """Ensure xray client exists on a specific port."""
    _run_xray_cmd(
        [
            "python3",
            XRAY_CLIENT_MANAGER,
            "ensure-client",
            "--port",
            str(port),
            "--uuid",
            user_uuid,
            "--email",
            email,
            "--flow",
            "xtls-rprx-vision",
            "--tg-id",
            str(user_id),
        ],
        action=f"ensure-client:diag-port-{port}",
    )


def _generate_link_for_port(user_uuid: str, port: int, label: str | None = None) -> str:
    """Generate a VLESS Reality link for any of our transport ports."""
    profile = load_vless_profile(port)
    return _generate_reality_link_for_port(user_uuid, port, profile, label=label)


def _pick_best_transport(
    symptom: str,
    diag: dict,
) -> tuple[dict, str]:
    """Pick the best transport config based on symptom and diagnostics.

    Returns (transport_dict, reason_text).
    """
    ports = diag["ports"]

    # Symptoms that clearly need a DPI-bypass port
    need_bypass = symptom in ("mobile", "no_connect", "slow")

    # Telegram/YouTube issues = likely WARP routing problem, not transport
    if symptom == "no_telegram" and not diag["telegram_direct"]:
        need_bypass = True
    if symptom == "no_youtube" and not diag["warp_youtube"]:
        need_bypass = True
    if symptom == "gemini" and not (diag["warp_gemini"] and diag["warp_aistudio"]):
        need_bypass = True

    # If primary port is down, force bypass
    if not ports.get(VPN_PORT, False):
        need_bypass = True

    if need_bypass:
        reasons = {
            "mobile": "Мобильный оператор фильтрует порт 443. Переключаю на российский резервный порт.",
            "no_connect": "Основной порт заблокирован или нестабилен. Переключаю на резервный.",
            "slow": "Порт 443 проходит через DPI и тормозит. Переключаю на резервный порт.",
            "no_telegram": "Telegram отвечает нестабильно. Пробую резервный транспорт.",
            "no_youtube": "YouTube ограничен провайдером. Пробую резервный транспорт.",
            "gemini": "Google AI сервисы отвечают нестабильно. Пробую резервный транспорт и обновляю профиль.",
            "no_sites": "Сайты не грузятся. Пробую резервный порт без DPI.",
        }
        secondary = next(
            (t for t in DIAG_TRANSPORTS if t["port"] == SECONDARY_VPN_PORT),
            None,
        )
        legacy = next(
            (t for t in DIAG_TRANSPORTS if t["port"] == LEGACY_DIAGNOSTIC_VPN_PORT),
            None,
        )
        if secondary and ports.get(secondary["port"], False):
            return secondary, reasons.get(symptom, "Переключаю на резервный транспорт.")
        if legacy and ports.get(legacy["port"], False):
            return legacy, (
                "Основной и резервный 2083 недоступны. "
                "Пробую legacy-диагностический профиль."
            )
        # All bypass ports down — fall back to primary
        if ports.get(VPN_PORT, False):
            return DIAG_TRANSPORTS[
                0
            ], "Резервные порты недоступны. Основной порт работает — пересоздаю профиль."
    else:
        # For no_sites, no_telegram, no_youtube with working WARP — re-issue main profile
        if ports.get(VPN_PORT, False):
            reasons_main = {
                "no_telegram": "Сервер достаёт Telegram напрямую — пересоздаю профиль.",
                "no_youtube": "YouTube идёт через WARP — должно работать. Пересоздаю профиль.",
                "gemini": "Gemini и AI Studio с сервера открываются. Пересоздаю профиль и даю шаги для приложения.",
                "no_sites": "Сервер работает нормально. Пересоздаю профиль — скорее всего старый повреждён.",
            }
            return DIAG_TRANSPORTS[0], reasons_main.get(symptom, "Пересоздаю основной профиль.")

    # Nothing works
    return DIAG_TRANSPORTS[
        0
    ], "Все порты нестабильны. Пересоздаю основной профиль — попробуй позже."


async def diagnose_and_send_config(
    callback,
    symptom: str,
) -> None:
    """Full diagnostic flow: check server, pick transport, ensure client, send config."""
    user_id = callback.from_user.id
    _, user = get_user_state(user_id)
    if not user:
        await safe_edit(
            callback,
            render_inactive_subscription_text(),
            reply_markup=build_main_menu(user_id),
        )
        return

    # Show "diagnosing..." message
    await safe_edit(
        callback,
        f"{BOT_BRAND}\n\nПровожу диагностику...\nПроверяю порты, маршрутизацию, WARP...",
    )

    diag = await run_server_diagnostics()
    transport, reason = _pick_best_transport(symptom, diag)
    port = transport["port"]

    # Build diagnostic report
    port_status_lines = []
    for t in DIAG_TRANSPORTS:
        alive = diag["ports"].get(t["port"], False)
        icon = "+" if alive else "x"
        port_status_lines.append(f"  [{icon}] {t['tag']}")
    warp_icon = "+" if diag["warp_alive"] else "x"
    tg_icon = "+" if diag["telegram_direct"] else "x"
    yt_icon = "+" if diag["warp_youtube"] else "x"
    gemini_icon = "+" if diag["warp_gemini"] else "x"
    aistudio_icon = "+" if diag["warp_aistudio"] else "x"

    report = (
        f"{BOT_BRAND}\n\n"
        f"Диагностика\n\n"
        f"Транспорты:\n" + "\n".join(port_status_lines) + "\n\n"
        f"WARP:\n"
        f"  [{warp_icon}] Proxy\n"
        f"  [{yt_icon}] YouTube\n"
        f"  [{gemini_icon}] Gemini\n"
        f"  [{aistudio_icon}] AI Studio\n\n"
        f"Telegram direct:\n"
        f"  [{tg_icon}] Reachability\n\n"
        f"Результат: {reason}\n\n"
    )

    # Ensure user has client on the chosen port
    device = sync_primary_device(user_id)
    target_uuid = device["vpn_uuid"] if device else user["vpn_uuid"]
    email = device.get("xray_email") if device else None
    if not email:
        email = f"tg-{user_id}@x0tta6bl4"

    try:
        _ensure_client_on_port(user_id, target_uuid, port, email)
    except XrayError:
        logger.warning("diag: failed to ensure client on port %d for user %d", port, user_id)

    # Generate link for the chosen transport
    label = f"{BOT_BRAND}{transport['label_suffix']}"
    vless_link = _generate_link_for_port(target_uuid, port, label=label)

    report += (
        f"Подключение: {transport['tag']}\n\n"
        "Импортируй этот профиль в приложение:\n\n"
        f"`{vless_link}`"
    )

    log_activity(user_id, f"diag_{symptom}_port_{port}")

    await safe_edit(
        callback,
        report,
        reply_markup=build_repair_followup_menu(f"diag_{symptom}"),
        parse_mode="Markdown",
    )

    # Also send QR
    try:
        await send_qr_card(callback.message, f"Диагностика — {transport['tag']}", vless_link)
    except Exception as exc:
        logger.warning("diag: failed to send QR for user %d: %s", user_id, exc)


async def send_qr_card(message: Message, title: str, vless_url: str) -> None:
    qr_image = qrcode.make(vless_url)
    buffer = BytesIO()
    qr_image.save(buffer, format="PNG")
    buffer.seek(0)

    caption = (
        f"🔗 <b>{html.escape(BOT_BRAND)}: {html.escape(title)}</b>\n\n"
        "Сканируй QR в приложении.\n\n"
        f"<code>{html.escape(vless_url)}</code>"
    )
    await message.answer_photo(
        photo=BufferedInputFile(buffer.read(), filename="ghost-access-config.png"),
        caption=caption,
        parse_mode="HTML",
    )


async def send_connect_bundle(
    message: Message,
    *,
    main_link: str,
    fallback_link: str = "",
    context: str,
    title: str = "подключение",
    lead_text: str | None = None,
    show_main_menu: bool = True,
) -> None:
    if hasattr(message, "bot") and hasattr(message, "chat"):
        await send_connect_bundle_to_chat(
            message.bot,
            message.chat.id,
            main_link=main_link,
            fallback_link=fallback_link,
            context=context,
            title=title,
            lead_text=lead_text,
            show_main_menu=show_main_menu,
        )
        return

    await message.answer_photo(
        photo=BufferedInputFile(
            _render_connect_bundle_qr(main_link),
            filename="ghost-access-connect-qr.png",
        ),
        caption=_build_connect_bundle_caption(
            main_link=main_link,
            fallback_link=fallback_link,
            title=title,
            lead_text=lead_text,
        ),
        parse_mode="HTML",
        reply_markup=build_connect_delivery_menu(
            context,
            has_fallback=bool(fallback_link),
            show_main_menu=show_main_menu,
        ),
    )


def _build_connect_bundle_caption(
    *,
    main_link: str,
    fallback_link: str = "",
    title: str = "подключение",
    lead_text: str | None = None,
) -> str:
    lines = [f"🔗 <b>{html.escape(BOT_BRAND)}: {html.escape(title)}</b>", ""]
    if lead_text:
        lines.append(html.escape(lead_text))
        lines.append("")
    lines.extend(
        [
            "Импортируй по QR.",
            "Если вручную — скопируй ссылку ниже.",
            "",
            f"<code>{html.escape(main_link)}</code>",
        ]
    )
    if fallback_link:
        lines.extend(
            [
                "",
                f"Если основной {VPN_PORT} не работает — открой кнопку «{fallback_delivery_button_text()}».",
            ]
        )
    return "\n".join(lines)


def _render_connect_bundle_qr(main_link: str) -> bytes:
    qr_image = qrcode.make(main_link)
    buffer = BytesIO()
    qr_image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.read()


def _render_qr_data_uri(link: str) -> str:
    if not qrcode or not link:
        return ""
    png = _render_connect_bundle_qr(link)
    encoded = base64.b64encode(png).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _format_portal_expiry(expires_at: datetime | None) -> str:
    if not expires_at:
        return "—"
    return expires_at.astimezone(UTC).strftime("%d.%m.%Y %H:%M UTC")


def _build_portal_link_rows(
    *,
    main_link: str,
    subscription_url: str,
    fallback_link: str = "",
    android_bundle_url: str = "",
) -> list[tuple[str, str]]:
    rows = [("Subscription URL", subscription_url)]
    if main_link:
        rows.append((f"Прямой профиль {VPN_PORT}", main_link))
    if fallback_link:
        rows.append((fallback_profile_title(), fallback_link))
    if android_bundle_url:
        rows.append(("Android bundle", android_bundle_url))
    return rows


def render_web_access_portal(
    *,
    title: str,
    subtitle: str,
    plan_label: str,
    expires_at: datetime | None,
    main_link: str,
    subscription_url: str,
    fallback_link: str = "",
    android_bundle_url: str = "",
    claim_code: str = "",
    status: str = "active",
) -> str:
    badge = "Активно" if status == "active" else "Истекло"
    qr_uri = _render_qr_data_uri(main_link or subscription_url)
    rows = _build_portal_link_rows(
        main_link=main_link,
        subscription_url=subscription_url,
        fallback_link=fallback_link,
        android_bundle_url=android_bundle_url,
    )
    rows_html = "\n".join(
        (
            "<div class=\"link-card\">"
            f"<div class=\"link-label\">{html.escape(label)}</div>"
            f"<code>{html.escape(value)}</code>"
            "</div>"
        )
        for label, value in rows
    )
    claim_html = ""
    if claim_code:
        claim_html = (
            "<div class=\"meta-row\">"
            f"<span>Claim code</span><code>{html.escape(claim_code)}</code>"
            "</div>"
        )
    qr_html = ""
    if qr_uri:
        qr_html = (
            "<div class=\"qr-card\">"
            "<div class=\"qr-title\">QR для быстрого импорта</div>"
            f"<img src=\"{qr_uri}\" alt=\"VPN QR\" />"
            "</div>"
        )
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(BOT_BRAND)} — доступ</title>
  <meta name="robots" content="noindex,nofollow,noarchive,nosnippet,noimageindex" />
  <style>
    :root {{
      color-scheme: light;
      --bg: #f3efe7;
      --panel: #fffdf8;
      --text: #1d1a17;
      --muted: #6a625b;
      --line: #ddd2c5;
      --accent: #0e6b55;
      --warn: #b25722;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(14,107,85,0.08), transparent 36%),
        linear-gradient(180deg, #f8f3ea 0%, var(--bg) 100%);
      color: var(--text);
    }}
    .wrap {{
      max-width: 880px;
      margin: 0 auto;
      padding: 24px 16px 48px;
    }}
    .hero, .panel, .qr-card, .link-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      box-shadow: 0 10px 30px rgba(23, 17, 11, 0.06);
    }}
    .hero {{
      padding: 24px;
      margin-bottom: 18px;
    }}
    .eyebrow {{
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 12px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 32px;
      line-height: 1.1;
    }}
    .subtitle {{
      color: var(--muted);
      font-size: 16px;
      max-width: 640px;
      margin: 0;
    }}
    .badge {{
      display: inline-block;
      margin-top: 16px;
      padding: 8px 12px;
      border-radius: 999px;
      background: {('#f8ede4' if status != 'active' else '#e7f5f0')};
      color: {('var(--warn)' if status != 'active' else 'var(--accent)')};
      font-weight: 700;
      font-size: 13px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1.3fr 0.9fr;
      gap: 18px;
      align-items: start;
    }}
    .panel {{
      padding: 20px;
    }}
    .meta-row {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 12px 0;
      border-bottom: 1px solid var(--line);
      font-size: 15px;
    }}
    .meta-row:last-child {{ border-bottom: 0; }}
    .meta-row span {{ color: var(--muted); }}
    .links {{
      display: grid;
      gap: 12px;
      margin-top: 18px;
    }}
    .link-card {{
      padding: 14px;
    }}
    .link-label {{
      font-size: 13px;
      font-weight: 700;
      color: var(--muted);
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    code {{
      display: block;
      font-family: "IBM Plex Mono", "SFMono-Regular", monospace;
      font-size: 12px;
      line-height: 1.55;
      word-break: break-all;
      white-space: pre-wrap;
      color: #1c4338;
    }}
    .hint {{
      margin-top: 18px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.55;
    }}
    .qr-card {{
      padding: 20px;
      text-align: center;
    }}
    .qr-title {{
      font-weight: 700;
      margin-bottom: 12px;
    }}
    .qr-card img {{
      width: min(100%, 280px);
      aspect-ratio: 1 / 1;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: white;
      padding: 12px;
    }}
    @media (max-width: 760px) {{
      .grid {{
        grid-template-columns: 1fr;
      }}
      h1 {{
        font-size: 28px;
      }}
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <div class="eyebrow">{html.escape(BOT_BRAND)}</div>
      <h1>{html.escape(title)}</h1>
      <p class="subtitle">{html.escape(subtitle)}</p>
      <div class="badge">{html.escape(badge)}</div>
    </section>
    <section class="grid">
      <div class="panel">
        <div class="meta-row"><span>План</span><strong>{html.escape(plan_label)}</strong></div>
        <div class="meta-row"><span>Действует до</span><strong>{html.escape(_format_portal_expiry(expires_at))}</strong></div>
        {claim_html}
        <div class="links">
          {rows_html}
        </div>
        <div class="hint">
          Открой приложение, импортируй один из профилей или subscription URL и просто включи подключение.
          Если основной профиль не открывается, используй резерв только как запасной вариант.
        </div>
      </div>
      {qr_html}
    </section>
  </main>
</body>
</html>"""


async def send_connect_bundle_to_chat(
    bot: Bot,
    chat_id: int,
    *,
    main_link: str,
    fallback_link: str = "",
    context: str,
    title: str = "подключение",
    lead_text: str | None = None,
    show_main_menu: bool = True,
) -> None:
    await bot.send_photo(
        chat_id,
        photo=BufferedInputFile(
            _render_connect_bundle_qr(main_link),
            filename="ghost-access-connect-qr.png",
        ),
        caption=_build_connect_bundle_caption(
            main_link=main_link,
            fallback_link=fallback_link,
            title=title,
            lead_text=lead_text,
        ),
        parse_mode="HTML",
        reply_markup=build_connect_delivery_menu(
            context,
            has_fallback=bool(fallback_link),
            show_main_menu=show_main_menu,
        ),
    )


async def send_config_with_qr(message: Message, main_link: str, fallback_link: str) -> None:
    await send_qr_card(message, "основной профиль", main_link)
    if fallback_link:
        await send_qr_card(message, fallback_profile_title(), fallback_link)


def build_v2rayn_profile(user_uuid: str) -> str:
    reality = load_reality_profile()
    profile = {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "tag": "socks",
                "port": 10808,
                "listen": "127.0.0.1",
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True},
            },
            {
                "tag": "http",
                "port": 10809,
                "listen": "127.0.0.1",
                "protocol": "http",
                "settings": {},
            },
        ],
        "outbounds": [
            {
                "tag": "proxy",
                "protocol": "vless",
                "settings": {
                    "vnext": [
                        {
                            "address": PROFILE_VPN_SERVER,
                            "port": VPN_PORT,
                            "users": [
                                {
                                    "id": user_uuid,
                                    "encryption": "none",
                                    "flow": reality["flow"],
                                }
                            ],
                        }
                    ]
                },
                "streamSettings": {
                    "network": reality["type"],
                    "security": "reality",
                    "realitySettings": {
                        "show": False,
                        "fingerprint": reality["fingerprint"],
                        "serverName": reality["server_name"],
                        "publicKey": reality["public_key"],
                        "shortId": reality["short_id"],
                        "spiderX": "/",
                        "padding": 1,
                    },
                    "tcpSettings": {
                        "header": {"type": "none"},
                        "noDelay": True,
                        "keepAliveInterval": 0,
                        "connectionReuse": True,
                        "mark": 255,
                    },
                },
            },
            {"tag": "direct", "protocol": "freedom", "settings": {}},
            {"tag": "block", "protocol": "blackhole", "settings": {}},
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [
                {"type": "field", "ip": ["geoip:private"], "outboundTag": "direct"},
                {"type": "field", "network": "tcp,udp", "outboundTag": "proxy"},
            ],
        },
    }
    return json.dumps(profile, ensure_ascii=False, indent=2)


async def send_v2rayn_profile(message: Message, user: dict) -> None:
    primary = sync_primary_device(user["user_id"])
    target_uuid = primary["vpn_uuid"] if primary else user["vpn_uuid"]
    profile_json = build_v2rayn_profile(target_uuid)
    filename = f"ghost-access-{user['user_id']}.json"
    await message.answer_document(
        document=BufferedInputFile(profile_json.encode("utf-8"), filename=filename),
        caption=(
            "Готовый JSON-файл для основного профиля. "
            "Импортируй его через «Импорт из файла»."
        ),
        reply_markup=build_post_config_menu(),
    )
    await message.answer(
        render_transport_bundle_text(
            target_uuid,
            base_label=BOT_BRAND,
            include_fallbacks=EXPOSE_FALLBACK_TRANSPORTS,
        ),
        reply_markup=build_post_config_menu(),
    )


def render_repair_response(kind: str, user: dict | None) -> str:
    if not user:
        return render_inactive_subscription_text()

    main_link, fallback_link = get_user_links(user)
    fallback_available = bool(fallback_link)

    if kind == "no_connect":
        if not fallback_available:
            return (
                f"{BOT_BRAND}\n\n"
                "Не подключается\n\n"
                "1. Выключи профиль в приложении\n"
                "2. Удали старый профиль\n"
                "3. Импортируй этот профиль заново:\n\n"
                f"`{main_link}`"
            )
        return (
            f"{BOT_BRAND}\n\n"
            "Не подключается\n\n"
            "1. Выключи профиль в приложении\n"
            f"2. Попробуй операторский резерв {SECONDARY_VPN_PORT}:\n\n"
            f"`{fallback_link}`\n\n"
            "Не помогло? Импортируй основной заново."
        )
    if kind == "no_sites":
        if not fallback_available:
            return (
                f"{BOT_BRAND}\n\n"
                "Подключение есть, сайты не грузятся\n\n"
                "1. Перезапусти профиль в приложении\n"
                "2. Проверь /status\n"
                "3. Импортируй профиль заново:\n\n"
                f"`{main_link}`"
            )
        return (
            f"{BOT_BRAND}\n\n"
            "Подключение есть, сайты не грузятся\n\n"
            "1. Перезапусти профиль в приложении\n"
            "2. Проверь /status\n"
            f"3. Попробуй операторский резерв {SECONDARY_VPN_PORT}:\n\n"
            f"`{fallback_link}`"
        )
    if kind == "mobile":
        if not fallback_available:
            return (
                f"{BOT_BRAND}\n\n"
                "Wi-Fi работает, мобильная сеть нет (или наоборот)\n\n"
                "1. Удали профиль\n"
                "2. Импортируй основной профиль заново\n"
                "3. Если не помогло — это уже операторская диагностика, напиши админу."
            )
        return (
            f"{BOT_BRAND}\n\n"
            "Wi-Fi работает, мобильная сеть нет (или наоборот)\n\n"
            f"Попробуй операторский резерв {SECONDARY_VPN_PORT}:\n\n"
            f"`{fallback_link}`"
        )
    if kind == "gemini":
        lines = [
            f"{BOT_BRAND}\n\nGemini / Google AI\n",
            "Серверный маршрут проверен. Для Gemini чаще всего решает именно режим клиента.\n",
            "Android:\n"
            "1. Лучше Hiddify; в v2rayNG обязательно включи VPN / TUN для всех приложений\n"
            "2. Убери split tunneling и bypass-списки для Google, Gemini, Chrome и Google Play Services\n"
            "3. Переподключи профиль\n"
            "4. Очисти кэш Gemini и Google, затем открой снова\n",
            "iPhone / iPad:\n"
            "1. Happ / Streisand / Shadowrocket должны работать как полный VPN\n"
            "2. Не оставляй bypass для Safari / Google / Gemini\n",
            "Если нужен новый профиль, импортируй этот:\n",
            f"`{main_link}`",
        ]
        if fallback_available:
            lines.extend(
                [
                    "",
                    f"Если мобильный оператор режет основной порт, попробуй резерв {SECONDARY_VPN_PORT}:",
                    "",
                    f"`{fallback_link}`",
                ]
            )
        return "\n".join(lines)
    return f"{BOT_BRAND}\n\nТвой профиль:\n\n`{main_link}`"


async def send_subscription_card(message: Message, user: dict) -> None:
    await message.answer(
        render_subscription_text(user),
        parse_mode="HTML",
        reply_markup=build_post_config_menu(),
    )


async def send_subscription_bundle(message: Message, user: dict) -> None:
    delivery_url = build_delivery_connect_url(user)
    fallback_link = ""
    title = "подключение"
    lead_text_prefix = ""
    if not is_android_stealth_profile(user):
        _, fallback_link = get_user_links(user)
    else:
        title = "android stealth"
        lead_text_prefix = "Android-only bundle. Foreign apps идут через SPB, остальные остаются direct. "
    expires_at = parse_expires_at(user.get("expires_at"))
    expiry_text = expires_at.strftime("%d.%m.%Y %H:%M") if expires_at else "—"
    await send_connect_bundle(
        message,
        main_link=delivery_url,
        fallback_link=fallback_link,
        context="subscription",
        title=title,
        lead_text=f"{lead_text_prefix}Доступ до {expiry_text}.",
        show_main_menu=True,
    )


async def send_subscription_bundle_to_user(bot: Bot, user: dict) -> None:
    delivery_url = build_delivery_connect_url(user)
    fallback_link = ""
    title = "подключение"
    lead_text_prefix = ""
    if not is_android_stealth_profile(user):
        _, fallback_link = get_user_links(user)
    else:
        title = "android stealth"
        lead_text_prefix = "Android-only bundle. Foreign apps идут через SPB, остальные остаются direct. "
    expires_at = parse_expires_at(user.get("expires_at"))
    expiry_text = expires_at.strftime("%d.%m.%Y %H:%M") if expires_at else "—"
    await send_connect_bundle_to_chat(
        bot,
        int(user["user_id"]),
        main_link=delivery_url,
        fallback_link=fallback_link,
        context="subscription",
        title=title,
        lead_text=f"{lead_text_prefix}Доступ до {expiry_text}.",
        show_main_menu=True,
    )


async def send_device_connect_bundle(
    message: Message,
    device: dict,
    *,
    share_mode: bool = False,
) -> None:
    main_link, fallback_link = get_device_links(device)
    title = device["device_name"]
    lead_text = (
        f"Это подключение для: {device['device_name']}."
        if share_mode
        else f"Устройство: {device['device_name']}."
    )
    await send_connect_bundle(
        message,
        main_link=main_link,
        fallback_link=fallback_link,
        context=f"device:{int(device['device_id'])}",
        title=title,
        lead_text=lead_text,
        show_main_menu=not share_mode,
    )


def render_repair_failed_text(user: dict | None, user_id: int) -> str:
    return render_support_escalation_text(user, user_id)


def render_start_text(user_id: int) -> str:
    summary = render_state_summary(user_id, pending_prefix="У тебя есть неоплаченная заявка")

    if summary["state"] == "new":
        return (
            f"{BOT_BRAND}\n\n"
            "Персональный профиль подключения и управление подпиской.\n\n"
            "Быстрый старт:\n"
            f"1. Возьми {TRIAL_CTA_TEXT.lower()} или оформи подписку\n"
            "2. Нажми «Подключить»\n"
            "3. Импортируй QR или ссылку в приложение\n\n"
            "Нажимая «Попробовать», ты принимаешь /terms."
            f"{summary['pending_hint']}"
        )
    if summary["state"] == "trial_active":
        return (
            f"{BOT_BRAND}\n\n"
            f"Тест активен до {summary['expiry']}.\n\n"
            "Жми «Подключить» — пришлю QR и ссылку.\n"
            "Всё работает? Оформи подписку, чтобы не потерять доступ."
            f"{summary['pending_hint']}"
        )
    if summary["state"] == "paid_active":
        return (
            f"{BOT_BRAND}\n\n"
            f"Подписка до {summary['expiry']} ({summary['time_left']}).\n\n"
            "Подключить — получить профиль\n"
            "Кабинет — устройства и настройки\n"
            "Помощь — если что-то сломалось"
            f"{summary['pending_hint']}"
        )
    return (
        f"{BOT_BRAND}\n\n"
        "Подписка закончилась.\n"
        "Доступ приостановлен.\n\n"
        "Жми «Купить подписку» — подключение вернётся сразу."
        f"{summary['pending_hint']}"
    )


@router.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject) -> None:
    logger.info(
        "incoming /start from chat_id=%s user_id=%s args=%r",
        message.chat.id,
        message.from_user.id,
        command.args,
    )
    args = (command.args or "").strip()

    if args.upper().startswith("OFFLINE-"):
        claim_code = args.upper()
        try:
            user = claim_operator_issued_subscription(
                message.from_user.id,
                message.from_user.username,
                claim_code,
            )
        except LookupError:
            await message.answer(
                f"{BOT_BRAND}\n\n"
                "Код подключения не найден.\n\n"
                "Проверь код или попроси оператора выдать новый.",
                reply_markup=build_main_menu(message.from_user.id),
            )
            return
        except ValueError as exc:
            if str(exc) == "already_claimed":
                await message.answer(
                    f"{BOT_BRAND}\n\n"
                    "Этот код уже привязан к другому Telegram-аккаунту.\n\n"
                    "Если это ошибка, напиши в поддержку.",
                    reply_markup=build_support_menu(),
                )
                return
            if str(exc) == "user_exists":
                await message.answer(
                    f"{BOT_BRAND}\n\n"
                    "К этому Telegram уже привязан аккаунт.\n\n"
                    "Чтобы не смешать две подписки, напиши в поддержку.",
                    reply_markup=build_support_menu(),
                )
                return
            raise
        except XrayError as exc:
            await message.answer(str(exc), reply_markup=build_support_menu())
            return

        log_activity(message.from_user.id, f"deeplink_offline_claim:{claim_code}")
        await message.answer(
            f"{BOT_BRAND}\n\n"
            "Подписка привязана к этому Telegram.\n"
            "Ниже отправляю ссылку для подключения.",
            reply_markup=build_post_config_menu(),
        )
        await send_subscription_bundle(message, user)
        return

    # Deeplink: /start support — from support-url header in subscription clients
    if args == "support":
        user_id = message.from_user.id
        _, user = get_user_state(user_id)
        await message.answer(
            render_support_escalation_text(user, user_id),
            reply_markup=build_support_menu(),
        )
        log_activity(user_id, "deeplink_support")
        return

    # Deeplink: /start renew — from expired subscription stubs
    if args == "renew":
        await message.answer(
            render_buy_text(message.from_user.id),
            reply_markup=build_buy_menu(message.from_user.id),
        )
        log_activity(message.from_user.id, "deeplink_renew")
        return

    if args.startswith("ref_"):
        referrer = args.removeprefix("ref_")
        start_text = render_start_text(message.from_user.id)
        if referrer.isdigit() and int(referrer) != message.from_user.id:
            recorded = record_referral_open(int(referrer), message.from_user.id)
            if recorded:
                start_text += (
                    "\n\nТебя пригласил друг. Если возьмёшь тест — ему +1 день. Если потом оплатишь подписку — ему ещё +7 дней."
                )
        await message.answer(
            start_text,
            reply_markup=build_main_menu(message.from_user.id),
        )
        return

    # Deeplink: /start bind_<TOKEN> — from Landing (VPN IP detection)
    if args.startswith("bind_"):
        token = args.removeprefix("bind_")
        record = get_offline_subscription_by_token(token)
        if not record:
            await message.answer(
                f"{BOT_BRAND}\n\n"
                "Код привязки недействителен или истёк.\n\n"
                "Попроси выдать новый код или открой личный кабинет ещё раз.",
                reply_markup=build_main_menu(message.from_user.id),
            )
            return
        try:
            user = claim_operator_issued_subscription(
                message.from_user.id,
                message.from_user.username,
                str(record["claim_code"]),
            )
        except LookupError:
            await message.answer(
                f"{BOT_BRAND}\n\n"
                "Код привязки не найден.\n\n"
                "Проверь ссылку или попроси выдать новый код.",
                reply_markup=build_main_menu(message.from_user.id),
            )
            return
        except ValueError as exc:
            if str(exc) == "already_claimed":
                await message.answer(
                    f"{BOT_BRAND}\n\n"
                    "Этот код уже привязан к другому Telegram-аккаунту.\n\n"
                    "Если это ошибка, напиши в поддержку.",
                    reply_markup=build_support_menu(),
                )
                return
            if str(exc) == "user_exists":
                await message.answer(
                    f"{BOT_BRAND}\n\n"
                    "К этому Telegram уже привязан аккаунт.\n\n"
                    "Чтобы не смешать две подписки, напиши в поддержку.",
                    reply_markup=build_support_menu(),
                )
                return
            raise
        except XrayError as exc:
            await message.answer(str(exc), reply_markup=build_support_menu())
            return

        log_activity(message.from_user.id, f"ip_bind_claimed:{token}")
        await message.answer(
            f"{BOT_BRAND}\n\n"
            "Подписка привязана к этому Telegram.\n"
            "Ниже отправляю ссылку для подключения.",
            reply_markup=build_post_config_menu(),
        )
        await send_subscription_bundle(message, user)
        return

    # Phase 1: Entry Point Router
    text, reply_markup = await onboarding_logic.route_start(message.from_user.id)
    active_user = get_active_user(message.from_user.id)
    if active_user:
        await send_subscription_bundle(message, active_user)
        return
    await message.answer(text, reply_markup=reply_markup)


@router.message(Command("bind"))
async def cmd_bind(message: Message, command: CommandObject) -> None:
    logger.info("incoming /bind from chat_id=%s user_id=%s", message.chat.id, message.from_user.id)
    if not command.args:
        await message.answer("Использование: /bind <код_привязки>\nЭтот код можно получить в Личном кабинете на сайте.")
        return

    token = command.args.strip()
    record = get_offline_subscription_by_token(token)
    if not record:
        await message.answer(
            f"{BOT_BRAND}\n\n"
            "Код привязки недействителен или истёк.",
            reply_markup=build_main_menu(message.from_user.id),
        )
        return

    try:
        user = claim_operator_issued_subscription(
            message.from_user.id,
            message.from_user.username,
            str(record["claim_code"]),
        )
    except LookupError:
        await message.answer(
            f"{BOT_BRAND}\n\n"
            "Код привязки не найден.",
            reply_markup=build_main_menu(message.from_user.id),
        )
        return
    except ValueError as exc:
        if str(exc) == "already_claimed":
            await message.answer(
                f"{BOT_BRAND}\n\n"
                "Этот код уже привязан к другому Telegram-аккаунту.",
                reply_markup=build_support_menu(),
            )
            return
        if str(exc) == "user_exists":
            await message.answer(
                f"{BOT_BRAND}\n\n"
                "К этому Telegram уже привязан аккаунт.",
                reply_markup=build_support_menu(),
            )
            return
        raise
    except XrayError as exc:
        await message.answer(str(exc), reply_markup=build_support_menu())
        return

    log_activity(message.from_user.id, f"ip_bind_claimed:{token}")
    await message.answer(
        f"{BOT_BRAND}\n\n"
        "Подписка привязана к этому Telegram.\n"
        "Ниже отправляю ссылку для подключения.",
        reply_markup=build_post_config_menu(),
    )
    await send_subscription_bundle(message, user)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    logger.info("incoming /help from chat_id=%s user_id=%s", message.chat.id, message.from_user.id)
    await message.answer(render_help_text(), reply_markup=build_main_menu(message.from_user.id))


@router.message(Command("account"))
async def cmd_account(message: Message) -> None:
    logger.info(
        "incoming /account from chat_id=%s user_id=%s", message.chat.id, message.from_user.id
    )
    await message.answer(
        render_account_text(message.from_user.id),
        reply_markup=build_account_menu(message.from_user.id),
    )


@router.message(Command("trial"))
async def cmd_trial(message: Message) -> None:
    logger.info("incoming /trial from chat_id=%s user_id=%s", message.chat.id, message.from_user.id)
    if not await enforce_rate_limit(message, "trial"):
        return
    if not check_xray_port_alive():
        await message.answer(
            f"{BOT_BRAND}\n\n"
            "Сервер временно недоступен. Попробуй через пару минут.\n"
            "Если проблема повторяется — напиши /repair.",
        )
        logger.warning("cmd_trial: xray port %d unreachable, blocked profile delivery", VPN_PORT)
        return
    try:
        user = ensure_user_trial(message.from_user.id, message.from_user.username)
    except XrayError as exc:
        await message.answer(str(exc))
        return
    if not user:
        await message.answer(
            f"{BOT_BRAND}\n\n"
            "Тест уже был. Повторно не выдаётся.\n\n"
            "Подписка от 149₽/мес — до 5 устройств.\n"
            "Выбери тариф ниже.",
            reply_markup=build_buy_menu(message.from_user.id),
        )
        return
    await send_subscription_bundle(message, user)


@router.message(Command("config"))
async def cmd_config(message: Message) -> None:
    logger.info(
        "incoming /config from chat_id=%s user_id=%s", message.chat.id, message.from_user.id
    )
    if not await enforce_rate_limit(message, "config"):
        return
    user = get_active_user(message.from_user.id)
    if not user:
        await message.answer(
            render_inactive_subscription_text(),
            reply_markup=build_main_menu(message.from_user.id),
        )
        return
    if not check_xray_port_alive():
        await message.answer(
            f"{BOT_BRAND}\n\n"
            "Сервер временно недоступен. Попробуй через пару минут.\n"
            "Если проблема повторяется — напиши /repair.",
        )
        logger.warning("cmd_config: xray port %d unreachable, blocked profile delivery", VPN_PORT)
        return

    await send_subscription_bundle(message, user)


@router.message(Command("json"))
async def cmd_json(message: Message) -> None:
    logger.info("incoming /json from chat_id=%s user_id=%s", message.chat.id, message.from_user.id)
    if not await enforce_rate_limit(message, "json"):
        return
    user = get_active_user(message.from_user.id)
    if not user:
        await message.answer(render_inactive_subscription_text())
        return
    if not check_xray_port_alive():
        await message.answer(
            f"{BOT_BRAND}\n\n"
            "Сервер временно недоступен. Попробуй через пару минут.\n"
            "Если проблема повторяется — напиши /repair.",
        )
        logger.warning("cmd_json: xray port %d unreachable, blocked profile delivery", VPN_PORT)
        return
    await send_v2rayn_profile(message, user)


@router.message(Command("sub"))
async def cmd_sub(message: Message) -> None:
    logger.info("incoming /sub from chat_id=%s user_id=%s", message.chat.id, message.from_user.id)
    if not await enforce_rate_limit(message, "sub"):
        return
    user = get_active_user(message.from_user.id)
    if not user:
        await message.answer(render_inactive_subscription_text())
        return
    if not check_xray_port_alive():
        await message.answer(
            f"{BOT_BRAND}\n\n"
            "Сервер временно недоступен. Попробуй через пару минут.\n"
            "Если проблема повторяется — напиши /repair.",
        )
        logger.warning("cmd_sub: xray port %d unreachable, blocked profile delivery", VPN_PORT)
        return
    await send_subscription_card(message, user)
    await send_subscription_bundle(message, user)


@router.message(Command("devices"))
async def cmd_devices(message: Message) -> None:
    logger.info(
        "incoming /devices from chat_id=%s user_id=%s", message.chat.id, message.from_user.id
    )
    await message.answer(
        render_devices_text(message.from_user.id),
        reply_markup=build_devices_menu(message.from_user.id),
    )


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    logger.info(
        "incoming /status from chat_id=%s user_id=%s", message.chat.id, message.from_user.id
    )
    await message.answer(
        render_status_text(message.from_user.id),
        reply_markup=build_main_menu(message.from_user.id),
    )


@router.message(Command("whoami"))
async def cmd_whoami(message: Message) -> None:
    logger.info(
        "incoming /whoami from chat_id=%s user_id=%s", message.chat.id, message.from_user.id
    )
    await message.answer(
        f"Твой ID: <code>{message.from_user.id}</code>",
        parse_mode="HTML",
        reply_markup=build_support_menu(),
    )


@router.message(Command("buy"))
async def cmd_buy(message: Message) -> None:
    logger.info("incoming /buy from chat_id=%s user_id=%s", message.chat.id, message.from_user.id)
    await message.answer(
        render_buy_text(message.from_user.id), reply_markup=build_buy_menu(message.from_user.id)
    )


@router.message(Command("payments"))
async def cmd_payments(message: Message) -> None:
    logger.info(
        "incoming /payments from chat_id=%s user_id=%s", message.chat.id, message.from_user.id
    )
    await message.answer(
        render_user_payments_text(message.from_user.id),
        reply_markup=build_user_payments_menu(message.from_user.id),
    )


@router.message(Command("invite"))
async def cmd_invite(message: Message) -> None:
    logger.info(
        "incoming /invite from chat_id=%s user_id=%s", message.chat.id, message.from_user.id
    )
    if not await enforce_rate_limit(message, "invite"):
        return
    await message.answer(
        render_invite_text(message.from_user.id),
        reply_markup=build_invite_menu(message.from_user.id),
    )


@router.message(Command("rewards"))
async def cmd_rewards(message: Message) -> None:
    logger.info(
        "incoming /rewards from chat_id=%s user_id=%s", message.chat.id, message.from_user.id
    )
    await message.answer(
        render_rewards_text(message.from_user.id),
        reply_markup=build_invite_menu(message.from_user.id),
    )


@router.message(Command("guide"))
async def cmd_guide(message: Message) -> None:
    logger.info("incoming /guide from chat_id=%s user_id=%s", message.chat.id, message.from_user.id)
    await message.answer(render_guide_intro(), reply_markup=build_guide_menu())


@router.message(Command("terms"))
async def cmd_terms(message: Message) -> None:
    await message.answer(
        f"{BOT_BRAND} — Условия использования\n\n"
        "1. Сервис предоставляет защищённый доступ в интернет.\n"
        "2. Подписка привязана к Telegram-аккаунту.\n"
        "3. Передавать доступ третьим лицам запрещено "
        "(кроме устройств в рамках семейного плана).\n"
        "4. Сервис не гарантирует 100% uptime, "
        "но стремится к максимальной доступности.\n"
        "5. Возврат средств возможен в течение 3 дней после оплаты, "
        "если сервис не работал по нашей вине.\n"
        "6. Мы не храним логи вашего трафика.\n"
        "7. Мы оставляем за собой право заблокировать аккаунт "
        "при нарушении условий.\n"
        "8. Продолжая использовать сервис, вы принимаете эти условия.\n\n"
        "Вопросы: /help",
        reply_markup=build_main_menu(message.from_user.id),
    )


@router.message(Command("privacy"))
async def cmd_privacy(message: Message) -> None:
    await message.answer(
        f"{BOT_BRAND} — Политика конфиденциальности\n\n"
        "Какие данные мы храним:\n"
        "• Telegram user ID\n"
        "• Имя профиля Telegram (для отображения)\n"
        "• Дата регистрации и оплат\n"
        "• Список устройств (тип, User-Agent)\n"
        "• IP-адрес последнего подключения к подписке\n\n"
        "Какие данные мы НЕ храним:\n"
        "• Историю посещений сайтов\n"
        "• Содержимое трафика\n"
        "• DNS-запросы\n\n"
        "Данные платежей обрабатываются провайдером "
        "(ЮKassa / YooMoney / CardLink) и не хранятся у нас.\n\n"
        "Удалить все данные: /deleteme\n"
        "Вопросы: /help",
        reply_markup=build_main_menu(message.from_user.id),
    )


@router.message(Command("deleteme"))
async def cmd_deleteme(message: Message) -> None:
    user_id = message.from_user.id
    _, user = get_user_state(user_id)
    if not user:
        await message.answer("У тебя нет аккаунта в системе.")
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="Да, удалить все данные", callback_data="confirm_delete_account")
    kb.button(text="Отмена", callback_data="menu")
    kb.adjust(1)
    await message.answer(
        f"{BOT_BRAND}\n\n"
        "Удаление аккаунта\n\n"
        "Будут удалены:\n"
        "• Профиль и подписка\n"
        "• Все устройства и доступ\n"
        "• История активности\n\n"
        "История платежей будет обезличена (для бухгалтерии).\n\n"
        "Это действие необратимо.",
        reply_markup=kb.as_markup(),
    )


@router.message(Command("faq"))
async def cmd_faq(message: Message) -> None:
    await message.answer(
        f"{BOT_BRAND} — Частые вопросы\n\n"
        "Не подключается?\n"
        "→ /repair — пошаговая диагностика\n\n"
        "Как подключить ребёнка/семью?\n"
        "→ /devices → Добавить устройство → Поделиться\n\n"
        "Как продлить подписку?\n"
        "→ /buy — дни прибавятся к текущему сроку\n\n"
        "Как сменить устройство?\n"
        "→ /devices → выбери устройство → Заменить\n\n"
        "Работает на Wi-Fi, не работает на мобильной сети?\n"
        "→ /repair → выбери этот сценарий\n\n"
        "Какое приложение скачать?\n"
        "→ /guide — инструкция для каждой платформы\n\n"
        "Как удалить аккаунт?\n"
        "→ /deleteme\n\n"
        "Условия и конфиденциальность:\n"
        "→ /terms  /privacy",
        reply_markup=build_main_menu(message.from_user.id),
    )


@router.message(Command("repair"))
async def cmd_repair(message: Message) -> None:
    logger.info(
        "incoming /repair from chat_id=%s user_id=%s", message.chat.id, message.from_user.id
    )
    if not await enforce_rate_limit(message, "repair"):
        return
    await message.answer(render_repair_intro(), reply_markup=build_repair_menu())


@router.message(Command("ping"))
async def cmd_ping(message: Message) -> None:
    """Quick status check — shows subscription state and server reachability."""
    logger.info("incoming /ping from chat_id=%s user_id=%s", message.chat.id, message.from_user.id)
    user_id = message.from_user.id
    state, user = get_user_state(user_id)
    summary = render_state_summary(user_id)
    devices = list_user_devices(user_id) if user else []
    active_devices = [d for d in devices if d.get("status") == "active"]
    server_alive = check_xray_port_alive()
    server_status = "доступен" if server_alive else "недоступен"

    await message.answer(
        f"{BOT_BRAND}\n\n"
        f"{summary['headline']}\n"
        f"Тариф: {summary['plan']}\n"
        f"Осталось: {summary['time_left']}\n"
        f"Устройств: {len(active_devices)}/{get_device_limit(user)}\n"
        f"Сервер: {server_status}\n\n"
        f"{summary['next_step']}",
        reply_markup=build_main_menu(user_id),
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    logger.info("incoming /stats from chat_id=%s user_id=%s", message.chat.id, message.from_user.id)
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администратору.")
        return

    stats = get_user_stats()
    referral_stats = get_global_referral_stats()
    open_to_trial = (
        (referral_stats["trial"] / referral_stats["opens"]) * 100
        if referral_stats["opens"]
        else 0.0
    )
    trial_to_paid = (
        (referral_stats["paid"] / referral_stats["trial"]) * 100 if referral_stats["trial"] else 0.0
    )
    open_to_paid = (
        (referral_stats["paid"] / referral_stats["opens"]) * 100 if referral_stats["opens"] else 0.0
    )
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE expires_at > datetime('now') AND plan != 'trial'"
        )
        paid_active = cursor.fetchone()["cnt"]
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE expires_at > datetime('now') AND plan = 'trial'"
        )
        trial_active = cursor.fetchone()["cnt"]
        cursor.execute("SELECT COUNT(*) as cnt FROM devices WHERE status = 'active'")
        active_devices = cursor.fetchone()["cnt"]

    await message.answer(
        f"{BOT_BRAND} — Статистика\n\n"
        f"Всего пользователей: {stats['total_users']}\n"
        f"Активных (trial): {trial_active}\n"
        f"Активных (платных): {paid_active}\n"
        f"Устройств (active): {active_devices}\n"
        f"Выручка: {stats['total_revenue']:.0f} ₽\n\n"
        f"Рефералы — открытий: {referral_stats['opens']}\n"
        f"Рефералы — trial: {referral_stats['trial']}\n"
        f"Рефералы — оплат: {referral_stats['paid']}\n"
        f"Рефералы — бонусных дней: {referral_stats['bonus_days']}\n"
        f"Рефералы — выручка: {referral_stats['revenue']:.0f} ₽\n"
        f"Воронка open→trial: {open_to_trial:.0f}%\n"
        f"Воронка trial→paid: {trial_to_paid:.0f}%\n"
        f"Воронка open→paid: {open_to_paid:.0f}%\n\n"
        f"Кап бонусных дней: {REFERRAL_BONUS_CAP_DAYS}\n"
        f"Бонус за тест: +{REFERRAL_TRIAL_BONUS_DAYS} день\n"
        f"Бонус за оплату: +{REFERRAL_BONUS_DAYS} дней\n"
        f"{render_top_referrers_block()}\n\n"
        f"{render_recent_referrals_block()}\n\n"
        f"{render_payment_status_block()}\n\n"
        f"{render_rate_limit_block()}\n\n"
        f"{render_noisy_users_block()}\n\n"
        f"{render_suspicious_users_block()}\n",
        reply_markup=build_admin_menu(),
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    logger.info("incoming /admin from chat_id=%s user_id=%s", message.chat.id, message.from_user.id)
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администратору.")
        return
    await message.answer(render_admin_panel_text(), reply_markup=build_admin_menu())


@router.message(Command("admin_user"))
async def cmd_admin_user(message: Message, command: CommandObject) -> None:
    logger.info(
        "incoming /admin_user from chat_id=%s user_id=%s args=%r",
        message.chat.id,
        message.from_user.id,
        command.args,
    )
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администратору.")
        return
    args = (command.args or "").split()
    if len(args) != 1:
        await message.answer(render_admin_user_lookup_text(), reply_markup=build_admin_menu())
        return
    try:
        target_user_id = int(args[0])
    except ValueError:
        await message.answer(render_admin_user_lookup_text(), reply_markup=build_admin_menu())
        return
    await message.answer(
        render_admin_user_text(target_user_id),
        reply_markup=build_admin_user_menu(target_user_id),
    )


@router.message(Command("stats_abuse"))
async def cmd_stats_abuse(message: Message) -> None:
    logger.info(
        "incoming /stats_abuse from chat_id=%s user_id=%s", message.chat.id, message.from_user.id
    )
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администратору.")
        return
    await message.answer(render_abuse_stats_text(), reply_markup=build_admin_menu())


@router.message(Command("adminhelp"))
async def cmd_adminhelp(message: Message) -> None:
    logger.info(
        "incoming /adminhelp from chat_id=%s user_id=%s", message.chat.id, message.from_user.id
    )
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администратору.")
        return
    await message.answer(render_admin_help_text(), reply_markup=build_admin_menu())


@router.message(Command("revenue"))
async def cmd_revenue(message: Message) -> None:
    """Admin: revenue dashboard with MRR, churn, LTV."""
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администратору.")
        return

    now = datetime.now()
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Revenue this month
        month_start = now.replace(day=1, hour=0, minute=0, second=0)
        cursor.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM payments "
            "WHERE payment_status IN ('completed', 'approved') AND payment_date >= ?",
            (month_start.isoformat(),),
        )
        mrr = cursor.fetchone()["total"]

        # Revenue last month
        last_month_end = month_start - timedelta(seconds=1)
        last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0)
        cursor.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM payments "
            "WHERE payment_status IN ('completed', 'approved') AND payment_date >= ? AND payment_date < ?",
            (last_month_start.isoformat(), month_start.isoformat()),
        )
        last_mrr = cursor.fetchone()["total"]

        # Total revenue all time
        cursor.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM payments "
            "WHERE payment_status IN ('completed', 'approved')"
        )
        total_revenue = cursor.fetchone()["total"]

        # Paid active users
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE expires_at > datetime('now') AND plan != 'trial'"
        )
        paid_active = cursor.fetchone()["cnt"]

        # Total paying users ever
        cursor.execute(
            "SELECT COUNT(DISTINCT user_id) as cnt FROM payments "
            "WHERE payment_status IN ('completed', 'approved') AND user_id > 0"
        )
        total_paid_ever = cursor.fetchone()["cnt"]

        # Churned this month (expired, were paid)
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM users "
            "WHERE expires_at > ? AND expires_at <= ? AND plan != 'trial'",
            (last_month_start.isoformat(), now.isoformat()),
        )
        churned = cursor.fetchone()["cnt"]

        # Trial conversions this month
        cursor.execute(
            "SELECT COUNT(DISTINCT user_id) as cnt FROM payments "
            "WHERE payment_status IN ('completed', 'approved') AND payment_date >= ?",
            (month_start.isoformat(),),
        )
        new_paid = cursor.fetchone()["cnt"]

        # Revenue by plan
        cursor.execute(
            "SELECT payment_provider, COALESCE(SUM(amount), 0) as total, COUNT(*) as cnt "
            "FROM payments WHERE payment_status IN ('completed', 'approved') AND payment_date >= ? "
            "GROUP BY payment_provider ORDER BY total DESC",
            (month_start.isoformat(),),
        )
        by_provider = cursor.fetchall()

    # LTV = total revenue / total paying users
    ltv = total_revenue / total_paid_ever if total_paid_ever else 0
    # Churn rate
    churn_base = paid_active + churned
    churn_rate = (churned / churn_base * 100) if churn_base else 0
    # MRR delta
    mrr_delta = mrr - last_mrr
    delta_sign = "+" if mrr_delta >= 0 else ""

    lines = [
        f"{BOT_BRAND} — Доходы\n",
        f"Этот месяц: {mrr:.0f} ₽ ({delta_sign}{mrr_delta:.0f} vs прошлый)",
        f"Прошлый месяц: {last_mrr:.0f} ₽",
        f"Всего за всё время: {total_revenue:.0f} ₽\n",
        f"Платящих сейчас: {paid_active}",
        f"Новых платящих в этом месяце: {new_paid}",
        f"Ушли (churn): {churned} ({churn_rate:.0f}%)",
        f"LTV (средний доход/юзер): {ltv:.0f} ₽\n",
    ]
    if by_provider:
        lines.append("По провайдерам (этот месяц):")
        for row in by_provider:
            prov = (row["payment_provider"] or "unknown").split(":")[0].split("_")[0]
            lines.append(f"  {prov}: {row['total']:.0f} ₽ ({row['cnt']} платежей)")

    await message.answer("\n".join(lines), reply_markup=build_admin_menu())


@router.message(Command("activate"))
async def cmd_activate(message: Message, command: CommandObject) -> None:
    logger.info(
        "incoming /activate from chat_id=%s user_id=%s args=%r",
        message.chat.id,
        message.from_user.id,
        command.args,
    )
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администратору.")
        return

    target_user_id, plan_key = parse_activate_args(command.args)
    if target_user_id is None and plan_key is None:
        await message.answer(render_admin_usage())
        return

    if target_user_id is None:
        await message.answer("user_id должен быть числом.\n\n" + render_admin_usage())
        return

    if plan_key not in PLANS:
        await message.answer("Неизвестный план.\n\n" + render_admin_usage())
        return

    try:
        activated_user = activate_paid_plan(
            target_user_id,
            None,
            plan_key,
            provider="admin_grant",
            record_billing=False,
            reward_referral=False,
        )
    except XrayError as exc:
        await message.answer(f"Ошибка xray: {exc}")
        return
    expires_at = parse_expires_at(activated_user.get("expires_at"))
    plan_label = render_plan_label(plan_key)
    await message.answer(
        f"Активировано: user_id={target_user_id}\n"
        f"План: {plan_label}\n"
        f"Активно до: {expires_at.strftime('%d.%m.%Y %H:%M') if expires_at else 'unknown'}",
        reply_markup=build_admin_menu(),
    )
    try:
        await message.bot.send_message(
            target_user_id,
            f"{BOT_BRAND}: подписка продлена.\n"
            f"План: {plan_label}\n"
            f"Активно до: {expires_at.strftime('%d.%m.%Y %H:%M') if expires_at else 'unknown'}\n\n"
            "Открой /config, чтобы получить актуальный QR-профиль.",
        )
    except Exception as exc:
        logger.warning("failed to notify activated user_id=%s: %s", target_user_id, exc)


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, command: CommandObject) -> None:
    """Admin: send message to users. Usage: /broadcast [audience] text
    audience: all (default), active, paid, trial, expired
    """
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администратору.")
        return

    raw = (command.args or "").strip()
    if not raw:
        await message.answer(
            "Использование: /broadcast [аудитория] текст\n\n"
            "Аудитории: all, active, paid, trial, expired\n"
            "Пример: /broadcast active Обновление сервера в 03:00"
        )
        return

    parts = raw.split(None, 1)
    audiences = {"all", "active", "paid", "trial", "expired"}
    if len(parts) >= 2 and parts[0].lower() in audiences:
        audience = parts[0].lower()
        text = parts[1]
    else:
        audience = "all"
        text = raw

    user_ids = get_broadcast_user_ids(audience)
    if not user_ids:
        await message.answer(f"Аудитория «{audience}» пуста.")
        return

    await message.answer(f"Рассылка ({audience}): {len(user_ids)} получателей. Отправляю...")

    sent, failed, blocked = 0, 0, 0
    for uid in user_ids:
        try:
            await message.bot.send_message(uid, f"{BOT_BRAND}\n\n{text}")
            sent += 1
        except Exception as exc:
            exc_str = str(exc).lower()
            if "blocked" in exc_str or "deactivated" in exc_str or "chat not found" in exc_str:
                blocked += 1
            else:
                failed += 1
            logger.debug("broadcast failed for %d: %s", uid, exc)
        if sent % 25 == 0:
            await asyncio.sleep(1)  # Telegram rate limit: ~30 msg/sec

    await message.answer(
        f"Рассылка завершена.\n\n"
        f"Отправлено: {sent}\n"
        f"Заблокировали бота: {blocked}\n"
        f"Ошибки: {failed}"
    )
    log_activity(message.from_user.id, f"broadcast_{audience}_{sent}")


@router.message(Command("refund"))
async def cmd_refund(message: Message, command: CommandObject) -> None:
    """Admin: refund a payment. Usage: /refund <payment_id> [reason]"""
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администратору.")
        return

    raw = (command.args or "").strip()
    if not raw:
        await message.answer("Использование: /refund <payment_id> [причина]")
        return

    parts = raw.split(None, 1)
    try:
        payment_id = int(parts[0])
    except ValueError:
        await message.answer("payment_id должен быть числом.")
        return
    reason = parts[1] if len(parts) > 1 else "admin refund"

    payment = get_payment(payment_id)
    if not payment:
        await message.answer(f"Платёж #{payment_id} не найден.")
        return

    if payment["payment_status"] == "refunded":
        await message.answer(f"Платёж #{payment_id} уже возвращён.")
        return

    update_payment_status(payment_id, "refunded")
    user_id = payment["user_id"]
    amount = payment.get("amount", 0)
    log_activity(message.from_user.id, f"admin_refund_{payment_id}_{user_id}_{reason}")

    await message.answer(
        f"Возврат оформлен.\n\n"
        f"Платёж: #{payment_id}\n"
        f"Пользователь: {user_id}\n"
        f"Сумма: {amount:.0f} ₽\n"
        f"Причина: {reason}\n\n"
        "Перевод пользователю нужно сделать вручную через провайдера.",
        reply_markup=build_admin_menu(),
    )

    try:
        await message.bot.send_message(
            user_id,
            f"{BOT_BRAND}\n\n"
            f"Возврат средств оформлен: {amount:.0f} ₽.\n"
            f"Причина: {reason}\n\n"
            "Средства поступят в течение 3-5 рабочих дней.",
        )
    except Exception:
        pass


@router.message(Command("promo"))
async def cmd_promo(message: Message, command: CommandObject) -> None:
    """Admin: manage promo codes.
    /promo — list active codes
    /promo create CODE days 7 [uses 100] [expires 2026-05-01]
    /promo create CODE plan basic_1m [uses 50]
    /promo delete CODE
    """
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администратору.")
        return

    raw = (command.args or "").strip()

    # List codes
    if not raw:
        codes = list_promo_codes()
        if not codes:
            await message.answer("Промокодов нет.")
            return
        lines = [f"{BOT_BRAND} — Промокоды\n"]
        for c in codes:
            exp = c.get("expires_at", "")[:10] if c.get("expires_at") else "∞"
            if c["promo_type"] == "days":
                val = f"+{c['value']} дн."
            else:
                val = f"план {c.get('plan_key', '?')}"
            lines.append(
                f"<code>{c['code']}</code> — {val}, "
                f"исп: {c['used_count']}/{c['max_uses']}, до: {exp}"
            )
        await message.answer("\n".join(lines), parse_mode="HTML")
        return

    tokens = raw.split()

    # Delete
    if tokens[0].lower() == "delete" and len(tokens) >= 2:
        code = tokens[1]
        if delete_promo_code(code):
            await message.answer(f"Промокод <code>{code}</code> удалён.", parse_mode="HTML")
        else:
            await message.answer("Промокод не найден.")
        return

    # Create
    if tokens[0].lower() == "create" and len(tokens) >= 4:
        code = tokens[1]
        promo_type = tokens[2].lower()
        max_uses = 1
        expires_at = None
        plan_key = None
        value = 0

        if promo_type == "days":
            value = int(tokens[3])
        elif promo_type == "plan":
            plan_key = tokens[3]
            if plan_key not in PLANS:
                await message.answer(f"Неизвестный план: {plan_key}")
                return
        else:
            await message.answer("Тип: days или plan")
            return

        # Parse optional params
        i = 4
        while i < len(tokens) - 1:
            key = tokens[i].lower()
            val_str = tokens[i + 1]
            if key == "uses":
                max_uses = int(val_str)
            elif key == "expires":
                expires_at = val_str + " 23:59:59"
            i += 2

        try:
            create_promo_code(
                code,
                promo_type=promo_type,
                value=value,
                plan_key=plan_key,
                max_uses=max_uses,
                expires_at=expires_at,
            )
        except Exception as exc:
            await message.answer(f"Ошибка: {exc}")
            return
        await message.answer(
            f"Промокод создан: <code>{code}</code>\n"
            f"Тип: {promo_type}, значение: {value or plan_key}\n"
            f"Лимит: {max_uses}, истекает: {expires_at or '∞'}",
            parse_mode="HTML",
        )
        return

    await message.answer(
        "Использование:\n"
        "/promo — список\n"
        "/promo create CODE days 7 [uses 100] [expires 2026-05-01]\n"
        "/promo create CODE plan basic_1m [uses 50]\n"
        "/promo delete CODE"
    )


@router.message(Command("redeem"))
async def cmd_redeem(message: Message, command: CommandObject) -> None:
    """User command: redeem a promo code. Usage: /redeem CODE"""
    code = (command.args or "").strip()
    if not code:
        await message.answer("Введи промокод: /redeem КОД")
        return

    user_id = message.from_user.id
    promo = redeem_promo_code(code, user_id)
    if not promo:
        await message.answer("Промокод недействителен, уже использован или истёк.")
        return

    if promo["promo_type"] == "days":
        bonus_days = promo["value"]
        _, user = get_user_state(user_id)
        if not user:
            await message.answer("Сначала нажми /start.")
            return
        current_expiry = parse_expires_at(user.get("expires_at"))
        now = datetime.now()
        base = current_expiry if current_expiry and current_expiry > now else now
        new_expiry = base + timedelta(days=bonus_days)
        update_user(user_id, expires_at=new_expiry)
        await message.answer(
            f"Промокод активирован! +{bonus_days} дней.\n"
            f"Подписка до: {new_expiry.strftime('%d.%m.%Y %H:%M')}",
            reply_markup=build_account_menu(user_id),
        )
        log_activity(user_id, f"promo_redeem_days_{code}_{bonus_days}")

    elif promo["promo_type"] == "plan":
        plan_key = promo.get("plan_key")
        if not plan_key or plan_key not in PLANS:
            await message.answer("Ошибка промокода (неизвестный план).")
            return
        try:
            activated = activate_paid_plan(
                user_id,
                None,
                plan_key,
                provider=f"promo:{code}",
                record_billing=False,
                reward_referral=False,
            )
        except Exception as exc:
            await message.answer(f"Ошибка активации: {exc}")
            return
        expires_at = parse_expires_at(activated.get("expires_at"))
        await message.answer(
            f"Промокод активирован! План: {render_plan_label(plan_key)}\n"
            f"Подписка до: {expires_at.strftime('%d.%m.%Y %H:%M') if expires_at else '?'}",
            reply_markup=build_account_menu(user_id),
        )
        log_activity(user_id, f"promo_redeem_plan_{code}_{plan_key}")


@router.callback_query()
async def handle_callback(callback: CallbackQuery) -> None:
    logger.info(
        "incoming callback=%s from chat_id=%s user_id=%s",
        callback.data,
        callback.message.chat.id if callback.message else "unknown",
        callback.from_user.id,
    )

    # Phase 1: Onboarding and Payment dispatcher
    if await onboarding_logic.handle_onboarding_callback(callback):
        await callback.answer()
        return

    if callback.data == "trial":
        if not await enforce_rate_limit(callback, "trial"):
            return
        if not check_xray_port_alive():
            await safe_edit(
                callback,
                f"{BOT_BRAND}\n\n"
                "Сервер временно недоступен. Попробуй через пару минут.\n"
                "Если проблема повторяется — напиши /repair.",
                reply_markup=build_main_menu(callback.from_user.id),
            )
            await callback.answer()
            logger.warning("callback trial: xray port %d unreachable", VPN_PORT)
            return
        try:
            user = ensure_user_trial(callback.from_user.id, callback.from_user.username)
        except XrayError as exc:
            await callback.message.answer(str(exc))
            await callback.answer()
            return
        if not user:
            await safe_edit(
                callback,
                f"{BOT_BRAND}\n\nТест уже использован.\n\nЖми «Купить подписку».",
                reply_markup=build_buy_menu(callback.from_user.id),
            )
            await callback.answer()
            return
        await send_subscription_bundle(callback.message, user)
        await callback.answer("Подключение отправлено")
    elif callback.data == "config":
        if not await enforce_rate_limit(callback, "config"):
            return
        user = get_active_user(callback.from_user.id)
        if not user:
            await safe_edit(
                callback,
                render_inactive_subscription_text(),
                reply_markup=build_main_menu(callback.from_user.id),
            )
        elif not check_xray_port_alive():
            await safe_edit(
                callback,
                f"{BOT_BRAND}\n\n"
                "Сервер временно недоступен. Попробуй через пару минут.\n"
                "Если проблема повторяется — напиши /repair.",
                reply_markup=build_main_menu(callback.from_user.id),
            )
            logger.warning("callback config: xray port %d unreachable", VPN_PORT)
        else:
            await send_subscription_bundle(callback.message, user)
            await callback.answer("Подключение отправлено")
    elif callback.data == "buy":
        await safe_edit(
            callback,
            render_buy_text(callback.from_user.id),
            reply_markup=build_buy_menu(callback.from_user.id),
        )
    elif callback.data == "upgrade":
        user_id = callback.from_user.id
        _, user = get_user_state(user_id)
        if not user:
            await safe_edit(
                callback, "Сначала активируй подписку.", reply_markup=build_main_menu(user_id)
            )
        else:
            current_plan = user.get("plan", "")
            expires_at = parse_expires_at(user.get("expires_at"))
            now = datetime.now()
            remaining_days = (
                max(0, (expires_at - now).days) if expires_at and expires_at > now else 0
            )
            current_amount = PLANS.get(current_plan, {}).get("amount", 0)
            current_days = PLANS.get(current_plan, {}).get("days", 30)
            daily_rate = current_amount / current_days if current_days else 0
            credit = daily_rate * remaining_days
            payment_provider = get_active_payment_provider()

            lines = [
                f"{BOT_BRAND}\n",
                "Сменить план\n",
                f"Текущий: {PLANS.get(current_plan, {}).get('label', current_plan)}",
                f"Осталось: {remaining_days} дн.",
                f"Остаток: ~{credit:.0f} ₽\n",
            ]
            builder = InlineKeyboardBuilder()
            plan_order = ["basic_1m", "basic_3m", "basic_6m", "basic_12m"]
            for pk in plan_order:
                if pk == current_plan:
                    continue
                plan = PLANS[pk]
                diff = plan["amount"] - credit
                if diff < 0:
                    diff = 0
                lines.append(
                    f"{plan['label']} — {plan['amount']} ₽ "
                    f"(доплата ~{diff:.0f} ₽, {plan['devices']} устр.)"
                )
                btn_text = f"{plan['label']} ({diff:.0f} ₽)"
                if payment_provider == "cardlink":
                    builder.button(text=btn_text, callback_data=f"buy:cardlink:{pk}")
                elif payment_provider == "yookassa":
                    builder.button(text=btn_text, callback_data=f"buy:yookassa:{pk}")
                elif payment_provider == "yoomoney":
                    payment_url = create_yoomoney_url(plan["amount"], user_id, pk)
                    if payment_url:
                        builder.button(text=btn_text, url=payment_url)
                    else:
                        builder.button(text=btn_text, callback_data="buy:manual")
                else:
                    builder.button(text=btn_text, callback_data="buy:manual")
            builder.button(text="Назад", callback_data="account")
            builder.adjust(1)
            await safe_edit(callback, "\n".join(lines), reply_markup=builder.as_markup())
    elif callback.data == "freeze":
        user_id = callback.from_user.id
        _, user = get_user_state(user_id)
        if not user or user.get("plan") == "trial":
            await safe_edit(
                callback,
                "Заморозка доступна только для платных подписок.",
                reply_markup=build_main_menu(user_id),
            )
        elif has_activity(user_id, "freeze_used"):
            await safe_edit(
                callback,
                f"{BOT_BRAND}\n\nЗаморозка уже использована в этом периоде.",
                reply_markup=build_account_menu(user_id),
            )
        else:
            kb = InlineKeyboardBuilder()
            for days in [7, 14, 30]:
                kb.button(text=f"Заморозить на {days} дн.", callback_data=f"freeze_confirm:{days}")
            kb.button(text="Отмена", callback_data="account")
            kb.adjust(1)
            await safe_edit(
                callback,
                f"{BOT_BRAND}\n\n"
                "Заморозка подписки\n\n"
                "Дата окончания сдвинется на выбранный срок.\n"
                "Подключение продолжит работать.\n"
                "Заморозить можно один раз за период подписки.",
                reply_markup=kb.as_markup(),
            )
    elif callback.data.startswith("freeze_confirm:"):
        freeze_days = int(callback.data.split(":")[1])
        user_id = callback.from_user.id
        _, user = get_user_state(user_id)
        if not user:
            await safe_edit(callback, "Ошибка.", reply_markup=build_main_menu(user_id))
        elif has_activity(user_id, "freeze_used"):
            await safe_edit(
                callback, "Заморозка уже использована.", reply_markup=build_account_menu(user_id)
            )
        else:
            expires_at = parse_expires_at(user.get("expires_at"))
            if not expires_at:
                await safe_edit(
                    callback, "Нет активной подписки.", reply_markup=build_main_menu(user_id)
                )
            else:
                new_expiry = expires_at + timedelta(days=freeze_days)
                update_user(user_id, expires_at=new_expiry)
                log_activity(user_id, "freeze_used")
                log_activity(user_id, f"freeze_{freeze_days}d")
                await safe_edit(
                    callback,
                    f"{BOT_BRAND}\n\n"
                    f"Подписка заморожена на {freeze_days} дней.\n"
                    f"Новая дата окончания: {new_expiry.strftime('%d.%m.%Y %H:%M')}",
                    reply_markup=build_account_menu(user_id),
                )
    elif callback.data == "sub":
        user = get_active_user(callback.from_user.id)
        if not user:
            await safe_edit(
                callback,
                render_inactive_subscription_text(),
                reply_markup=build_main_menu(callback.from_user.id),
            )
        else:
            await send_subscription_bundle(callback.message, user)
            await callback.answer("Подключение отправлено")
    elif callback.data == "subhelp:iphone":
        user = get_active_user(callback.from_user.id)
        if not user:
            await safe_edit(
                callback,
                render_inactive_subscription_text(),
                reply_markup=build_main_menu(callback.from_user.id),
            )
        else:
            await safe_edit(
                callback,
                render_subscription_iphone_help(callback.from_user.id),
                reply_markup=build_connect_delivery_menu(
                    "subscription",
                    has_fallback=bool(generate_fallback_link(user["vpn_uuid"])),
                    show_main_menu=True,
                ),
                parse_mode="HTML",
            )
    elif callback.data.startswith("connect:fallback:"):
        context = callback.data.removeprefix("connect:fallback:")
        if context == "subscription":
            user = get_active_user(callback.from_user.id)
            if not user:
                await safe_edit(
                    callback,
                    render_inactive_subscription_text(),
                    reply_markup=build_main_menu(callback.from_user.id),
                )
            else:
                _, fallback_link = get_user_links(user)
                await safe_edit(
                    callback,
                    render_connect_fallback_help(fallback_link),
                    reply_markup=build_connect_delivery_menu(
                        "subscription",
                        has_fallback=bool(fallback_link),
                        show_main_menu=True,
                    ),
                    parse_mode="HTML",
                )
        elif context.startswith("device:"):
            device_id = int(context.split(":", 1)[1])
            device = get_device(device_id)
            if (
                not device
                or device["user_id"] != callback.from_user.id
                or device.get("status") != "active"
            ):
                await safe_edit(
                    callback,
                    "Устройство недоступно.",
                    reply_markup=build_devices_menu(callback.from_user.id),
                )
            else:
                _, fallback_link = get_device_links(device)
                await safe_edit(
                    callback,
                    render_connect_fallback_help(fallback_link),
                    reply_markup=build_connect_delivery_menu(
                        f"device:{device_id}",
                        has_fallback=bool(fallback_link),
                        show_main_menu=True,
                    ),
                    parse_mode="HTML",
                )
        else:
            await callback.answer("Контекст подключения не найден")
    elif callback.data == "buy:resume_latest":
        payment = get_latest_pending_payment(callback.from_user.id)
        if not payment:
            await safe_edit(
                callback,
                "Незавершённых заявок сейчас нет.",
                reply_markup=build_buy_menu(callback.from_user.id),
            )
        else:
            await send_user_payment_detail(callback.message, callback.from_user.id, payment)
    elif callback.data == "payments":
        await safe_edit(
            callback,
            render_user_payments_text(callback.from_user.id),
            reply_markup=build_user_payments_menu(callback.from_user.id),
        )
    elif callback.data.startswith("user_payment:view:"):
        payment_id = int(callback.data.split(":")[2])
        payment = get_payment(payment_id)
        if not payment or int(payment["user_id"]) != callback.from_user.id:
            await safe_edit(
                callback,
                "Заявка не найдена.",
                reply_markup=build_user_payments_menu(callback.from_user.id),
            )
        else:
            await send_user_payment_detail(callback.message, callback.from_user.id, payment)
    elif callback.data.startswith("user_payment:refresh:"):
        payment_id = int(callback.data.split(":")[2])
        payment = get_payment(payment_id)
        if not payment or int(payment["user_id"]) != callback.from_user.id:
            await safe_edit(
                callback,
                "Заявка не найдена.",
                reply_markup=build_user_payments_menu(callback.from_user.id),
            )
            await callback.answer()
            return
        if payment.get("payment_status") != "pending":
            await safe_edit(
                callback,
                render_user_payment_detail_text(payment),
                reply_markup=build_user_payment_detail_menu(payment, callback.from_user.id),
            )
            await callback.answer()
            return
        plan_key = parse_payment_purchase_key(payment)
        if not plan_key:
            await safe_edit(
                callback,
                "Не удалось определить покупку заявки.",
                reply_markup=build_user_payments_menu(callback.from_user.id),
            )
            await callback.answer()
            return
        family = get_payment_provider_family(payment)
        remote_payment = None
        confirmation_url = None
        if family == "yookassa":
            remote_payment_id = parse_yookassa_payment_id(payment)
            if not remote_payment_id:
                logger.warning("missing yookassa payment id for local payment_id=%s", payment_id)
            else:
                try:
                    remote_payment = fetch_yookassa_payment(remote_payment_id)
                    confirmation_url = (
                        (remote_payment.get("confirmation") or {}).get("confirmation_url")
                    ) or None
                except Exception as exc:
                    logger.warning(
                        "failed to refresh yookassa payment payment_id=%s: %s", payment_id, exc
                    )
        if remote_payment and remote_payment.get("status") == "canceled":
            if transition_pending_payment(payment_id, "rejected"):
                payment = get_payment(payment_id) or payment
            await safe_edit(
                callback,
                render_user_payment_detail_text(payment, remote_payment=remote_payment),
                reply_markup=build_user_payment_detail_menu(payment, callback.from_user.id),
            )
            await callback.answer(render_payment_refresh_result("canceled"))
            return
        matched = match_successful_pending_payment(payment)
        if matched:
            try:
                completed_provider = build_completed_provider(payment, payment_id, plan_key, "auto")
                activated_user = await approve_pending_payment_with_provider(
                    callback.message.bot,
                    payment,
                    plan_key,
                    completed_provider,
                )
            except XrayError as exc:
                await safe_edit(
                    callback, str(exc), reply_markup=build_user_payments_menu(callback.from_user.id)
                )
                await callback.answer()
                return
            if activated_user:
                payment = get_payment(payment_id) or payment
                await safe_edit(
                    callback,
                    render_user_payment_detail_text(payment, remote_payment=matched),
                    reply_markup=build_user_payment_detail_menu(payment, callback.from_user.id),
                )
                await callback.answer(render_payment_refresh_result("confirmed"))
                return
        await safe_edit(
            callback,
            render_user_payment_detail_text(payment, remote_payment=remote_payment),
            reply_markup=build_user_payment_detail_menu(
                payment, callback.from_user.id, confirmation_url
            ),
        )
        await callback.answer(render_payment_refresh_result("updated"))
    elif callback.data == "account":
        await safe_edit(
            callback,
            render_account_text(callback.from_user.id),
            reply_markup=build_account_menu(callback.from_user.id),
        )
    elif callback.data == "invite":
        if not await enforce_rate_limit(callback, "invite"):
            return
        await safe_edit(
            callback,
            render_invite_text(callback.from_user.id),
            reply_markup=build_invite_menu(callback.from_user.id),
        )
    elif callback.data == "rewards":
        await safe_edit(
            callback,
            render_rewards_text(callback.from_user.id),
            reply_markup=build_invite_menu(callback.from_user.id),
        )
    elif callback.data == "devices":
        await safe_edit(
            callback,
            render_devices_text(callback.from_user.id),
            reply_markup=build_devices_menu(callback.from_user.id),
        )
    elif callback.data == "buy:paid":
        log_activity(callback.from_user.id, "buy_marked_paid")
        await safe_edit(
            callback,
            render_buy_waiting_text(callback.from_user.id),
            reply_markup=build_waiting_payment_menu(),
        )
    elif callback.data == "buy:addon:device_slot_1":
        state, user = get_user_state(callback.from_user.id)
        plan_key = resolve_plan_key(str((user or {}).get("plan", "trial")))
        if state in {"new", "trial_active", "expired"} or not user or plan_key == "trial":
            await safe_edit(
                callback,
                f"{BOT_BRAND}\n\n"
                "Дополнительные слоты доступны только с активной платной подпиской.",
                reply_markup=build_account_menu(callback.from_user.id),
            )
        elif get_user_extra_device_slots(callback.from_user.id) >= MAX_EXTRA_DEVICE_SLOTS:
            await safe_edit(
                callback,
                f"{BOT_BRAND}\n\n"
                "Ты уже достиг лимита на докупаемые слоты устройств.",
                reply_markup=build_account_menu(callback.from_user.id),
            )
        else:
            await safe_edit(
                callback,
                render_extra_device_slot_offer_text(callback.from_user.id),
                reply_markup=build_extra_device_slot_menu(callback.from_user.id),
            )
    elif callback.data.startswith("buy:cardlink:"):
        plan_key = callback.data.split(":", 2)[2]
        purchase = get_purchase_config(plan_key)
        if not purchase:
            await safe_edit(
                callback, "Неизвестный продукт.", reply_markup=build_buy_menu(callback.from_user.id)
            )
        elif not cardlink_configured():
            await safe_edit(
                callback,
                "CardLink пока не настроен в окружении бота.",
                reply_markup=build_buy_menu(callback.from_user.id),
            )
        else:
            existing_payment = get_latest_pending_payment(
                callback.from_user.id,
                plan_key=plan_key,
                provider_prefix="cardlink:",
            )
            if existing_payment:
                await safe_edit(
                    callback,
                    f"{BOT_BRAND}\n\n"
                    "У тебя уже есть незавершённая заявка по этой покупке.\n"
                    f"payment_id: {existing_payment['payment_id']}\n"
                    f"Покупка: {render_purchase_label(plan_key)}\n\n"
                    "Сначала заверши или проверь текущую заявку, чтобы не создавать дубликат.",
                    reply_markup=build_existing_pending_payment_menu(
                        int(existing_payment["payment_id"])
                    ),
                )
                await callback.answer()
                return
            try:
                cl_result = create_cardlink_payment(callback.from_user.id, plan_key)
            except Exception as exc:
                logger.warning(
                    "failed to create cardlink payment user_id=%s plan=%s: %s",
                    callback.from_user.id,
                    plan_key,
                    exc,
                )
                await safe_edit(
                    callback,
                    "Не удалось создать платёж.\nПопробуй ещё раз чуть позже.",
                    reply_markup=build_buy_menu(callback.from_user.id),
                )
                await callback.answer()
                return
            user = get_user(callback.from_user.id)
            if user:
                target = onboarding_logic.determine_payment_return_target(user)
                onboarding_logic.set_payment_return_target(callback.from_user.id, target)

            payment = create_pending_payment(
                user_id=callback.from_user.id,
                amount=purchase["amount"],
                currency="RUB",
                provider=f"cardlink:{cl_result['order_id']}:{cl_result['bill_id']}:{plan_key}",
            )
            log_activity(callback.from_user.id, f"payment_claimed_{plan_key}")
            kb = InlineKeyboardBuilder()
            kb.button(text="Оплатить", url=cl_result["payment_url"])
            kb.button(text="Мои заявки", callback_data="payments")
            kb.button(text="Назад", callback_data="menu")
            kb.adjust(1)
            await safe_edit(
                callback,
                f"{BOT_BRAND}\n\n"
                f"Счёт создан.\n"
                f"Покупка: {render_purchase_label(plan_key)}\n"
                f"Сумма: {purchase['amount']} ₽\n\n"
                "Нажми «Оплатить» — откроется страница оплаты картой.\n"
                "После оплаты подписка активируется автоматически.",
                reply_markup=kb.as_markup(),
            )
            if payment.get("payment_id"):
                await notify_admins_about_payment(
                    callback.message.bot,
                    int(payment["payment_id"]),
                    f"{BOT_BRAND} — новая заявка CardLink",
                )
    elif callback.data.startswith("buy:yookassa:"):
        plan_key = callback.data.split(":", 2)[2]
        purchase = get_purchase_config(plan_key)
        if not purchase:
            await safe_edit(
                callback, "Неизвестный продукт.", reply_markup=build_buy_menu(callback.from_user.id)
            )
        elif not yookassa_configured():
            await safe_edit(
                callback,
                "ЮKassa пока не настроена в окружении бота.",
                reply_markup=build_buy_menu(callback.from_user.id),
            )
        else:
            existing_payment, existing_remote = get_reusable_yookassa_payment(
                callback.from_user.id, plan_key
            )
            if existing_payment:
                if existing_remote and existing_remote.get("status") == "succeeded":
                    try:
                        activated_user = await approve_pending_payment_with_provider(
                            callback.message.bot,
                            existing_payment,
                            plan_key,
                            f"yookassa_auto:{int(existing_payment['payment_id'])}:{plan_key}",
                        )
                    except XrayError as exc:
                        await safe_edit(
                            callback, str(exc), reply_markup=build_buy_menu(callback.from_user.id)
                        )
                        await callback.answer()
                        return
                    if activated_user:
                        expires_at = parse_expires_at(activated_user.get("expires_at"))
                        await safe_edit(
                            callback,
                            f"{BOT_BRAND}\n\n"
                            "У тебя уже есть успешно оплаченная заявка по этому тарифу.\n"
                            f"payment_id: {existing_payment.get('payment_id')}\n"
                            f"Активно до: {expires_at.strftime('%d.%m.%Y %H:%M') if expires_at else 'unknown'}\n\n"
                            "Открой /config, чтобы получить актуальный профиль.",
                            reply_markup=build_post_config_menu(),
                        )
                        await callback.answer("Оплата уже подтверждена")
                        return
                if existing_remote:
                    if existing_remote.get("status") == "canceled":
                        transition_pending_payment(int(existing_payment["payment_id"]), "rejected")
                        existing_payment = (
                            get_payment(int(existing_payment["payment_id"])) or existing_payment
                        )
                    elif existing_remote.get("status") in {"pending", "waiting_for_capture"}:
                        confirmation_url = (
                            (existing_remote.get("confirmation") or {}).get("confirmation_url")
                        ) or ""
                        if confirmation_url:
                            plan_label = render_purchase_label(plan_key)
                            await safe_edit(
                                callback,
                                f"{BOT_BRAND}\n\n"
                                "У тебя уже есть незавершённая оплата по этой покупке.\n"
                                f"payment_id: {existing_payment.get('payment_id')}\n"
                                f"Покупка: {plan_label}\n\n"
                                "Открой прежнюю ссылку и продолжи оплату через СБП.",
                                reply_markup=build_yookassa_checkout_menu(
                                    confirmation_url, callback.from_user.id
                                ),
                            )
                            await callback.answer()
                            return
                if existing_payment.get("payment_status") == "pending":
                    await safe_edit(
                        callback,
                        f"{BOT_BRAND}\n\n"
                        "У тебя уже есть незавершённая заявка по этой покупке.\n"
                        f"payment_id: {existing_payment.get('payment_id')}\n\n"
                        "Я не буду создавать дубль. Открой текущую заявку и нажми «Обновить статус».",
                        reply_markup=build_user_payment_detail_menu(
                            existing_payment, callback.from_user.id
                        ),
                    )
                    await callback.answer()
                    return
            try:
                remote_payment = create_yookassa_sbp_payment(callback.from_user.id, plan_key)
            except Exception as exc:
                logger.warning(
                    "failed to create yookassa payment user_id=%s plan=%s: %s",
                    callback.from_user.id,
                    plan_key,
                    exc,
                )
                await safe_edit(
                    callback,
                    "Не удалось создать платёж ЮKassa.\nПопробуй ещё раз чуть позже.",
                    reply_markup=build_buy_menu(callback.from_user.id),
                )
                await callback.answer()
                return
            confirmation_url = (
                (remote_payment.get("confirmation") or {}).get("confirmation_url")
            ) or ""
            remote_payment_id = str(remote_payment.get("id") or "").strip()
            if not confirmation_url or not remote_payment_id:
                await safe_edit(
                    callback,
                    "ЮKassa вернула неполный ответ.\nПопробуй ещё раз чуть позже.",
                    reply_markup=build_buy_menu(callback.from_user.id),
                )
                await callback.answer()
                return
            user = get_user(callback.from_user.id)
            if user:
                target = onboarding_logic.determine_payment_return_target(user)
                onboarding_logic.set_payment_return_target(callback.from_user.id, target)

            payment = create_pending_payment(
                user_id=callback.from_user.id,
                amount=purchase["amount"],
                currency="RUB",
                provider=f"yookassa_sbp:{remote_payment_id}:{plan_key}",
            )
            log_activity(callback.from_user.id, f"payment_claimed_{plan_key}")
            await callback.message.answer(
                f"{BOT_BRAND}\n\n"
                "Платёж ЮKassa создан.\n"
                f"payment_id: {payment.get('payment_id')}\n"
                f"Покупка: {render_purchase_label(plan_key)}\n"
                f"Сумма: {purchase['amount']} ₽\n\n"
                "Нажми кнопку ниже, чтобы открыть оплату через СБП.\n"
                "После успешной оплаты бот попробует подтвердить её автоматически.",
                reply_markup=build_yookassa_checkout_menu(confirmation_url, callback.from_user.id),
            )
            if payment.get("payment_id"):
                await notify_admins_about_payment(
                    callback.message.bot,
                    int(payment["payment_id"]),
                    f"{BOT_BRAND} — новая заявка ЮKassa",
                )
    elif callback.data.startswith("buy:yoomoney:"):
        plan_key = callback.data.split(":", 2)[2]
        purchase = get_purchase_config(plan_key)
        if not purchase:
            await safe_edit(
                callback, "Неизвестный продукт.", reply_markup=build_buy_menu(callback.from_user.id)
            )
        elif not YOOMONEY_RECEIVER:
            await safe_edit(
                callback,
                "YooMoney пока не настроен в окружении бота.",
                reply_markup=build_buy_menu(callback.from_user.id),
            )
        else:
            payment_url = create_yoomoney_url(purchase["amount"], callback.from_user.id, plan_key)
            if not payment_url:
                await safe_edit(
                    callback,
                    "Не удалось подготовить ссылку YooMoney.\nПопробуй ещё раз чуть позже.",
                    reply_markup=build_buy_menu(callback.from_user.id),
                )
                await callback.answer()
                return
            existing_payment = get_latest_pending_payment(callback.from_user.id, plan_key=plan_key)
            if existing_payment and get_payment_provider_family(existing_payment) == "yoomoney":
                await safe_edit(
                    callback,
                    render_user_payment_detail_text(existing_payment),
                    reply_markup=build_user_payment_detail_menu(
                        existing_payment,
                        callback.from_user.id,
                        payment_url,
                    ),
                )
                await callback.answer("Открыта текущая заявка")
                return
            user = get_user(callback.from_user.id)
            if user:
                target = onboarding_logic.determine_payment_return_target(user)
                onboarding_logic.set_payment_return_target(callback.from_user.id, target)

            payment = create_pending_payment(
                user_id=callback.from_user.id,
                amount=purchase["amount"],
                currency="RUB",
                provider=f"yoomoney_checkout:{plan_key}",
            )
            log_activity(callback.from_user.id, f"payment_claimed_{plan_key}")
            await safe_edit(
                callback,
                f"{BOT_BRAND}\n\n"
                "Заявка создана.\n"
                f"payment_id: {payment.get('payment_id')}\n"
                f"Покупка: {render_purchase_label(plan_key)}\n"
                f"Сумма: {purchase['amount']} ₽\n\n"
                "Нажми «Оплатить».\n"
                "После оплаты бот попробует подтвердить её автоматически.\n"
                "Если не подтвердилась — открой «Мои заявки».",
                reply_markup=build_yoomoney_checkout_menu(payment_url, callback.from_user.id),
            )
            if payment.get("payment_id"):
                await notify_admins_about_payment(
                    callback.message.bot,
                    int(payment["payment_id"]),
                    f"{BOT_BRAND} — новая заявка YooMoney",
                )
    elif callback.data.startswith("buy:claim:"):
        plan_key = callback.data.split(":", 2)[2]
        purchase = get_purchase_config(plan_key)
        if not purchase:
            await safe_edit(
                callback, "Неизвестный продукт.", reply_markup=build_waiting_payment_menu()
            )
        else:
            payment = create_pending_payment(
                user_id=callback.from_user.id,
                amount=purchase["amount"],
                currency="RUB",
                provider=f"yoomoney_claim:{plan_key}",
            )
            log_activity(callback.from_user.id, f"payment_claimed_{plan_key}")
            await safe_edit(
                callback,
                f"{BOT_BRAND}\n\n"
                f"Заявка на проверку создана.\n"
                f"payment_id: {payment.get('payment_id')}\n"
                f"Покупка: {render_purchase_label(plan_key)}\n"
                f"Сумма: {purchase['amount']} ₽\n\n"
                "Администратор увидит её в очереди проверки.",
                reply_markup=build_waiting_payment_menu(),
            )
            if payment.get("payment_id"):
                await notify_admins_about_payment(
                    callback.message.bot,
                    int(payment["payment_id"]),
                    f"{BOT_BRAND} — новая заявка на оплату",
                )
    elif callback.data == "buy:manual":
        await callback.message.answer(
            "YooMoney ещё не настроен в окружении бота.\n"
            "Нужно добавить `YOOMONEY_RECEIVER` в env сервиса."
        )
    elif callback.data == "support:id":
        await safe_edit(
            callback,
            f"Твой ID: <code>{callback.from_user.id}</code>",
            reply_markup=build_support_menu(),
            parse_mode="HTML",
        )
    elif callback.data == "status":
        await safe_edit(
            callback,
            render_status_text(callback.from_user.id),
            reply_markup=build_main_menu(callback.from_user.id),
        )
    elif callback.data == "admin":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            await safe_edit(
                callback,
                render_admin_panel_text(),
                reply_markup=build_admin_menu(),
            )
    elif callback.data == "admin:offline":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            await safe_edit(
                callback,
                render_admin_offline_issue_text(),
                reply_markup=build_admin_offline_issue_menu(),
            )
    elif callback.data.startswith("admin:offline:issue:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            plan_key = callback.data.rsplit(":", 1)[-1]
            try:
                subscription = issue_operator_offline_subscription(plan_key)
            except XrayError as exc:
                await callback.message.answer(
                    f"{BOT_BRAND} — выпуск без Telegram\n\nОшибка xray: {exc}",
                    reply_markup=build_admin_offline_issue_menu(),
                )
                await callback.answer()
                return
            except Exception as exc:
                await callback.message.answer(
                    f"{BOT_BRAND} — выпуск без Telegram\n\nНе удалось выпустить подписку: {exc}",
                    reply_markup=build_admin_offline_issue_menu(),
                )
                await callback.answer()
                return

            log_activity(
                callback.from_user.id,
                f"offline_subscription_issued:{plan_key}:{subscription['claim_code']}",
            )
            await callback.message.answer(
                render_admin_offline_issued_text(subscription),
                reply_markup=build_admin_offline_issued_menu(),
                parse_mode="HTML",
            )
            await callback.answer("Offline-подписка выпущена")
    elif callback.data == "admin:stats":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            stats = get_user_stats()
            referral_stats = get_global_referral_stats()
            open_to_trial = (
                (referral_stats["trial"] / referral_stats["opens"]) * 100
                if referral_stats["opens"]
                else 0.0
            )
            trial_to_paid = (
                (referral_stats["paid"] / referral_stats["trial"]) * 100
                if referral_stats["trial"]
                else 0.0
            )
            open_to_paid = (
                (referral_stats["paid"] / referral_stats["opens"]) * 100
                if referral_stats["opens"]
                else 0.0
            )
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) as cnt FROM users WHERE expires_at > datetime('now') AND plan != 'trial'"
                )
                paid_active = cursor.fetchone()["cnt"]
                cursor.execute(
                    "SELECT COUNT(*) as cnt FROM users WHERE expires_at > datetime('now') AND plan = 'trial'"
                )
                trial_active = cursor.fetchone()["cnt"]
                cursor.execute("SELECT COUNT(*) as cnt FROM devices WHERE status = 'active'")
                active_devices = cursor.fetchone()["cnt"]
            await safe_edit(
                callback,
                f"{BOT_BRAND} — Статистика\n\n"
                f"Всего пользователей: {stats['total_users']}\n"
                f"Активных (trial): {trial_active}\n"
                f"Активных (платных): {paid_active}\n"
                f"Устройств (active): {active_devices}\n"
                f"Выручка: {stats['total_revenue']:.0f} ₽\n\n"
                f"Рефералы — открытий: {referral_stats['opens']}\n"
                f"Рефералы — trial: {referral_stats['trial']}\n"
                f"Рефералы — оплат: {referral_stats['paid']}\n"
                f"Рефералы — бонусных дней: {referral_stats['bonus_days']}\n"
                f"Рефералы — выручка: {referral_stats['revenue']:.0f} ₽\n"
                f"Воронка open→trial: {open_to_trial:.0f}%\n"
                f"Воронка trial→paid: {trial_to_paid:.0f}%\n"
                f"Воронка open→paid: {open_to_paid:.0f}%\n\n"
                f"Кап бонусных дней: {REFERRAL_BONUS_CAP_DAYS}\n"
                f"Бонус за оплату: +{REFERRAL_BONUS_DAYS} дней\n"
                f"{render_top_referrers_block()}\n\n"
                f"{render_payment_status_block()}\n\n"
                f"{render_rate_limit_block()}\n\n"
                f"{render_noisy_users_block()}\n\n"
                f"{render_suspicious_users_block()}\n",
                reply_markup=build_admin_menu(),
            )
    elif callback.data == "admin:abuse":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            await safe_edit(
                callback,
                render_abuse_stats_text(),
                reply_markup=build_admin_menu(),
            )
    elif callback.data == "admin:vpn":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            await safe_edit(
                callback,
                render_admin_vpn_health_text(),
                reply_markup=build_admin_menu(),
            )
    elif callback.data == "admin:runtime":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            await safe_edit(
                callback,
                render_admin_runtime_text(),
                reply_markup=build_admin_runtime_menu(),
            )
    elif callback.data == "admin:runtime:health":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            await safe_edit(
                callback,
                render_admin_vpn_health_text(),
                reply_markup=build_admin_runtime_menu(),
            )
    elif callback.data == "admin:runtime:refresh":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            health_text = render_admin_vpn_health_text()
            devices_ok, devices_payload, devices_output = await run_operator_json_command(
                ["python3", DEVICE_ACTIVITY_SYNC_SCRIPT, "--once"],
                timeout=40,
            )
            script_path = (
                "/opt/ghost-access-bot/scripts/reconcile_secondary_reality_clients.py"
                if os.path.exists(
                    "/opt/ghost-access-bot/scripts/reconcile_secondary_reality_clients.py"
                )
                else "/mnt/projects/scripts/reconcile_secondary_reality_clients.py"
            )
            secondary_ok, secondary_payload, secondary_output = await run_operator_json_command(
                ["python3", script_path],
                timeout=60,
            )
            await safe_edit(
                callback,
                render_admin_runtime_refresh_result(
                    health_text,
                    devices_ok,
                    devices_payload,
                    devices_output,
                    secondary_ok,
                    secondary_payload,
                    secondary_output,
                ),
                reply_markup=build_admin_runtime_menu(),
            )
    elif callback.data == "admin:runtime:reply":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            await safe_edit(
                callback,
                render_admin_user_reply_text(),
                reply_markup=build_admin_runtime_menu(),
            )
    elif callback.data == "admin:runtime:devices":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            ok, payload, output = await run_operator_json_command(
                ["python3", DEVICE_ACTIVITY_SYNC_SCRIPT, "--once"],
                timeout=40,
            )
            if ok and payload is not None:
                text = (
                    f"{BOT_BRAND} — Устройства\n\n"
                    "Синхронизация завершена.\n\n"
                    f"Нашлось: {payload.get('matched', 0)}\n"
                    f"Обновлено: {payload.get('updated', 0)}\n"
                    f"Пропущено: {payload.get('skipped', 0)}"
                )
            else:
                text = (
                    f"{BOT_BRAND} — Устройства\n\n"
                    "Не удалось обновить активность устройств.\n"
                    "Попробуй ещё раз чуть позже.\n\n"
                    f"Детали:\n{output[:700]}"
                )
            await safe_edit(
                callback,
                text,
                reply_markup=build_admin_runtime_menu(),
            )
    elif callback.data == "admin:runtime:secondary":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            script_path = (
                "/opt/ghost-access-bot/scripts/reconcile_secondary_reality_clients.py"
                if os.path.exists(
                    "/opt/ghost-access-bot/scripts/reconcile_secondary_reality_clients.py"
                )
                else "/mnt/projects/scripts/reconcile_secondary_reality_clients.py"
            )
            ok, payload, output = await run_operator_json_command(
                ["python3", script_path],
                timeout=60,
            )
            if payload is not None:
                text = (
                    f"{BOT_BRAND} — Резерв 2083\n\n"
                    "Проверка завершена.\n\n"
                    f"Устройств в базе: {payload.get('devices_seen', 0)}\n"
                    f"Зеркалировано: {payload.get('mirrored', 0)}\n"
                    f"Добавлено в runtime: {payload.get('runtime_added', 0)}\n"
                    f"Ошибок: {len(payload.get('errors', []))}"
                )
            else:
                text = (
                    f"{BOT_BRAND} — Резерв 2083\n\n"
                    "Не удалось проверить резерв.\n"
                    "Попробуй ещё раз чуть позже.\n\n"
                    f"Детали:\n{output[:700]}"
                )
            await safe_edit(
                callback,
                text,
                reply_markup=build_admin_runtime_menu(),
            )
    elif callback.data == "admin:users":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            ADMIN_USER_BROWSER_STATE.setdefault(
                callback.from_user.id,
                {
                    "status": "all",
                    "search": "",
                    "offset": "0",
                    "page_size": str(ADMIN_USERS_PAGE_SIZE),
                },
            )
            await safe_edit(
                callback,
                render_admin_users_text(callback.from_user.id),
                reply_markup=build_admin_users_menu(callback.from_user.id),
            )
    elif callback.data.startswith("admin:users:filter:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            status = callback.data.rsplit(":", 1)[1]
            state = ADMIN_USER_BROWSER_STATE.setdefault(
                callback.from_user.id,
                {
                    "status": "all",
                    "search": "",
                    "offset": "0",
                    "page_size": str(ADMIN_USERS_PAGE_SIZE),
                },
            )
            state["status"] = status
            state["offset"] = "0"
            await safe_edit(
                callback,
                render_admin_users_text(callback.from_user.id),
                reply_markup=build_admin_users_menu(callback.from_user.id),
            )
    elif callback.data.startswith("admin:users:page:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            offset = callback.data.rsplit(":", 1)[1]
            state = ADMIN_USER_BROWSER_STATE.setdefault(
                callback.from_user.id,
                {
                    "status": "all",
                    "search": "",
                    "offset": "0",
                    "page_size": str(ADMIN_USERS_PAGE_SIZE),
                },
            )
            state["offset"] = offset if offset.isdigit() else "0"
            await safe_edit(
                callback,
                render_admin_users_text(callback.from_user.id),
                reply_markup=build_admin_users_menu(callback.from_user.id),
            )
    elif callback.data == "admin:users:search":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            ADMIN_INPUT_MODE[callback.from_user.id] = "admin_user_search"
            await safe_edit(
                callback,
                f"{BOT_BRAND} — пользователи\n\n"
                "Отправь `@username` или `user_id` одним сообщением.\n\n"
                "Пример:\n"
                "@x0tta6bl4\n"
                "или\n"
                "2018432227",
                reply_markup=build_admin_menu(),
                parse_mode="Markdown",
            )
    elif callback.data == "admin:users:search_clear":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            state = ADMIN_USER_BROWSER_STATE.setdefault(
                callback.from_user.id,
                {
                    "status": "all",
                    "search": "",
                    "offset": "0",
                    "page_size": str(ADMIN_USERS_PAGE_SIZE),
                },
            )
            state["search"] = ""
            state["offset"] = "0"
            await safe_edit(
                callback,
                render_admin_users_text(callback.from_user.id),
                reply_markup=build_admin_users_menu(callback.from_user.id),
            )
    elif callback.data == "admin:payments":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            await safe_edit(
                callback,
                render_pending_payments_text(),
                reply_markup=build_admin_payment_queue_menu(),
            )
    elif callback.data == "admin:payments_done":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            await safe_edit(
                callback,
                render_processed_payments_text(),
                reply_markup=build_admin_menu(),
            )
    elif callback.data == "admin:payments_sync":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        elif not automatic_payment_verification_enabled():
            await callback.message.answer(
                "Автопроверка платежей не настроена.\nНужно добавить `YOOMONEY_API_TOKEN` или `YOOKASSA_*` в env сервиса.",
                reply_markup=build_admin_menu(),
            )
        else:
            approved = await reconcile_pending_payments(callback.message.bot)
            await callback.message.answer(
                f"{BOT_BRAND}\n\nРучная проверка завершена.\nАвтоподтверждено заявок: {approved}",
                reply_markup=build_admin_menu(),
            )
    elif callback.data == "admin:broadcast_templates":
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа")
        else:
            kb = InlineKeyboardBuilder()
            templates = [
                ("Тех. работы ночью", "bcast_tpl:maintenance"),
                ("Сервер обновлён", "bcast_tpl:updated"),
                ("Временные проблемы", "bcast_tpl:issues"),
                ("Новогодняя скидка", "bcast_tpl:promo"),
            ]
            for text, data in templates:
                kb.button(text=text, callback_data=data)
            kb.button(text="Назад", callback_data="admin")
            kb.adjust(2, 2, 1)
            await safe_edit(
                callback,
                f"{BOT_BRAND}\n\nШаблоны рассылки\n\n"
                "Выбери шаблон — увидишь текст и сможешь отправить.\n"
                "Или используй /broadcast для произвольного текста.",
                reply_markup=kb.as_markup(),
            )
    elif callback.data.startswith("bcast_tpl:"):
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа")
        else:
            tpl_key = callback.data.split(":")[1]
            templates = {
                "maintenance": (
                    "active",
                    "Плановые работы сегодня с 02:00 до 04:00 МСК.\n"
                    "Возможны кратковременные отключения.\n"
                    "Если после 04:00 не работает — нажми /repair.",
                ),
                "updated": (
                    "active",
                    "Сервер обновлён. Всё работает.\nЕсли есть проблемы — нажми /repair.",
                ),
                "issues": (
                    "active",
                    "Сейчас есть проблемы с подключением. Уже чиним.\n"
                    "Попробуй /repair или подожди 15-30 минут.",
                ),
                "promo": (
                    "all",
                    "Новогодняя акция! Годовая подписка со скидкой 30%.\n"
                    "Успей до конца января. /buy",
                ),
            }
            audience, text = templates.get(tpl_key, ("active", ""))
            if not text:
                await callback.answer("Шаблон не найден")
            else:
                kb = InlineKeyboardBuilder()
                kb.button(text=f"Отправить ({audience})", callback_data=f"bcast_send:{tpl_key}")
                kb.button(text="Назад", callback_data="admin:broadcast_templates")
                kb.adjust(1)
                await safe_edit(
                    callback,
                    f"{BOT_BRAND}\n\nПредпросмотр ({audience}):\n\n{text}",
                    reply_markup=kb.as_markup(),
                )
    elif callback.data.startswith("bcast_send:"):
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа")
        else:
            tpl_key = callback.data.split(":")[1]
            templates = {
                "maintenance": (
                    "active",
                    "Плановые работы сегодня с 02:00 до 04:00 МСК.\nВозможны кратковременные отключения.\nЕсли после 04:00 не работает — нажми /repair.",
                ),
                "updated": (
                    "active",
                    "Сервер обновлён. Всё работает.\nЕсли есть проблемы — нажми /repair.",
                ),
                "issues": (
                    "active",
                    "Сейчас есть проблемы с подключением. Уже чиним.\nПопробуй /repair или подожди 15-30 минут.",
                ),
                "promo": (
                    "all",
                    "Новогодняя акция! Годовая подписка со скидкой 30%.\nУспей до конца января. /buy",
                ),
            }
            audience, text = templates.get(tpl_key, ("active", ""))
            user_ids = get_broadcast_user_ids(audience)
            sent, blocked = 0, 0
            for uid in user_ids:
                try:
                    await callback.bot.send_message(uid, f"{BOT_BRAND}\n\n{text}")
                    sent += 1
                except Exception:
                    blocked += 1
                if sent % 25 == 0:
                    await asyncio.sleep(1)
            log_activity(callback.from_user.id, f"broadcast_tpl_{tpl_key}_{sent}")
            await safe_edit(
                callback,
                f"Рассылка «{tpl_key}» завершена.\nОтправлено: {sent}, не доставлено: {blocked}",
                reply_markup=build_admin_menu(),
            )
    elif callback.data == "admin:revenue":
        if not is_admin(callback.from_user.id):
            await callback.answer("Нет доступа")
        else:
            # Reuse cmd_revenue logic inline
            now = datetime.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0)
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COALESCE(SUM(amount), 0) as total FROM payments "
                    "WHERE payment_status IN ('completed', 'approved') AND payment_date >= ?",
                    (month_start.isoformat(),),
                )
                mrr = cursor.fetchone()["total"]
                cursor.execute(
                    "SELECT COUNT(*) as cnt FROM users WHERE expires_at > datetime('now') AND plan != 'trial'"
                )
                paid_active = cursor.fetchone()["cnt"]
                cursor.execute(
                    "SELECT COALESCE(SUM(amount), 0) as total FROM payments "
                    "WHERE payment_status IN ('completed', 'approved')"
                )
                total_rev = cursor.fetchone()["total"]
            await safe_edit(
                callback,
                f"{BOT_BRAND} — Доходы\n\n"
                f"Этот месяц: {mrr:.0f} ₽\n"
                f"Всего: {total_rev:.0f} ₽\n"
                f"Платящих: {paid_active}\n\n"
                "Подробнее: /revenue",
                reply_markup=build_admin_menu(),
            )
    elif callback.data == "admin:help":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            await safe_edit(
                callback,
                render_admin_help_text(),
                reply_markup=build_admin_menu(),
            )
    elif callback.data.startswith("admin_payment:view:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            payment_id = int(callback.data.split(":")[2])
            await safe_edit(
                callback,
                render_admin_payment_text(payment_id),
                reply_markup=build_admin_payment_menu(payment_id),
            )
    elif callback.data.startswith("admin_payment:approve_prompt:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            payment_id = int(callback.data.split(":")[2])
            payment = get_payment(payment_id)
            if not payment:
                await callback.message.answer(
                    "Платёж не найден.", reply_markup=build_admin_payment_queue_menu()
                )
            elif payment.get("payment_status") != "pending":
                await callback.message.answer(
                    "Этот платёж уже обработан.", reply_markup=build_admin_payment_queue_menu()
                )
            else:
                await safe_edit(
                    callback,
                    render_admin_payment_text(payment_id)
                    + "\n\nВнимание: ручное подтверждение сразу активирует подписку без проверки фактической оплаты.",
                    reply_markup=build_admin_payment_confirm_menu(payment_id),
                )
    elif callback.data.startswith("admin_payment:approve:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            payment_id = int(callback.data.split(":")[2])
            payment = get_payment(payment_id)
            plan_key = parse_payment_purchase_key(payment)
            if not payment:
                await callback.message.answer(
                    "Платёж не найден.", reply_markup=build_admin_payment_queue_menu()
                )
            elif payment.get("payment_status") != "pending":
                await callback.message.answer(
                    "Этот платёж уже обработан.", reply_markup=build_admin_payment_queue_menu()
                )
            elif not plan_key:
                await callback.message.answer(
                    "Не удалось определить покупку для этого платежа.",
                    reply_markup=build_admin_payment_queue_menu(),
                )
            else:
                try:
                    manual_provider = build_completed_provider(
                        payment, payment_id, plan_key, "manual_review"
                    )
                    activated_user = await approve_pending_payment_with_provider(
                        callback.message.bot,
                        payment,
                        plan_key,
                        manual_provider,
                        notify_user=False,
                    )
                except XrayError as exc:
                    await callback.message.answer(
                        f"Ошибка xray: {exc}", reply_markup=build_admin_payment_menu(payment_id)
                    )
                    await callback.answer()
                    return
                expires_at = parse_expires_at(activated_user.get("expires_at"))
                plan_label = render_purchase_label(plan_key)
                await callback.message.answer(
                    f"Платёж подтверждён: #{payment_id}\n"
                    f"user_id={payment['user_id']}\n"
                    f"Покупка: {plan_label}\n"
                    f"Активно до: {expires_at.strftime('%d.%m.%Y %H:%M') if expires_at else 'unknown'}",
                    reply_markup=build_admin_payment_queue_menu(),
                )
                try:
                    success_text = (
                        f"{BOT_BRAND}\n\n"
                        "Оплата подтверждена.\n"
                        f"Покупка: {plan_label}\n"
                    )
                    if is_device_slot_addon_key(plan_key):
                        extra_total = get_user_extra_device_slots(int(payment["user_id"]))
                        success_text += f"Теперь докуплено слотов: +{extra_total}"
                    else:
                        success_text += (
                            f"До: {expires_at.strftime('%d.%m.%Y %H:%M') if expires_at else 'unknown'}"
                        )
                    await callback.message.bot.send_message(
                        int(payment["user_id"]),
                        success_text,
                        reply_markup=build_payment_success_menu(),
                    )
                except Exception as exc:
                    logger.warning(
                        "failed to notify approved payment user_id=%s: %s", payment["user_id"], exc
                    )
    elif callback.data.startswith("admin_payment:reject:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            payment_id = int(callback.data.split(":")[2])
            payment = get_payment(payment_id)
            if not payment:
                await callback.message.answer(
                    "Платёж не найден.", reply_markup=build_admin_payment_queue_menu()
                )
            elif payment.get("payment_status") != "pending":
                await callback.message.answer(
                    "Этот платёж уже обработан.", reply_markup=build_admin_payment_queue_menu()
                )
            else:
                if not transition_pending_payment(payment_id, "rejected"):
                    await callback.message.answer(
                        "Этот платёж уже обработан.", reply_markup=build_admin_payment_queue_menu()
                    )
                else:
                    await callback.message.answer(
                        f"Платёж отклонён: #{payment_id}",
                        reply_markup=build_admin_payment_queue_menu(),
                    )
                    try:
                        await callback.message.bot.send_message(
                            int(payment["user_id"]),
                            f"{BOT_BRAND}\n\n"
                            "Заявка на оплату отклонена.\n"
                            "Проверь сумму или статус перевода и создай новую заявку после оплаты.",
                            reply_markup=build_user_payments_menu(int(payment["user_id"])),
                        )
                    except Exception as exc:
                        logger.warning(
                            "failed to notify rejected payment user_id=%s: %s",
                            payment["user_id"],
                            exc,
                        )
    elif callback.data == "admin:user_help":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            ADMIN_INPUT_MODE[callback.from_user.id] = "admin_user_lookup"
            await safe_edit(
                callback,
                render_admin_user_lookup_text(),
                reply_markup=build_admin_menu(),
            )
    elif callback.data == "admin:user_lookup":
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            ADMIN_INPUT_MODE[callback.from_user.id] = "admin_user_lookup"
            await safe_edit(
                callback,
                render_admin_user_lookup_text(),
                reply_markup=build_admin_menu(),
            )
    elif callback.data.startswith("admin_user:quick:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            target_user_id = int(callback.data.split(":")[2])
            await safe_edit(
                callback,
                render_admin_activation_text(target_user_id),
                reply_markup=build_admin_activation_menu(target_user_id),
            )
    elif callback.data.startswith("admin_user:view:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            target_user_id = int(callback.data.split(":")[2])
            await safe_edit(
                callback,
                render_admin_user_text(target_user_id),
                reply_markup=build_admin_user_menu(target_user_id),
            )
    elif callback.data.startswith("admin_user:devices:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            target_user_id = int(callback.data.split(":")[2])
            await safe_edit(
                callback,
                render_admin_user_devices_text(target_user_id),
                reply_markup=build_admin_user_devices_menu(target_user_id),
            )
    elif callback.data.startswith("admin_user:payments:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            target_user_id = int(callback.data.split(":")[2])
            await safe_edit(
                callback,
                render_admin_user_payments_text(target_user_id),
                reply_markup=build_admin_user_menu(target_user_id),
            )
    elif callback.data.startswith("admin_user:activity:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            target_user_id = int(callback.data.split(":")[2])
            await safe_edit(
                callback,
                render_admin_user_activity_text(target_user_id),
                reply_markup=build_admin_user_menu(target_user_id),
            )
    elif callback.data.startswith("admin_user:deliver:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            target_user_id = int(callback.data.split(":")[2])
            target_user = get_user(target_user_id)
            if not target_user:
                await safe_edit(
                    callback,
                    f"{BOT_BRAND} — отправка профиля\n\nuser_id: {target_user_id}\nПользователь не найден.",
                    reply_markup=build_admin_menu(),
                )
            else:
                try:
                    await send_subscription_bundle_to_user(callback.message.bot, target_user)
                    await safe_edit(
                        callback,
                        (
                            f"{BOT_BRAND} — отправка профиля\n\n"
                            f"user_id: {target_user_id}\n"
                            f"Профиль: {render_delivery_profile_label(resolve_delivery_profile(target_user))}\n"
                            "Подключение отправлено пользователю в чат."
                        ),
                        reply_markup=build_admin_user_menu(target_user_id),
                    )
                except Exception as exc:
                    logger.warning(
                        "failed to deliver subscription bundle user_id=%s: %s",
                        target_user_id,
                        exc,
                    )
                    await safe_edit(
                        callback,
                        (
                            f"{BOT_BRAND} — отправка профиля\n\n"
                            f"user_id: {target_user_id}\n"
                            f"Не удалось отправить подключение: {exc}"
                        ),
                        reply_markup=build_admin_user_menu(target_user_id),
                    )
    elif callback.data.startswith("admin_user:profile:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            _, _, _, target_user_id_raw, profile = callback.data.split(":", 4)
            target_user_id = int(target_user_id_raw)
            updated_user = apply_delivery_profile(target_user_id, profile)
            if not updated_user:
                await safe_edit(
                    callback,
                    f"{BOT_BRAND} — профиль доставки\n\nuser_id: {target_user_id}\nПользователь не найден.",
                    reply_markup=build_admin_menu(),
                )
            else:
                await safe_edit(
                    callback,
                    (
                        f"{BOT_BRAND} — профиль доставки\n\n"
                        f"user_id: {target_user_id}\n"
                        f"Новый профиль: {render_delivery_profile_label(resolve_delivery_profile(updated_user))}\n"
                        f"entry_node: {resolve_entry_node(updated_user)}\n"
                        f"client_family: {resolve_client_family(updated_user)}\n"
                        f"connect_url: {build_delivery_connect_url(updated_user)}"
                    ),
                    reply_markup=build_admin_user_menu(target_user_id),
                )
    elif callback.data.startswith("admin_user:delete_prompt:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            target_user_id = int(callback.data.split(":")[2])
            await safe_edit(
                callback,
                f"{BOT_BRAND} — удалить профиль\n\n"
                f"user_id: {target_user_id}\n\n"
                "Будут удалены:\n"
                "• запись пользователя\n"
                "• устройства в базе бота\n"
                "• история активности и доступов\n\n"
                "Платежи будут обезличены.\n"
                "Активные xray-клиенты этого пользователя будут удалены.\n\n"
                "Это действие необратимо.",
                reply_markup=build_admin_user_delete_confirm_menu(target_user_id),
            )
    elif callback.data.startswith("admin_user:delete_confirm:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            target_user_id = int(callback.data.split(":")[2])
            devices = list_user_devices(target_user_id)
            removed_runtime = 0
            for device in devices:
                try:
                    remove_xray_client(device["vpn_uuid"], device.get("xray_email"))
                    removed_runtime += 1
                except Exception:
                    pass
            summary = delete_user_account(target_user_id)
            logger.info(
                "admin deleted profile user_id=%d devices=%d runtime_removed=%d activities=%d payments_anon=%d",
                target_user_id,
                summary["devices_removed"],
                removed_runtime,
                summary["activities_removed"],
                summary["payments_anonymized"],
            )
            await safe_edit(
                callback,
                f"{BOT_BRAND} — профиль удалён\n\n"
                f"user_id: {target_user_id}\n"
                f"Устройств удалено из базы: {summary['devices_removed']}\n"
                f"Активных xray-клиентов удалено: {removed_runtime}\n"
                f"Платежей обезличено: {summary['payments_anonymized']}",
                reply_markup=build_admin_menu(),
            )
    elif callback.data.startswith("admin_user:device:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            _, _, _, user_id_raw, device_id_raw = callback.data.split(":", 4)
            target_user_id = int(user_id_raw)
            device = get_device(int(device_id_raw))
            if not device or device["user_id"] != target_user_id:
                await callback.message.answer(
                    "Устройство не найдено.",
                    reply_markup=build_admin_user_devices_menu(target_user_id),
                )
            else:
                await callback.message.answer(
                    render_admin_user_device_text(target_user_id, device),
                    reply_markup=build_admin_user_device_menu(
                        target_user_id,
                        device["device_id"],
                        active=device.get("status") == "active",
                    ),
                )
    elif callback.data.startswith("admin_user:activate:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            _, _, user_id_raw, plan_key = callback.data.split(":", 3)
            target_user_id = int(user_id_raw)
            try:
                activated_user = activate_paid_plan(
                    target_user_id,
                    None,
                    plan_key,
                    provider="admin_grant",
                    record_billing=False,
                    reward_referral=False,
                )
            except XrayError as exc:
                await callback.message.answer(f"Ошибка xray: {exc}")
                await callback.answer()
                return
            expires_at = parse_expires_at(activated_user.get("expires_at"))
            plan_label = render_plan_label(plan_key)
            await callback.message.answer(
                f"Активировано: user_id={target_user_id}\n"
                f"План: {plan_label}\n"
                f"Активно до: {expires_at.strftime('%d.%m.%Y %H:%M') if expires_at else 'unknown'}",
                reply_markup=build_admin_user_menu(target_user_id),
            )
            try:
                await callback.message.bot.send_message(
                    target_user_id,
                    f"{BOT_BRAND}: подписка продлена.\n"
                    f"План: {plan_label}\n"
                    f"Активно до: {expires_at.strftime('%d.%m.%Y %H:%M') if expires_at else 'unknown'}\n\n"
                    "Открой /config, чтобы получить актуальный QR-профиль.",
                )
            except Exception as exc:
                logger.warning("failed to notify activated user_id=%s: %s", target_user_id, exc)
    elif callback.data.startswith("admin_user:revoke_device:"):
        if not is_admin(callback.from_user.id):
            await callback.message.answer("Эта команда доступна только администратору.")
        else:
            _, _, _, user_id_raw, device_id_raw = callback.data.split(":", 4)
            target_user_id = int(user_id_raw)
            device_id = int(device_id_raw)
            device = get_device(device_id)
            if not device or device["user_id"] != target_user_id:
                await callback.message.answer(
                    "Устройство не найдено.",
                    reply_markup=build_admin_user_devices_menu(target_user_id),
                )
            elif device.get("status") != "active":
                await callback.message.answer(
                    "Устройство уже неактивно.",
                    reply_markup=build_admin_user_devices_menu(target_user_id),
                )
            else:
                try:
                    remove_xray_client(device["vpn_uuid"], device.get("xray_email"))
                except XrayError as exc:
                    await callback.message.answer(str(exc))
                    await callback.answer()
                    return
                revoke_device(device_id)
                sync_primary_device(target_user_id)
                await callback.message.answer(
                    f"{BOT_BRAND}\n\nУстройство «{device['device_name']}» отключено администратором.",
                    reply_markup=build_admin_user_devices_menu(target_user_id),
                )
    elif callback.data == "repair":
        if not await enforce_rate_limit(callback, "repair"):
            return
        await safe_edit(callback, render_repair_intro(), reply_markup=build_repair_menu())
    elif callback.data.startswith("transport:") or callback.data.startswith("egress:"):
        if not is_user_active(callback.from_user.id):
            await callback.answer("Только для активных подписчиков")
            return
        mode = callback.data.split(":", 1)[1]
        changed, text = apply_transport_mode_choice(callback.from_user.id, mode)
        if changed:
            await safe_edit(
                callback,
                text,
                reply_markup=build_account_menu(callback.from_user.id),
            )
            await callback.answer("Режим Telegram обновлён")
    elif callback.data == "guide":
        await safe_edit(callback, render_guide_intro(), reply_markup=build_guide_menu())
    elif callback.data.startswith("guide:"):
        platform = callback.data.split(":", 1)[1]
        await safe_edit(
            callback,
            render_guide_text(platform),
            reply_markup=build_guide_platform_menu(platform),
        )
    elif callback.data == "confirm_delete_account":
        user_id = callback.from_user.id
        # Remove xray clients for all active devices
        devices = list_user_devices(user_id)
        for device in devices:
            try:
                remove_xray_client(device["vpn_uuid"], device.get("xray_email"))
            except Exception:
                pass
        summary = delete_user_account(user_id)
        logger.info(
            "account deleted user_id=%d devices=%d activities=%d payments_anon=%d",
            user_id,
            summary["devices_removed"],
            summary["activities_removed"],
            summary["payments_anonymized"],
        )
        await safe_edit(
            callback,
            f"{BOT_BRAND}\n\n"
            "Аккаунт удалён.\n\n"
            f"Устройств удалено: {summary['devices_removed']}\n"
            f"Платежей обезличено: {summary['payments_anonymized']}\n\n"
            "Все данные стёрты. Чтобы начать заново — /start",
        )
    elif callback.data == "menu":
        await safe_edit(
            callback,
            render_start_text(callback.from_user.id),
            reply_markup=build_main_menu(callback.from_user.id),
        )
    elif callback.data.startswith("diag:"):
        symptom = callback.data.split(":", 1)[1]
        if not await enforce_rate_limit(callback, "repair"):
            return
        await diagnose_and_send_config(callback, symptom)
    elif callback.data.startswith("repair:"):
        kind = callback.data.split(":", 1)[1]
        if not check_xray_port_alive():
            await safe_edit(
                callback,
                f"{BOT_BRAND}\n\n"
                "Сервер сейчас недоступен — проблема на нашей стороне.\n"
                "Мы уже знаем и чиним.\n\n"
                "Попробуй подключиться через 5-10 минут.",
                reply_markup=build_main_menu(callback.from_user.id),
            )
            logger.warning(
                "repair callback: xray port %d down, informed user %d",
                VPN_PORT,
                callback.from_user.id,
            )
        else:
            await safe_edit(
                callback,
                render_repair_response(kind, get_active_user(callback.from_user.id)),
                reply_markup=build_repair_followup_menu(kind),
                parse_mode="Markdown",
            )
    elif callback.data == "device:add":
        state, user = get_user_state(callback.from_user.id)
        if state == "new" or not user:
            await safe_edit(
                callback,
                "Сначала активируй тест или подписку.",
                reply_markup=build_main_menu(callback.from_user.id),
            )
        else:
            devices = list_user_devices(callback.from_user.id)
            limit = get_device_limit(user)
            if len(devices) >= limit:
                await safe_edit(
                    callback,
                    "Лимит устройств достигнут. Отключи старое устройство, докупи слот или обнови подписку.",
                    reply_markup=build_devices_menu(callback.from_user.id),
                )
            else:
                await safe_edit(
                    callback,
                    render_device_type_text(callback.from_user.id),
                    reply_markup=build_device_type_menu(callback.from_user.id),
                )
    elif callback.data.startswith("device:add:"):
        device_type = callback.data.rsplit(":", 1)[1]
        state, user = get_user_state(callback.from_user.id)
        if state == "new" or not user:
            await safe_edit(
                callback,
                "Сначала активируй тест или подписку.",
                reply_markup=build_main_menu(callback.from_user.id),
            )
        else:
            try:
                device = create_next_device(callback.from_user.id, device_type=device_type)
            except XrayError as exc:
                await safe_edit(
                    callback, str(exc), reply_markup=build_devices_menu(callback.from_user.id)
                )
                await callback.answer()
                return
            except RuntimeError as exc:
                message = str(exc)
                if message == "Device limit reached":
                    await safe_edit(
                        callback,
                        "Лимит устройств достигнут. Отключи старое устройство, докупи слот или обнови подписку.",
                        reply_markup=build_devices_menu(callback.from_user.id),
                    )
                else:
                    await safe_edit(
                        callback,
                        f"Не удалось добавить устройство: {message}",
                        reply_markup=build_devices_menu(callback.from_user.id),
                    )
            else:
                await callback.answer("Устройство добавлено")
                await safe_edit(
                    callback,
                    render_device_added_text(device),
                    reply_markup=build_device_added_menu(int(device["device_id"])),
                )
                await send_device_connect_bundle(callback.message, device)
    elif callback.data.startswith("device:added:"):
        device_id = int(callback.data.rsplit(":", 1)[1])
        device = get_device(device_id)
        if not device or device["user_id"] != callback.from_user.id:
            await safe_edit(
                callback,
                "Устройство не найдено.",
                reply_markup=build_devices_menu(callback.from_user.id),
            )
        else:
            await safe_edit(
                callback,
                render_device_added_text(device),
                reply_markup=build_device_added_menu(device_id),
            )
    elif callback.data.startswith("device:connect_menu:"):
        device_id = int(callback.data.rsplit(":", 1)[1])
        device = get_device(device_id)
        if (
            not device
            or device["user_id"] != callback.from_user.id
            or device.get("status") != "active"
        ):
            await safe_edit(
                callback,
                "Устройство недоступно.",
                reply_markup=build_devices_menu(callback.from_user.id),
            )
        else:
            await send_device_connect_bundle(callback.message, device)
            await callback.answer("Подключение отправлено")
    elif callback.data.startswith("device:connect:"):
        _, _, device_id_str, platform = callback.data.split(":", 3)
        device_id = int(device_id_str)
        device = get_device(device_id)
        if (
            not device
            or device["user_id"] != callback.from_user.id
            or device.get("status") != "active"
        ):
            await safe_edit(
                callback,
                "Устройство недоступно.",
                reply_markup=build_devices_menu(callback.from_user.id),
            )
        else:
            await send_device_connect_bundle(callback.message, device)
            await callback.answer("Подключение отправлено")
    elif callback.data.startswith("device:show:"):
        device_id = int(callback.data.rsplit(":", 1)[1])
        device = get_device(device_id)
        if not device or device["user_id"] != callback.from_user.id:
            await safe_edit(
                callback,
                "Устройство не найдено.",
                reply_markup=build_devices_menu(callback.from_user.id),
            )
        else:
            await safe_edit(
                callback,
                render_device_detail_text(device),
                reply_markup=build_device_detail_menu(
                    device_id,
                    active=device.get("status") == "active",
                    locked=is_device_slot_locked(device),
                ),
            )
    elif callback.data.startswith("device:config:"):
        device_id = int(callback.data.rsplit(":", 1)[1])
        device = get_device(device_id)
        if (
            not device
            or device["user_id"] != callback.from_user.id
            or device.get("status") != "active"
        ):
            await safe_edit(
                callback,
                "Устройство недоступно.",
                reply_markup=build_devices_menu(callback.from_user.id),
            )
        else:
            await send_device_connect_bundle(callback.message, device)
            await callback.answer("Подключение отправлено")
    elif callback.data.startswith("device:make_primary:"):
        device_id = int(callback.data.rsplit(":", 1)[1])
        device = get_device(device_id)
        if (
            not device
            or device["user_id"] != callback.from_user.id
            or device.get("status") != "active"
        ):
            await safe_edit(
                callback,
                "Устройство недоступно.",
                reply_markup=build_devices_menu(callback.from_user.id),
            )
        else:
            primary = sync_primary_device(callback.from_user.id, device_id)
            if not primary:
                await safe_edit(
                    callback,
                    "Не удалось выбрать основное устройство.",
                    reply_markup=build_devices_menu(callback.from_user.id),
                )
            else:
                await safe_edit(
                    callback,
                    render_device_detail_text(primary),
                    reply_markup=build_device_detail_menu(
                        primary["device_id"],
                        active=primary.get("status") == "active",
                        locked=is_device_slot_locked(primary),
                    ),
                )
    elif callback.data.startswith("device:replace:"):
        device_id = int(callback.data.rsplit(":", 1)[1])
        device = get_device(device_id)
        if (
            not device
            or device["user_id"] != callback.from_user.id
            or device.get("status") != "active"
        ):
            await safe_edit(
                callback,
                "Устройство недоступно.",
                reply_markup=build_devices_menu(callback.from_user.id),
            )
        else:
            was_primary = is_primary_device(device)
            try:
                remove_xray_client(device["vpn_uuid"], device.get("xray_email"))
            except XrayError as exc:
                await safe_edit(
                    callback, str(exc), reply_markup=build_devices_menu(callback.from_user.id)
                )
                await callback.answer()
                return
            revoke_device(device_id)
            try:
                replacement = create_next_device(
                    callback.from_user.id, device_type=device.get("device_type") or "other"
                )
            except Exception as exc:
                await safe_edit(
                    callback,
                    f"Старый слот отключён, но новое устройство не создано: {exc}",
                    reply_markup=build_devices_menu(callback.from_user.id),
                )
                await callback.answer()
                return
            if was_primary:
                sync_primary_device(callback.from_user.id, replacement["device_id"])
                replacement = get_device(replacement["device_id"]) or replacement
            await send_device_connect_bundle(callback.message, replacement)
            await safe_edit(
                callback,
                render_device_replace_result(device, replacement),
                reply_markup=build_device_detail_menu(replacement["device_id"]),
            )
    elif callback.data.startswith("device:remove:"):
        device_id = int(callback.data.rsplit(":", 1)[1])
        device = get_device(device_id)
        if (
            not device
            or device["user_id"] != callback.from_user.id
            or device.get("status") != "active"
        ):
            await safe_edit(
                callback,
                "Устройство недоступно.",
                reply_markup=build_devices_menu(callback.from_user.id),
            )
        else:
            try:
                remove_xray_client(device["vpn_uuid"], device.get("xray_email"))
            except XrayError as exc:
                await safe_edit(
                    callback, str(exc), reply_markup=build_devices_menu(callback.from_user.id)
                )
                await callback.answer()
                return
            revoke_device(device_id)
            sync_primary_device(callback.from_user.id)
            await safe_edit(
                callback,
                f"{BOT_BRAND}\n\nУстройство «{device['device_name']}» отключено.",
                reply_markup=build_devices_menu(callback.from_user.id),
            )
    elif callback.data.startswith("device:share:"):
        device_id = int(callback.data.rsplit(":", 1)[1])
        device = get_device(device_id)
        if (
            not device
            or device["user_id"] != callback.from_user.id
            or device.get("status") != "active"
        ):
            await safe_edit(
                callback,
                "Устройство недоступно.",
                reply_markup=build_devices_menu(callback.from_user.id),
            )
        else:
            await send_device_connect_bundle(callback.message, device, share_mode=True)
            await callback.answer("Можно просто переслать")
    elif callback.data.startswith("device:rename:"):
        device_id = int(callback.data.rsplit(":", 1)[1])
        device = get_device(device_id)
        if not device or device["user_id"] != callback.from_user.id:
            await safe_edit(
                callback,
                "Устройство не найдено.",
                reply_markup=build_devices_menu(callback.from_user.id),
            )
        else:
            DEVICE_RENAME_PENDING[callback.from_user.id] = device_id
            builder = InlineKeyboardBuilder()
            presets = build_device_rename_presets(callback.from_user.id)
            for text, name in presets:
                builder.button(text=text, callback_data=f"device:rename_to:{device_id}:{name}")
            builder.button(text="Назад", callback_data=f"device:show:{device_id}")
            builder.adjust(2, 2, 2, 1)
            await safe_edit(
                callback,
                (
                    f"{BOT_BRAND}\n\n"
                    f"Переименовать «{device['device_name']}»\n\n"
                    "Выбери готовый вариант ниже или просто отправь своё имя сообщением.\n"
                    "Примеры: «Мой телефон», «Рабочий ноутбук», «Телефон ребенка 2»."
                ),
                reply_markup=builder.as_markup(),
            )
    elif callback.data.startswith("device:rename_custom:"):
        device_id = int(callback.data.rsplit(":", 1)[1])
        device = get_device(device_id)
        if not device or device["user_id"] != callback.from_user.id:
            await safe_edit(
                callback,
                "Устройство не найдено.",
                reply_markup=build_devices_menu(callback.from_user.id),
            )
        else:
            DEVICE_RENAME_PENDING[callback.from_user.id] = device_id
            await safe_edit(
                callback,
                (
                    f"{BOT_BRAND}\n\n"
                    f"Отправь новое имя для устройства «{device['device_name']}».\n\n"
                    "Примеры:\n"
                    "Мой телефон\n"
                    "Рабочий ноутбук\n"
                    "Телефон ребенка 2\n\n"
                    "Чтобы отменить, отправь: отмена"
                ),
                reply_markup=build_device_detail_menu(
                    device_id,
                    active=device.get("status") == "active",
                    locked=is_device_slot_locked(device),
                ),
            )
    elif callback.data.startswith("device:rename_to:"):
        parts = callback.data.split(":", 3)
        device_id = int(parts[2])
        new_name = parts[3]
        device = get_device(device_id)
        if not device or device["user_id"] != callback.from_user.id:
            await safe_edit(
                callback,
                "Устройство не найдено.",
                reply_markup=build_devices_menu(callback.from_user.id),
            )
        else:
            try:
                device, final_name = apply_device_rename(callback.from_user.id, device_id, new_name)
            except XrayError as exc:
                await safe_edit(
                    callback, str(exc), reply_markup=build_devices_menu(callback.from_user.id)
                )
                await callback.answer()
                return
            except RuntimeError as exc:
                await callback.answer(str(exc), show_alert=True)
                return
            DEVICE_RENAME_PENDING.pop(callback.from_user.id, None)
            await callback.answer(f"Имя обновлено: {final_name}")
            await safe_edit(
                callback,
                render_device_detail_text(device),
                reply_markup=build_device_detail_menu(
                    device_id,
                    active=device.get("status") == "active",
                    locked=is_device_slot_locked(device),
                ),
            )
    elif callback.data.startswith("repair_result:"):
        _, kind, result = callback.data.split(":", 2)
        action = f"repair_{kind}_{result}"
        log_activity(callback.from_user.id, action)
        if result == "worked":
            await safe_edit(
                callback,
                f"{BOT_BRAND}\n\nХорошо, я запомнил, что этот сценарий помог.\n"
                "Если понадобится, нажми «Подключить».",
                reply_markup=build_post_config_menu(),
            )
        else:
            _, user = get_user_state(callback.from_user.id)
            await safe_edit(
                callback,
                render_repair_failed_text(user, callback.from_user.id),
                reply_markup=build_support_menu(),
            )
            # Alert admin about stuck user
            await notify_admins(
                callback.message.bot,
                f"{BOT_BRAND} — пользователю не помогла диагностика\n\n"
                f"user_id: {callback.from_user.id}\n"
                f"username: @{callback.from_user.username or '—'}\n"
                f"сценарий: {kind}\n"
                f"тариф: {render_user_plan_value(user) if user else 'нет'}",
            )
    elif callback.data == "help":
        await safe_edit(
            callback,
            render_help_text(),
            reply_markup=build_main_menu(callback.from_user.id),
        )

    await callback.answer()


@router.inline_query()
async def handle_inline_query(inline_query: InlineQuery) -> None:
    """Inline mode: share referral invite in any chat."""
    user_id = inline_query.from_user.id
    invite_link = build_invite_link(user_id)
    summary = get_referral_summary(user_id)

    description = f"{TRIAL_DAYS_TEXT} бесплатно. Приглашений: {summary['opens']}, оплат: {summary['paid']}"
    message_text = (
        f"{BOT_BRAND}\n\n"
        "Персональный профиль подключения по ссылке или QR.\n"
        f"Тестовый период {TRIAL_DAYS_TEXT}.\n\n"
        f"{invite_link}"
    )

    result = InlineQueryResultArticle(
        id="invite",
        title=f"{BOT_BRAND} — пригласить",
        description=description,
        input_message_content=InputTextMessageContent(
            message_text=message_text,
        ),
    )
    await inline_query.answer([result], cache_time=60, is_personal=True)


@router.message()
async def fallback_message(message: Message) -> None:
    logger.info(
        "incoming fallback text=%r from chat_id=%s user_id=%s",
        message.text,
        message.chat.id,
        message.from_user.id,
    )
    pending_device_id = DEVICE_RENAME_PENDING.get(message.from_user.id)
    if pending_device_id:
        raw_text = (message.text or "").strip()
        if raw_text.lower() in {"отмена", "cancel", "/cancel"}:
            DEVICE_RENAME_PENDING.pop(message.from_user.id, None)
            device = get_device(pending_device_id)
            if device and device["user_id"] == message.from_user.id:
                await message.answer(
                    f"{BOT_BRAND}\n\nПереименование отменено.",
                    reply_markup=build_device_detail_menu(
                        pending_device_id,
                        active=device.get("status") == "active",
                        locked=is_device_slot_locked(device),
                    ),
                )
            else:
                await message.answer(f"{BOT_BRAND}\n\nПереименование отменено.")
            return
        try:
            device, final_name = apply_device_rename(message.from_user.id, pending_device_id, raw_text)
        except XrayError as exc:
            await message.answer(str(exc), reply_markup=build_devices_menu(message.from_user.id))
            return
        except RuntimeError as exc:
            await message.answer(
                f"{BOT_BRAND}\n\n{exc}\n\nОтправь другое имя или «отмена».",
                reply_markup=build_devices_menu(message.from_user.id),
            )
            return
        DEVICE_RENAME_PENDING.pop(message.from_user.id, None)
        await message.answer(
            f"{BOT_BRAND}\n\nИмя обновлено: {final_name}",
            reply_markup=build_device_detail_menu(
                pending_device_id,
                active=device.get("status") == "active",
                locked=is_device_slot_locked(device),
            ),
        )
        return
    admin_mode = ADMIN_INPUT_MODE.get(message.from_user.id)
    if is_admin(message.from_user.id) and admin_mode == "admin_user_lookup":
        raw_text = (message.text or "").strip()
        if raw_text.lower() in {"отмена", "cancel", "/cancel"}:
            ADMIN_INPUT_MODE.pop(message.from_user.id, None)
            await message.answer(
                f"{BOT_BRAND} — оператор\n\nВвод user_id отменён.",
                reply_markup=build_admin_menu(),
            )
            return
        if not raw_text.isdigit():
            await message.answer(
                f"{BOT_BRAND} — оператор\n\n"
                "Нужен числовой user_id.\n\n"
                "Пример:\n"
                "2018432227\n\n"
                "Чтобы выйти, отправь «отмена».",
                reply_markup=build_admin_menu(),
            )
            return
        ADMIN_INPUT_MODE.pop(message.from_user.id, None)
        target_user_id = int(raw_text)
        await message.answer(
            render_admin_activation_text(target_user_id),
            reply_markup=build_admin_activation_menu(target_user_id),
        )
        return
    if is_admin(message.from_user.id) and admin_mode == "admin_user_search":
        raw_text = (message.text or "").strip()
        if raw_text.lower() in {"отмена", "cancel", "/cancel"}:
            ADMIN_INPUT_MODE.pop(message.from_user.id, None)
            await message.answer(
                f"{BOT_BRAND} — пользователи\n\nПоиск отменён.",
                reply_markup=build_admin_menu(),
            )
            return
        ADMIN_INPUT_MODE.pop(message.from_user.id, None)
        state = ADMIN_USER_BROWSER_STATE.setdefault(
            message.from_user.id,
            {"status": "all", "search": "", "offset": "0", "page_size": str(ADMIN_USERS_PAGE_SIZE)},
        )
        state["search"] = raw_text.lstrip("@")
        state["offset"] = "0"
        await message.answer(
            render_admin_users_text(message.from_user.id),
            reply_markup=build_admin_users_menu(message.from_user.id),
        )
        return
    state, _ = get_user_state(message.from_user.id)
    if state == "new":
        hint = f"Нажми /start и попробуй {TRIAL_DAYS_TEXT.lower()} бесплатно."
    elif state == "expired":
        hint = "Подписка истекла. Нажми /buy, чтобы продлить."
    elif state in {"trial_active", "paid_active"}:
        hint = "Нажми /config для профиля или /repair для диагностики."
    else:
        hint = "Нажми /start, чтобы открыть меню."
    await message.answer(
        f"{BOT_BRAND}\n\n{hint}", reply_markup=build_main_menu(message.from_user.id)
    )


async def check_expiring_subscriptions(bot: Bot) -> None:
    """Background task: notify users about expiring subscriptions and trial upsell."""
    NOTIFY_BEFORE_DAYS = [3, 1]
    notified: set[tuple[int, str]] = set()

    while True:
        try:
            await asyncio.sleep(3600)  # check every hour
            now = datetime.now()

            # Trial upsell near expiry; shorter trials should upsell later.
            if TRIAL_DAYS <= 3:
                trial_upsell_start = now + timedelta(hours=12)
                trial_upsell_end = now + timedelta(hours=36)
            else:
                trial_upsell_start = now + timedelta(days=1)
                trial_upsell_end = now + timedelta(days=2)
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT user_id, plan, expires_at FROM users
                    WHERE plan = 'trial'
                      AND expires_at > ? AND expires_at <= ?
                    """,
                    (trial_upsell_start.isoformat(), trial_upsell_end.isoformat()),
                )
                trial_rows = cursor.fetchall()

            for row in trial_rows:
                uid = row["user_id"]
                if (uid, "trial_upsell") in notified or has_activity(uid, "trial_upsell_sent"):
                    continue
                expires_at = parse_expires_at(row["expires_at"])
                time_left = format_time_left(expires_at)
                try:
                    await bot.send_message(
                        uid,
                        f"{BOT_BRAND}\n\n"
                        f"Тестовый период заканчивается через {time_left}.\n\n"
                        "Если сервис устраивает, лучше оформить подписку сейчас.\n"
                        "Новый срок прибавится к текущей дате окончания.",
                        reply_markup=build_buy_menu(uid),
                    )
                    notified.add((uid, "trial_upsell"))
                    log_activity(uid, "trial_upsell_sent")
                    logger.info("Sent trial upsell to user %d", uid)
                except Exception as exc:
                    logger.warning("Failed to send trial upsell to %d: %s", uid, exc)

            # --- Pre-expiry reminders (3d, 1d) ---
            for days in NOTIFY_BEFORE_DAYS:
                threshold = now + timedelta(days=days)
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT user_id, plan, expires_at FROM users
                        WHERE expires_at > ? AND expires_at <= ?
                        """,
                        (now.isoformat(), threshold.isoformat()),
                    )
                    rows = cursor.fetchall()

                for row in rows:
                    uid = row["user_id"]
                    key = f"expiry_{days}d"
                    activity_key = f"expiry_reminder_{days}d"
                    if (uid, key) in notified or has_activity(uid, activity_key):
                        continue
                    expires_at = parse_expires_at(row["expires_at"])
                    try:
                        await bot.send_message(
                            uid,
                            f"{BOT_BRAND}\n\n"
                            f"Подписка истекает через {days} {'день' if days == 1 else 'дня'}.\n"
                            f"Активно до: {expires_at.strftime('%d.%m.%Y %H:%M') if expires_at else '?'}\n\n"
                            "Продли подписку, чтобы не потерять доступ.",
                            reply_markup=build_buy_menu(uid),
                        )
                        notified.add((uid, key))
                        log_activity(uid, activity_key)
                        logger.info("Sent %d-day expiry reminder to user %d", days, uid)
                    except Exception as exc:
                        logger.warning("Failed to send expiry reminder to %d: %s", uid, exc)

            # --- Post-expiry notification (just expired in last 2 hours) ---
            expired_since = now - timedelta(hours=2)
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT user_id, plan, expires_at FROM users
                    WHERE expires_at > ? AND expires_at <= ?
                    """,
                    (expired_since.isoformat(), now.isoformat()),
                )
                expired_rows = cursor.fetchall()

            for row in expired_rows:
                uid = row["user_id"]
                if (uid, "just_expired") in notified or has_activity(
                    uid, "post_expiry_notification"
                ):
                    continue
                try:
                    await bot.send_message(
                        uid,
                        f"{BOT_BRAND}\n\n"
                        "Подписка только что истекла.\n"
                        "Профиль больше не работает.\n\n"
                        "Продли сейчас — новый срок начнётся сразу.",
                        reply_markup=build_buy_menu(uid),
                    )
                    notified.add((uid, "just_expired"))
                    log_activity(uid, "post_expiry_notification")
                    logger.info("Sent post-expiry notification to user %d", uid)
                except Exception as exc:
                    logger.warning("Failed to send post-expiry notification to %d: %s", uid, exc)

            # --- Win-back campaigns (day 3, 7, 30 after expiry) ---
            for days_ago, activity_tag, text in [
                (
                    3,
                    "winback_3d",
                    "Мы скучаем! Продли подписку — интернет без ограничений вернётся сразу.",
                ),
                (7, "winback_7d", "Прошла неделя. Возвращайся — /buy и всё работает за секунду."),
                (30, "winback_30d", "Месяц без защиты. Если надумаешь — мы всё ещё здесь. /buy"),
            ]:
                winback_start = now - timedelta(days=days_ago + 1)
                winback_end = now - timedelta(days=days_ago)
                try:
                    with get_db_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            SELECT user_id FROM users
                            WHERE expires_at > ? AND expires_at <= ?
                              AND plan != 'trial'
                            """,
                            (winback_start.isoformat(), winback_end.isoformat()),
                        )
                        winback_rows = cursor.fetchall()
                except Exception:
                    winback_rows = []

                for row in winback_rows:
                    uid = row["user_id"]
                    if (uid, activity_tag) in notified or has_activity(uid, activity_tag):
                        continue
                    try:
                        await bot.send_message(
                            uid,
                            f"{BOT_BRAND}\n\n{text}",
                            reply_markup=build_buy_menu(uid),
                        )
                        notified.add((uid, activity_tag))
                        log_activity(uid, activity_tag)
                        logger.info("Sent %s to user %d", activity_tag, uid)
                    except Exception as exc:
                        logger.debug("Failed to send %s to %d: %s", activity_tag, uid, exc)

            # --- Remove xray clients for expired users ---
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT user_id, vpn_uuid, username FROM users
                        WHERE expires_at IS NOT NULL
                          AND expires_at <= ?
                          AND vpn_uuid IS NOT NULL
                          AND vpn_uuid != ''
                        """,
                        (now.isoformat(),),
                    )
                    expired_with_xray = cursor.fetchall()

                removed_count = 0
                for row in expired_with_xray:
                    uid = row["user_id"]
                    vpn_uuid = row["vpn_uuid"]
                    email = f"tg-{uid}@x0tta6bl4"
                    if (uid, "xray_removed") in notified:
                        continue
                    try:
                        remove_xray_client(vpn_uuid, email)
                        notified.add((uid, "xray_removed"))
                        removed_count += 1
                        logger.info("Removed expired xray client user_id=%d email=%s", uid, email)
                    except Exception as exc:
                        logger.warning(
                            "Failed to remove xray client for expired user %d: %s", uid, exc
                        )
                if removed_count:
                    logger.info("Expired xray cleanup: removed %d clients", removed_count)
            except Exception as exc:
                logger.error("Expired xray cleanup error: %s", exc)

            # Cleanup old entries
            if len(notified) > 10000:
                notified.clear()

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Expiry checker error: %s", exc)
            await asyncio.sleep(60)


async def check_pending_payments(bot: Bot) -> None:
    """Background task: auto-reconcile pending YooMoney payments by label."""
    last_queue_alert_signature: tuple[int, int] | None = None
    last_queue_digest_at: datetime | None = None
    while True:
        try:
            await asyncio.sleep(YOOMONEY_POLL_INTERVAL_SECONDS)
            reminders_sent = await send_pending_payment_reminders(bot)
            if reminders_sent:
                logger.info("sent %d pending payment reminders", reminders_sent)
            last_queue_alert_signature = await maybe_alert_payment_queue_health(
                bot,
                last_queue_alert_signature,
            )
            last_queue_digest_at = await maybe_send_payment_queue_digest(
                bot,
                last_queue_digest_at,
            )
            expired_rows = expire_stale_pending_payments(PENDING_PAYMENT_EXPIRE_HOURS)
            if expired_rows:
                logger.info("expired %d stale pending payments", len(expired_rows))
                for payment in expired_rows:
                    user_id = int(payment["user_id"])
                    payment_id = int(payment["payment_id"])
                    try:
                        await bot.send_message(
                            user_id,
                            f"{BOT_BRAND}\n\n"
                            "Заявка на проверку оплаты истекла.\n"
                            f"payment_id: {payment_id}\n\n"
                            "Если оплата всё ещё актуальна, создай новую заявку через «Купить подписку» или напиши администратору.",
                            reply_markup=build_buy_menu(user_id),
                        )
                    except Exception as exc:
                        logger.warning(
                            "failed to notify expired payment user_id=%s: %s", user_id, exc
                        )
                    await notify_admins_about_payment(
                        bot,
                        payment_id,
                        f"{BOT_BRAND} — заявка истекла автоматически",
                    )
            if not automatic_payment_verification_enabled():
                continue
            approved = await reconcile_pending_payments(bot)
            if approved:
                logger.info("auto-approved %d pending payments", approved)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Pending payment checker error: %s", exc)
            await asyncio.sleep(60)


async def sync_device_activity_loop() -> None:
    while True:
        try:
            await asyncio.sleep(DEVICE_ACTIVITY_SYNC_INTERVAL_SECONDS)
            result = subprocess.run(
                ["python3", DEVICE_ACTIVITY_SYNC_SCRIPT, "--once"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=30,
                env=_sudo_env(),
            )
            logger.info("device activity sync: %s", result.stdout.strip())
        except asyncio.CancelledError:
            break
        except subprocess.CalledProcessError as exc:
            details = (exc.stdout or "").strip()
            logger.warning(
                "device activity sync failed rc=%s output=%s",
                exc.returncode,
                details[:1000] or exc,
            )
            await asyncio.sleep(30)
        except subprocess.TimeoutExpired as exc:
            details = (exc.stdout or exc.stderr or "").strip() if hasattr(exc, "stdout") else ""
            logger.warning(
                "device activity sync timed out after %ss output=%s",
                exc.timeout,
                details[:1000],
            )
            await asyncio.sleep(30)
        except Exception as exc:
            logger.warning("device activity sync failed: %s", exc)
            await asyncio.sleep(30)


async def monitor_xray_health(bot: Bot) -> None:
    """Background task: check xray ports every 2 min, alert admin if down."""
    HEALTH_CHECK_INTERVAL = 120  # seconds
    consecutive_failures = 0
    alerted = False

    while True:
        try:
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            port_health = check_xray_ports_health()
            down_ports = [p for p, alive in port_health.items() if not alive]

            if down_ports:
                consecutive_failures += 1
                logger.warning(
                    "xray health check: ports %s down (consecutive=%d)",
                    down_ports,
                    consecutive_failures,
                )
                # Alert after 2 consecutive failures (4 min down) to avoid false alarms
                if consecutive_failures >= 2 and not alerted:
                    await notify_admins(
                        bot,
                        f"{BOT_BRAND} — СЕРВЕР НЕДОСТУПЕН\n\n"
                        f"Порты не отвечают: {', '.join(str(p) for p in down_ports)}\n"
                        f"Сервер: {VPN_SERVER}\n"
                        f"Подряд проверок: {consecutive_failures}\n\n"
                        "Пользователи не могут подключиться.\n"
                        "Проверь xray / x-ui на VPS.",
                    )
                    alerted = True
                    logger.error("xray health: admin alerted, ports %s down", down_ports)
            else:
                if alerted:
                    await notify_admins(
                        bot,
                        f"{BOT_BRAND} — сервер восстановлен\n\n"
                        f"Все порты отвечают: {', '.join(str(p) for p in port_health)}\n"
                        f"Сервер: {VPN_SERVER}",
                    )
                    logger.info("xray health: recovered, admin notified")
                consecutive_failures = 0
                alerted = False

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("xray health monitor error: %s", exc)
            await asyncio.sleep(30)


def verify_yookassa_webhook_signature(body: bytes, signature: str) -> bool:
    """Verify Yookassa webhook signature using HMAC-SHA256.

    Yookassa sends signature in 'Authorization' header as:
    'Signature: <base64_hmac_sha256>'
    """
    if not YOOKASSA_WEBHOOK_SECRET:
        logger.warning("YOOKASSA_WEBHOOK_SECRET not set, skipping signature verification")
        return True  # Allow in dev mode if not configured

    import hmac
    import hashlib

    expected = hmac.new(
        YOOKASSA_WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()

    # Yookassa sends base64-encoded signature
    try:
        import base64
        decoded_sig = base64.b64decode(signature).hex()
        return hmac.compare_digest(decoded_sig, expected)
    except Exception:
        # Fallback: compare as-is
        return hmac.compare_digest(signature, expected)


async def handle_yookassa_webhook(request):
    """Handle Yookassa payment webhook (POST JSON)."""
    from aiohttp import web
    from time import time

    start_time = time()

    try:
        body = await request.read()
        signature = request.headers.get("Authorization", "").replace("Signature ", "")

        if not verify_yookassa_webhook_signature(body, signature):
            logger.warning("yookassa webhook: invalid signature")
            if WEBHOOK_TOTAL:
                WEBHOOK_TOTAL.labels(provider="yookassa", status="invalid_signature").inc()
            return web.Response(text="INVALID SIGNATURE", status=403)

        try:
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("yookassa webhook: invalid JSON: %s", exc)
            return web.Response(text="BAD REQUEST", status=400)

        event = data.get("event", "")
        payment_obj = data.get("object", {})
        payment_id = payment_obj.get("id", "")
        status = payment_obj.get("status", "")

        logger.info("yookassa webhook: event=%s payment_id=%s status=%s", event, payment_id, status)

        if event != "payment.succeeded":
            logger.info("yookassa webhook: ignoring event %s", event)
            return web.Response(text="OK")

        if status != "succeeded":
            logger.info("yookassa webhook: payment not succeeded, status=%s", status)
            return web.Response(text="OK")

        # Extract metadata
        metadata = payment_obj.get("metadata", {})
        user_id = int(metadata.get("user_id", 0))
        plan_key = metadata.get("plan_key", "")
        local_payment_id = metadata.get("local_payment_id", "")

        if not user_id or not plan_key:
            logger.warning("yookassa webhook: missing user_id/plan_key in metadata")
            return web.Response(text="OK")

        # Idempotency check
        webhook_id = f"yookassa:{payment_id}:{event}"
        if is_webhook_processed(webhook_id, "yookassa"):
            logger.info("yookassa webhook: already processed %s, skipping", webhook_id)
            return web.Response(text="OK")

        bot = request.app["bot"]

        # Find pending payment
        payment = None
        if local_payment_id:
            payment = get_payment(int(local_payment_id))

        if not payment or payment.get("payment_status") != "pending":
            # Try to find by user + plan
            recent = get_recent_payments_for_user(user_id, limit=5, include_internal=True)
            for p in recent:
                if p.get("payment_status") == "pending":
                    p_plan = parse_payment_purchase_key(p)
                    if p_plan == plan_key:
                        payment = p
                        break

        if not payment:
            logger.info("yookassa webhook: no pending payment for user_id=%s plan=%s", user_id, plan_key)
            return web.Response(text="OK")

        # Verify amount
        try:
            remote_amount = float(payment_obj.get("amount", {}).get("value", 0))
            local_amount = float(payment.get("amount", 0))
            if abs(remote_amount - local_amount) > 0.01:
                logger.warning(
                    "yookassa webhook: amount mismatch payment_id=%s remote=%.2f local=%.2f",
                    payment.get("payment_id"), remote_amount, local_amount
                )
                return web.Response(text="AMOUNT MISMATCH", status=400)
        except (TypeError, ValueError):
            logger.warning("yookassa webhook: amount parse error")
            return web.Response(text="BAD REQUEST", status=400)

        # Approve payment
        try:
            user = await approve_pending_payment_with_provider(
                bot,
                payment,
                plan_key,
                build_completed_provider(payment, int(payment["payment_id"]), plan_key, "auto"),
                notify_user=False,
            )
        except XrayError as exc:
            logger.error("yookassa webhook xray failure payment_id=%s: %s", payment.get("payment_id"), exc)
            try:
                await notify_admins_about_payment(
                    bot,
                    int(payment["payment_id"]),
                    f"{BOT_BRAND} — ОШИБКА: provisioning не удался после оплаты yookassa",
                )
            except Exception as alert_exc:
                logger.warning("failed to alert admins: %s", alert_exc)
            return web.Response(text="ERROR", status=500)

        if not user:
            logger.info("yookassa webhook: payment already processed payment_id=%s", payment.get("payment_id"))
            return web.Response(text="OK")

        # Record webhook as processed
        record_webhook_processed(webhook_id, "yookassa", "success")

        # Notify user
        plan = PLANS.get(plan_key, {})
        text = (
            f"{BOT_BRAND}\n\n"
            "Оплата подтверждена.\n"
            f"Тариф: {plan.get('label', plan_key)}\n"
            f"До: {user.get('expires_at', '')[:16].replace('T', ' ')}"
        )
        try:
            await bot.send_message(user_id, text, reply_markup=build_payment_success_menu())
        except Exception as exc:
            logger.warning("yookassa webhook: failed to notify user %s: %s", user_id, exc)

        logger.info("yookassa webhook: activated plan=%s for user_id=%s payment_id=%s", plan_key, user_id, payment_id)
        return web.Response(text="OK")

    except Exception as exc:
        logger.error("yookassa webhook error: %s", exc, exc_info=True)
        return web.Response(text="ERROR", status=500)


async def handle_cardlink_webhook(request):
    """Handle CardLink payment result webhook (POST form-urlencoded)."""
    from aiohttp import web
    from time import time

    start_time = time()

    try:
        data = await request.post()
        inv_id = data.get("InvId", "")
        out_sum = data.get("OutSum", "")
        status = data.get("Status", "")
        signature = data.get("SignatureValue", "")
        custom_raw = data.get("custom", "{}")
        order_id = inv_id

        logger.info("cardlink webhook: InvId=%s Status=%s OutSum=%s", inv_id, status, out_sum)

        if not verify_cardlink_signature(out_sum, inv_id, signature):
            logger.warning("cardlink webhook: invalid signature for InvId=%s", inv_id)
            if WEBHOOK_TOTAL:
                WEBHOOK_TOTAL.labels(provider="cardlink", status="invalid_signature").inc()
            return web.Response(text="INVALID SIGNATURE", status=403)

        if status != "SUCCESS":
            logger.info("cardlink webhook: non-success status %s for InvId=%s", status, inv_id)
            return web.Response(text="OK")

        # Idempotency protection: check if this webhook was already processed
        webhook_id = f"cardlink:{inv_id}:{out_sum}"
        if is_webhook_processed(webhook_id, "cardlink"):
            logger.info("cardlink webhook: already processed %s, skipping", webhook_id)
            return web.Response(text="OK")

        try:
            custom = json.loads(custom_raw)
        except (json.JSONDecodeError, TypeError):
            custom = {}
        user_id = int(custom.get("user_id", 0))
        plan_key = custom.get("plan_key", "")

        if not user_id or not plan_key:
            logger.warning("cardlink webhook: missing user_id/plan_key in custom: %s", custom_raw)
            return web.Response(text="OK")

        existing_processed = get_processed_cardlink_payment(user_id, inv_id)
        if existing_processed:
            logger.info(
                "cardlink webhook: duplicate delivery ignored for processed order user_id=%s inv_id=%s payment_id=%s",
                user_id,
                inv_id,
                existing_processed.get("payment_id"),
            )
            return web.Response(text="OK")

        bot = request.app["bot"]
        payment = get_matching_cardlink_pending_payment(user_id, plan_key, order_id=inv_id)
        if not payment:
            logger.info(
                "cardlink webhook: no pending local payment for user_id=%s plan=%s inv_id=%s",
                user_id,
                plan_key,
                inv_id,
            )
            return web.Response(text="OK")
        if payment.get("payment_status") != "pending":
            logger.info(
                "cardlink webhook: local payment already processed payment_id=%s status=%s",
                payment.get("payment_id"),
                payment.get("payment_status"),
            )
            return web.Response(text="OK")

        try:
            user = await approve_pending_payment_with_provider(
                bot,
                payment,
                plan_key,
                build_completed_provider(payment, int(payment["payment_id"]), plan_key, "auto"),
                notify_user=False,
            )
        except XrayError as exc:
            logger.error(
                "cardlink webhook xray failure payment_id=%s: %s", payment.get("payment_id"), exc
            )
            if PROVISIONING_FAILURES:
                PROVISIONING_FAILURES.labels(provider="cardlink").inc()
            if PAYMENT_TOTAL:
                PAYMENT_TOTAL.labels(provider="cardlink", status="provisioning_error").inc()
            # Alert admins about provisioning failure
            try:
                await notify_admins_about_payment(
                    bot,
                    int(payment["payment_id"]),
                    f"{BOT_BRAND} — ОШИБКА: provisioning не удался после оплаты cardlink",
                )
            except Exception as alert_exc:
                logger.warning("failed to alert admins about xray failure: %s", alert_exc)
            return web.Response(text="ERROR", status=500)
        if not user:
            logger.info(
                "cardlink webhook: payment already processed payment_id=%s",
                payment.get("payment_id"),
            )
            return web.Response(text="OK")

        plan = PLANS.get(plan_key, {})
        text = (
            f"{BOT_BRAND}\n\n"
            "Оплата подтверждена.\n"
            f"Тариф: {plan.get('label', plan_key)}\n"
            f"До: {user.get('expires_at', '')[:16].replace('T', ' ')}"
        )
        try:
            await bot.send_message(user_id, text, reply_markup=build_payment_success_menu())
        except Exception as exc:
            logger.warning("cardlink webhook: failed to notify user %s: %s", user_id, exc)

        # Record webhook as processed for idempotency
        record_webhook_processed(webhook_id, "cardlink", "success")

        logger.info(
            "cardlink webhook: activated plan=%s for user_id=%s inv_id=%s",
            plan_key,
            user_id,
            inv_id,
        )
        return web.Response(text="OK")
    except Exception as exc:
        logger.error("cardlink webhook error: %s", exc, exc_info=True)
        return web.Response(text="ERROR", status=500)


def parse_vpn_client_ua(ua: str) -> dict[str, str]:
    """Parse VPN client User-Agent into structured device info."""
    result = {
        "client_app": "",
        "client_version": "",
        "platform": "",
        "os_version": "",
        "device_model": "",
        "display": "",
    }
    if not ua:
        return result

    ua_lower = ua.lower()

    # Known VPN client patterns
    clients = [
        ("hiddifynext", "Hiddify"),
        ("hiddify", "Hiddify"),
        ("v2rayng", "v2rayNG"),
        ("v2rayn", "v2rayN"),
        ("streisand", "Streisand"),
        ("shadowrocket", "Shadowrocket"),
        ("flclash", "FlClash"),
        ("clashx", "ClashX"),
        ("clash", "Clash"),
        ("nekoray", "NekoRay"),
        ("nekobox", "NekoBox"),
        ("sing-box", "sing-box"),
        ("karing", "Karing"),
        ("v2raytun", "v2RayTun"),
        ("happ", "Happ"),
        ("foxray", "FoXray"),
    ]
    for pattern, name in clients:
        if pattern in ua_lower:
            result["client_app"] = name
            break

    # Extract version: look for /X.Y.Z or /vX.Y.Z
    import re

    ver_match = re.search(r"/v?(\d+\.\d+(?:\.\d+)?)", ua)
    if ver_match:
        result["client_version"] = ver_match.group(1)

    # Platform detection
    if "android" in ua_lower:
        result["platform"] = "Android"
        android_ver = re.search(r"Android\s+(\d+(?:\.\d+)?)", ua, re.IGNORECASE)
        if android_ver:
            result["os_version"] = android_ver.group(1)
    elif "iphone" in ua_lower or "ios" in ua_lower:
        result["platform"] = "iOS"
        ios_ver = re.search(r"iOS\s+(\d+(?:\.\d+)?)", ua, re.IGNORECASE)
        if ios_ver:
            result["os_version"] = ios_ver.group(1)
    elif "windows" in ua_lower:
        result["platform"] = "Windows"
        win_ver = re.search(r"Windows\s+(?:NT\s+)?(\d+(?:\.\d+)?)", ua, re.IGNORECASE)
        if win_ver:
            result["os_version"] = win_ver.group(1)
    elif "macos" in ua_lower or "darwin" in ua_lower or "mac os" in ua_lower:
        result["platform"] = "macOS"
    elif "linux" in ua_lower:
        result["platform"] = "Linux"
        linux_ver = re.search(r"(?:Ubuntu|Fedora|Debian)[\s/]*(\d+(?:\.\d+)?)", ua, re.IGNORECASE)
        if linux_ver:
            result["os_version"] = linux_ver.group(1)

    # Device model (from parentheses, common in mobile UAs)
    model_match = re.search(r";\s*([A-Za-z][\w\s\-]+?)(?:\s+Build|\))", ua)
    if model_match:
        result["device_model"] = model_match.group(1).strip()

    # Build display string
    parts = []
    if result["client_app"]:
        app_str = result["client_app"]
        if result["client_version"]:
            app_str += f" {result['client_version']}"
        parts.append(app_str)
    if result["platform"]:
        plat_str = result["platform"]
        if result["os_version"]:
            plat_str += f" {result['os_version']}"
        parts.append(plat_str)
    if result["device_model"]:
        parts.append(result["device_model"])
    result["display"] = " / ".join(parts) if parts else ua[:60]

    return result


async def notify_new_device(bot, user_id: int, access: dict, parsed: dict, token: str) -> None:
    """Send new device notification to user."""
    device_count = count_human_subscription_accesses(user_id)
    if device_count <= 1:
        mark_subscription_access_notified(access["access_id"])
        return
    model_line = parsed.get("device_model") or access.get("device_model") or ""
    platform_line = ""
    plat = parsed.get("platform") or access.get("platform") or ""
    os_ver = parsed.get("os_version") or access.get("os_version") or ""
    if plat:
        platform_line = plat
        if os_ver:
            platform_line += f" / {os_ver}"
    raw_ua = access.get("user_agent", "")
    first_seen = access.get("first_seen_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    lines = [
        f"{BOT_BRAND}\n",
        "🆕 Новое устройство подключено!\n",
        f"🔑 Подписка: {token[:8]}",
    ]
    if model_line:
        lines.append(f"📱 Модель: {model_line}")
    if platform_line:
        lines.append(f"🧠 Платформа: {platform_line}")
    lines.append(f"🌐 User-Agent: {raw_ua[:80]}")
    lines.append(f"🕓 Время подключения: {first_seen}")
    lines.append(f"📊 Всего устройств: {device_count}")
    lines.append(
        "\nЕсли это не ваше устройство — перевыпустите подписку "
        "через /devices, чтобы заблокировать доступ."
    )

    try:
        kb = InlineKeyboardBuilder()
        kb.button(text="Мои устройства", callback_data="devices")
        kb.button(text="Главное меню", callback_data="menu")
        kb.adjust(1)
        await bot.send_message(user_id, "\n".join(lines), reply_markup=kb.as_markup())
        mark_subscription_access_notified(access["access_id"])
        logger.info(
            "new device notification sent to user_id=%d ua=%s",
            user_id,
            access.get("user_agent", "")[:50],
        )
    except Exception as exc:
        logger.warning("failed to send new device notification to %d: %s", user_id, exc)


async def _notify_admins_abuse(bot, user_id: int, device_count: int, limit: int, ip: str) -> None:
    """Alert admins when a user has suspiciously many subscription accesses."""
    if has_activity(user_id, "abuse_alert_sent"):
        return
    text = (
        f"⚠️ Подозрение на шаринг\n\n"
        f"user_id: {user_id}\n"
        f"Уникальных UA: {device_count} (лимит: {limit})\n"
        f"Последний IP: {ip}\n\n"
        f"/admin_user {user_id}"
    )
    for admin_id in ADMIN_USER_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass
    log_activity(user_id, "abuse_alert_sent")
    logger.warning(
        "abuse alert: user_id=%d devices=%d limit=%d ip=%s", user_id, device_count, limit, ip
    )


def _subscription_probe_ips() -> set[str]:
    return {"127.0.0.1", "::1"}


def _subscription_probe_user_agent_prefixes() -> tuple[str, ...]:
    return (
        "curl/",
        "python-urllib/",
        "python-requests/",
        "aiohttp/",
        "diag-probe/",
        "post-deploy-probe/",
        "ghost-access-canary/",
        "ghost-access-probe/",
        "monitoring-agent/",
        "go-http-client/",
    )


def is_technical_subscription_access(
    user_agent: str,
    client_ip: str | None = None,
    *,
    probe_header: str | None = None,
) -> bool:
    ua_lower = (user_agent or "").strip().lower()
    header_value = (probe_header or "").strip().lower()
    if header_value and header_value not in {"0", "false", "no"}:
        return True
    if any(ua_lower.startswith(prefix) for prefix in _subscription_probe_user_agent_prefixes()):
        return True
    if (client_ip or "").strip() in _subscription_probe_ips():
        return True
    return False


def count_human_subscription_accesses(user_id: int) -> int:
    return sum(
        1
        for access in get_subscription_accesses(user_id)
        if not is_technical_subscription_access(
            str(access.get("user_agent") or ""),
            access.get("ip_address"),
        )
    )


def check_subscription_rate_limit(token: str, client_ip: str | None) -> tuple[bool, int]:
    """Apply a small in-memory limiter to subscription refresh bursts."""
    if SUBSCRIPTION_RATE_LIMIT_MAX_REQUESTS <= 0 or SUBSCRIPTION_RATE_LIMIT_WINDOW_SECONDS <= 0:
        return True, 0

    now = time.monotonic()
    cutoff = now - SUBSCRIPTION_RATE_LIMIT_WINDOW_SECONDS
    key = f"{token}|{(client_ip or 'unknown').strip() or 'unknown'}"

    with _SUBSCRIPTION_RATE_LIMIT_LOCK:
        bucket = [
            ts for ts in _SUBSCRIPTION_RATE_LIMIT_STATE.get(key, []) if ts >= cutoff
        ]
        if len(bucket) >= SUBSCRIPTION_RATE_LIMIT_MAX_REQUESTS:
            oldest = bucket[0]
            retry_after = max(1, int(SUBSCRIPTION_RATE_LIMIT_WINDOW_SECONDS - (now - oldest)))
            _SUBSCRIPTION_RATE_LIMIT_STATE[key] = bucket
            return False, retry_after

        bucket.append(now)
        _SUBSCRIPTION_RATE_LIMIT_STATE[key] = bucket

        if len(_SUBSCRIPTION_RATE_LIMIT_STATE) > 4096:
            stale_before = now - (SUBSCRIPTION_RATE_LIMIT_WINDOW_SECONDS * 2)
            stale_keys = [
                state_key
                for state_key, timestamps in _SUBSCRIPTION_RATE_LIMIT_STATE.items()
                if not timestamps or timestamps[-1] < stale_before
            ]
            for state_key in stale_keys[:1024]:
                _SUBSCRIPTION_RATE_LIMIT_STATE.pop(state_key, None)

    return True, 0


def _build_stub_profiles(messages: list[str]) -> str:
    """Build fake VLESS profiles that show as text messages in client app."""
    lines = []
    for msg in messages:
        stub_uuid = str(uuid.uuid4())
        fragment = quote(msg, safe="")
        lines.append(f"<REDACTED_VPN_URI>")
    return base64.b64encode("\n".join(lines).encode("utf-8")).decode("ascii")


def _subscription_base_headers(title_suffix: str = "") -> dict[str, str]:
    """Common subscription response headers."""
    raw_title = f"{BOT_BRAND}{title_suffix}"
    return {
        "Content-Type": "text/plain; charset=utf-8",
        "profile-title": f"base64:{base64.b64encode(raw_title.encode('utf-8')).decode('ascii')}",
        "profile-update-interval": "1",
        "profile-web-page-url": f"https://t.me/{BOT_USERNAME}",
        "support-url": (
            f"https://t.me/{SUPPORT_USERNAME}?start=support"
            if SUPPORT_USERNAME
            else f"https://t.me/{BOT_USERNAME}?start=support"
        ),
        "x-robots-tag": "noindex, nofollow, noarchive, nosnippet, noimageindex",
    }


async def handle_subscription_request(request):
    """Serve a Telegram-only subscription feed for compatible VPN clients."""
    from aiohttp import web

    token = (request.match_info.get("token") or "").strip()
    client_ip = request.headers.get("X-Real-IP") or request.remote
    rate_limit_token = token or "__empty__"
    allowed, retry_after = check_subscription_rate_limit(rate_limit_token, client_ip)
    if not allowed:
        throttled_user = get_user_by_subscription_token(token) if token else None
        payload = _build_stub_profiles(
            [
                "⚠️ Слишком много обновлений",
                "👇 Повторите попытку чуть позже",
                f"@{BOT_USERNAME}",
            ]
        )
        headers = _subscription_base_headers(" — лимит")
        if throttled_user:
            throttled_user_id = int(throttled_user["user_id"])
            headers["Content-Disposition"] = f'attachment; filename="tg_{throttled_user_id}"'
            log_activity(throttled_user_id, "subscription_rate_limited")
        else:
            headers["Content-Disposition"] = 'attachment; filename="throttled"'
        headers["Retry-After"] = str(retry_after)
        logger.warning(
            "subscription rate limited token=%s ip=%s retry_after=%ss",
            rate_limit_token[:16],
            client_ip,
            retry_after,
        )
        return web.Response(text=payload, headers=headers, status=429)

    user = get_user_by_subscription_token(token)
    offline = None if user else get_offline_subscription_by_token(token)
    if not user and not offline:
        payload = _build_stub_profiles(
            [
                "⚠️ Подписка не найдена",
                f"👇 Откройте бота @{BOT_USERNAME}",
            ]
        )
        headers = _subscription_base_headers()
        headers["Content-Disposition"] = 'attachment; filename="unknown"'
        return web.Response(text=payload, headers=headers, status=404)

    user_id = int(user["user_id"]) if user else None
    expires_at = parse_expires_at((user or offline or {}).get("expires_at"))

    if not expires_at or datetime.now() > expires_at:
        payload = _build_stub_profiles(
            [
                "⏰ Подписка истекла",
                "👇 Продлите в боте — доступ вернётся сразу",
                f"@{BOT_USERNAME}",
            ]
        )
        headers = _subscription_base_headers(" — истекла")
        filename = f'tg_{user_id}' if user_id is not None else "offline_expired"
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        if expires_at:
            headers["subscription-userinfo"] = (
                f"upload=0; download=0; total=0; expire={int(expires_at.timestamp())}"
            )
        announce_text = "⏰ Подписка истекла. Продлите в боте."
        headers["announce"] = (
            f"base64:{base64.b64encode(announce_text.encode('utf-8')).decode('ascii')}"
        )
        return web.Response(text=payload, headers=headers)

    ua = request.headers.get("User-Agent", "")
    ua_lower = ua.lower()
    force_raw_for_client = any(marker in ua_lower for marker in ("hiddify", "v2raytun"))
    raw = (request.query.get("format") or "").strip().lower() == "raw" or force_raw_for_client
    health_policy = build_subscription_health_policy()
    if user:
        payload = build_subscription_payload(user, raw=raw, health_policy=health_policy)
    else:
        payload = build_subscription_payload_for_offline(
            offline,
            raw=raw,
            health_policy=health_policy,
        )
    if not payload.strip():
        payload = _build_stub_profiles(
            [
                "⚠️ Нет активного устройства",
                "👇 Откройте бота и нажмите «Подключить»",
                f"@{BOT_USERNAME}",
            ]
        )
        raw = False
    if user_id is not None:
        filename = f"tg_{user_id}_all"
        primary = get_primary_device(user_id)
        ordered_primary_uuid = primary["vpn_uuid"] if primary else ""
        effective_transport = resolve_user_preferred_transport(user, health_policy)
    else:
        filename = f"offline_{str((offline or {}).get('claim_code') or 'sub').lower()}"
        ordered_primary_uuid = str((offline or {}).get("vpn_uuid") or "")
        effective_transport = resolve_user_preferred_transport(None, health_policy)

    time_left = format_time_left(expires_at)
    headers = _subscription_base_headers(f" — {time_left}")
    headers.update(
        {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "profile-update-interval": health_policy["profile_update_interval"],
            "subscription-userinfo": (
                f"upload=0; download=0; total=0; expire={int(expires_at.timestamp())}"
            ),
            "subscription-refill-date": str(int(expires_at.timestamp())),
            "x-primary-uuid": ordered_primary_uuid,
            "x-health-status": health_policy["health_status"],
            "x-health-source": health_policy["health_source"],
            "x-preferred-transport": effective_transport,
        }
    )
    if user_id is not None:
        headers["id"] = str(user_id)
        headers["x-egress-mode"] = get_user_egress_mode(user_id)
    if health_policy.get("health_generated_at"):
        headers["x-health-generated-at"] = health_policy["health_generated_at"]
    if health_policy.get("transport_health_status"):
        headers["x-transport-health-status"] = health_policy["transport_health_status"]
    if health_policy.get("subscription_health_status"):
        headers["x-subscription-health-status"] = health_policy["subscription_health_status"]
    if health_policy.get("best_path"):
        headers["x-best-path"] = health_policy["best_path"]
    if health_policy.get("reality_canary_total_s"):
        headers["x-reality-canary-total-s"] = health_policy["reality_canary_total_s"]
    if health_policy.get("reality_canary_http_code"):
        headers["x-reality-canary-http-code"] = health_policy["reality_canary_http_code"]
    if health_policy.get("secondary_reality_canary_total_s"):
        headers["x-secondary-reality-canary-total-s"] = health_policy[
            "secondary_reality_canary_total_s"
        ]
    if health_policy.get("secondary_reality_canary_http_code"):
        headers["x-secondary-reality-canary-http-code"] = health_policy[
            "secondary_reality_canary_http_code"
        ]
    if health_policy.get("subscription_direct_total_s"):
        headers["x-subscription-direct-total-s"] = health_policy["subscription_direct_total_s"]
    if health_policy.get("primary_path_latency_s"):
        headers["x-primary-path-latency-s"] = health_policy["primary_path_latency_s"]
    if health_policy.get("secondary_path_latency_s"):
        headers["x-secondary-path-latency-s"] = health_policy["secondary_path_latency_s"]
    if health_policy.get("fallback_nl_path_latency_s"):
        headers["x-fallback-nl-path-latency-s"] = health_policy["fallback_nl_path_latency_s"]
    if health_policy.get("announce"):
        raw_announce = health_policy["announce"]
        headers["announce"] = (
            f"base64:{base64.b64encode(raw_announce.encode('utf-8')).decode('ascii')}"
        )

    # --- New device detection + abuse check ---
    if ua and user_id is not None:
        try:
            probe_header = request.headers.get("X-Ghost-Access-Probe", "")
            if is_technical_subscription_access(ua, client_ip, probe_header=probe_header):
                logger.info(
                    "subscription access treated as technical probe user_id=%s ip=%s ua=%s header=%s",
                    user_id,
                    client_ip,
                    ua[:120],
                    probe_header[:80],
                )
                return web.Response(text=payload, headers=headers)
            parsed = parse_vpn_client_ua(ua)
            new_access = record_subscription_access(
                user_id,
                ua,
                ip_address=client_ip,
                parsed=parsed,
            )
            if new_access and request.app.get("bot"):
                asyncio.create_task(
                    notify_new_device(request.app["bot"], user_id, new_access, parsed, token)
                )
                # Access logging is advisory for delivery. If it succeeds, keep the
                # existing abuse heuristic; if it fails, the subscription must still
                # be served to the client.
                device_count = count_human_subscription_accesses(user_id)
                user_device_limit = get_device_limit(get_user(user_id))
                if device_count > user_device_limit + 3:
                    asyncio.create_task(
                        _notify_admins_abuse(
                            request.app["bot"],
                            user_id,
                            device_count,
                            user_device_limit,
                            client_ip,
                        )
                    )
        except Exception as exc:
            logger.warning(
                "subscription access logging failed user_id=%s ip=%s ua=%s: %s",
                user_id,
                client_ip,
                ua[:120],
                exc,
            )

    return web.Response(text=payload, headers=headers)


async def handle_android_stealth_bundle_request(request):
    """Serve the Android stealth JSON bundle for opt-in SPB users."""
    from aiohttp import web

    token = (request.match_info.get("token") or "").strip()
    client_ip = request.headers.get("X-Real-IP") or request.remote
    rate_limit_token = token or "__empty__"
    allowed, retry_after = check_subscription_rate_limit(rate_limit_token, client_ip)
    if not allowed:
        user = get_user_by_subscription_token(token) if token else None
        headers = {"Retry-After": str(retry_after), "Cache-Control": "no-store"}
        if user:
            log_activity(int(user["user_id"]), "android_stealth_bundle_rate_limited")
        return web.json_response(
            {
                "status": "rate_limited",
                "retry_after": retry_after,
                "detail": "Too many bundle refreshes",
            },
            status=429,
            headers=headers,
        )

    user = get_user_by_subscription_token(token)
    if not user:
        return web.json_response(
            {"status": "not_found", "detail": "Subscription bundle not found"},
            status=404,
            headers={"Cache-Control": "no-store"},
        )

    if not is_android_stealth_profile(user):
        return web.json_response(
            {
                "status": "profile_mismatch",
                "detail": "Android stealth mode is not enabled for this subscription",
                "expected_profile": DELIVERY_PROFILE_ANDROID_STEALTH_SPB,
                "current_profile": resolve_delivery_profile(user),
            },
            status=409,
            headers={"Cache-Control": "no-store"},
        )

    expires_at = parse_expires_at(user.get("expires_at"))
    if not expires_at or datetime.now() > expires_at:
        return web.json_response(
            {"status": "expired", "detail": "Subscription expired"},
            status=403,
            headers={"Cache-Control": "no-store"},
        )

    try:
        bundle = build_android_stealth_bundle(
            user,
            health_policy=build_subscription_health_policy(),
        )
    except RuntimeError as exc:
        logger.warning(
            "android stealth bundle unavailable user_id=%s: %s",
            user.get("user_id"),
            exc,
        )
        return web.json_response(
            {
                "status": "device_required",
                "detail": "Android stealth bundle requires an active device",
            },
            status=409,
            headers={"Cache-Control": "no-store"},
        )

    headers = {
        "Cache-Control": "no-store",
        "Content-Disposition": f'attachment; filename="tg_{int(user["user_id"])}_android_stealth.json"',
        "x-delivery-profile": DELIVERY_PROFILE_ANDROID_STEALTH_SPB,
        "x-entry-node": resolve_entry_node(user),
    }
    return web.Response(
        text=json.dumps(bundle, ensure_ascii=False),
        content_type="application/json",
        headers=headers,
    )


async def handle_access_portal_request(request):
    """Serve a Telegram-free HTML access page for a subscription token."""
    from aiohttp import web

    token = (request.match_info.get("token") or "").strip()
    user = get_user_by_subscription_token(token) if token else None
    offline = None if user else get_offline_subscription_by_token(token)

    if not user and not offline:
        return web.Response(
            text=render_web_access_portal(
                title="Доступ не найден",
                subtitle="Эта ссылка недействительна или уже была заменена. Запроси новую у оператора.",
                plan_label="—",
                expires_at=None,
                main_link="",
                subscription_url="",
                status="expired",
            ),
            status=404,
            content_type="text/html",
            headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow, noarchive, nosnippet, noimageindex"},
        )

    record = user or offline or {}
    expires_at = parse_expires_at(record.get("expires_at"))
    is_active = bool(expires_at and datetime.now() <= expires_at)
    token_url = build_subscription_url_from_token(token)
    if user:
        title = f"{BOT_BRAND} — доступ"
        subtitle = "Подключай профиль прямо с этой страницы без Telegram."
        plan_label = render_plan_label(str(user.get("plan") or ""))
        main_link = build_delivery_connect_url(user)
        direct_link = generate_vless_link(str(user.get("vpn_uuid") or "")) if user.get("vpn_uuid") else ""
        fallback_link = generate_fallback_link(str(user.get("vpn_uuid") or "")) if user.get("vpn_uuid") else ""
        android_bundle_url = (
            build_android_stealth_bundle_url_from_token(token) if is_android_stealth_profile(user) else ""
        )
        if direct_link and main_link == token_url:
            main_link = direct_link
        claim_code = ""
    else:
        title = f"{BOT_BRAND} — офлайн-доступ"
        subtitle = "Это прямая страница подключения для пользователя без Telegram."
        plan_label = render_plan_label(str(offline.get("plan") or ""))
        offline_uuid = str(offline.get("vpn_uuid") or "")
        offline_delivery_profile = str(offline.get("delivery_profile") or "").strip()
        offline_entry_node = str(offline.get("entry_node") or "").strip()
        if not offline_uuid:
            main_link = token_url
            fallback_link = ""
        elif offline_delivery_profile == DELIVERY_PROFILE_ANDROID_STEALTH_SPB or offline_entry_node == ENTRY_NODE_SPB:
            main_link = generate_spb_reality_link(offline_uuid, label=(offline.get("label") or f"{BOT_BRAND} • Offline").strip())
            fallback_link = ""
        else:
            main_link = generate_vless_link(offline_uuid)
            fallback_link = generate_fallback_link(offline_uuid)
        android_bundle_url = ""
        claim_code = str(offline.get("claim_code") or "")

    portal_html = render_web_access_portal(
        title=title,
        subtitle=subtitle,
        plan_label=plan_label,
        expires_at=expires_at,
        main_link=main_link,
        subscription_url=token_url,
        fallback_link=fallback_link,
        android_bundle_url=android_bundle_url,
        claim_code=claim_code,
        status="active" if is_active else "expired",
    )
    return web.Response(
        text=portal_html,
        status=200 if is_active else 403,
        content_type="text/html",
        headers={
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex, nofollow, noarchive, nosnippet, noimageindex",
        },
    )


async def handle_health_check(request):
    """Health endpoint for nginx/uptime monitoring."""
    from aiohttp import web

    port_health = check_xray_ports_health()
    all_ok = all(port_health.values())
    agent_payload, _stale, _source_path = load_vpn_service_agent_payload()
    agent_payload = agent_payload or {}
    tasks = request.app.get("background_tasks", {})
    task_state = {
        name: ("done" if task.done() else "running")
        for name, task in tasks.items()
        if task is not None
    }
    body = json.dumps(
        {
            "status": "ok" if all_ok else "degraded",
            "xray_ports": {str(p): alive for p, alive in port_health.items()},
            "server": VPN_SERVER,
            "provider": get_active_payment_provider(),
            "subscription_base_url": subscription_base_url(),
            "background_tasks": task_state,
            "monitor_generated_at": agent_payload.get("generated_at"),
            "ts": datetime.now().isoformat(),
        }
    )
    return web.Response(
        text=body,
        content_type="application/json",
        status=200 if all_ok else 503,
    )


async def start_http_server(bot: Bot, background_tasks: dict[str, asyncio.Task]) -> object:
    """Start aiohttp server for bot-adjacent HTTP endpoints."""
    from aiohttp import web

    app = web.Application()
    app["bot"] = bot
    app["background_tasks"] = background_tasks
    app.router.add_get("/health", handle_health_check)
    app.router.add_get("/health/ready", handle_health_check)
    app.router.add_get("/sub/{token}", handle_subscription_request)
    app.router.add_get("/access/{token}", handle_access_portal_request)
    app.router.add_get(
        "/bundle/{token}/android-stealth.json",
        handle_android_stealth_bundle_request,
    )
    if cardlink_configured():
        app.router.add_post("/cardlink/result", handle_cardlink_webhook)
    if yookassa_configured():
        app.router.add_post("/webhook/yookassa", handle_yookassa_webhook)
        logger.info("Yookassa webhook endpoint registered at /webhook/yookassa")
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", SUBSCRIPTION_HTTP_PORT)
    await site.start()
    logger.info(
        "HTTP endpoints started on port %d (subscription base=%s cardlink=%s)",
        SUBSCRIPTION_HTTP_PORT,
        subscription_base_url(),
        cardlink_configured(),
    )
    return runner


async def cancel_task(task: asyncio.Task | None, label: str) -> None:
    if task is None or task.done():
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        logger.info("%s cancelled", label)
    except Exception as exc:
        logger.warning("%s shutdown error: %s", label, exc)


async def main() -> None:
    acquire_single_instance_lock()
    init_database()
    onboarding_logic.register_bot_services(
        build_subscription_url=build_subscription_url,
        send_subscription_bundle=send_subscription_bundle,
        ensure_user_trial=ensure_user_trial,
        claim_operator_issued_subscription=claim_operator_issued_subscription,
    )
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # Register bot commands in Telegram menu
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="trial", description=f"{TRIAL_DAYS_TEXT} бесплатно"),
            BotCommand(command="config", description="Получить профиль"),
            BotCommand(command="status", description="Статус подписки"),
            BotCommand(command="buy", description="Купить подписку"),
            BotCommand(command="guide", description="Как подключить профиль"),
            BotCommand(command="repair", description="Диагностика подключения"),
            BotCommand(command="whoami", description="Показать Telegram ID"),
            BotCommand(command="help", description="Справка"),
        ]
    )

    expiry_task = asyncio.create_task(check_expiring_subscriptions(bot))
    payment_task = asyncio.create_task(check_pending_payments(bot))
    device_sync_task = asyncio.create_task(sync_device_activity_loop())
    health_task = asyncio.create_task(monitor_xray_health(bot))
    background_tasks = {
        "expiry_task": expiry_task,
        "payment_task": payment_task,
        "device_sync_task": device_sync_task,
        "health_task": health_task,
    }
    http_runner = await start_http_server(bot, background_tasks)

    try:
        if TELEGRAM_POLLING_ENABLED:
            logger.info("starting bot polling for %s:%s instance=%s", VPN_SERVER, VPN_PORT, INSTANCE_TAG)
            await bot.delete_webhook(drop_pending_updates=True)
            try:
                await dp.start_polling(bot)
            except TelegramConflictError as exc:
                logger.error("telegram polling conflict detected: %s", exc)
                await notify_admins(
                    bot,
                    f"{BOT_BRAND} — конфликт polling\n\n"
                    f"Инстанс: {INSTANCE_TAG}\n"
                    f"Lock file: {BOT_SINGLETON_LOCK_FILE}\n\n"
                    "Telegram сообщил, что другой процесс уже использует getUpdates для этого бота.\n"
                    "Нужно остановить второй poller, иначе self-service и платежная автоматизация будут нестабильны.",
                    reply_markup=build_admin_menu(),
                )
                raise SystemExit("telegram polling conflict")
        else:
            logger.info(
                "telegram polling disabled; keeping HTTP/background tasks only instance=%s",
                INSTANCE_TAG,
            )
            await asyncio.Event().wait()
    finally:
        global _XRAY_RELOAD_TASK
        for label, task in (
            ("expiry_task", expiry_task),
            ("payment_task", payment_task),
            ("device_sync_task", device_sync_task),
            ("health_task", health_task),
            ("xray_reload_task", _XRAY_RELOAD_TASK),
        ):
            await cancel_task(task, label)
        await http_runner.cleanup()
        await bot.session.close()
        logger.info("background tasks cancelled, http runner cleaned up, releasing lock")
        release_single_instance_lock()


if __name__ == "__main__":
    asyncio.run(main())
