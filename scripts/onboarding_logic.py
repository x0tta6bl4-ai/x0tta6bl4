"""Onboarding Logic for Ghost Access Bot (Phase 1 Production-Ready).

Implements the Entry Point Router, state management, and screen rendering.
Added: Full Soft-Deny path, Funnel Logging, and Stale Data protection.
"""

import logging
import os
from typing import Dict, List, Optional, Tuple, Set
from datetime import UTC, datetime, timedelta

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database
from onboarding_delivery import render_delivery, get_delivery_config

logger = logging.getLogger(__name__)

# ============================================================================
# BOT SERVICE HOOKS (dependency injection — avoids circular import with
# telegram_bot_simple). The bot's main() registers real implementations via
# register_bot_services(); tests can inject mocks.
# ============================================================================

_SVC: Dict[str, object] = {}
_CONFIG: Dict[str, object] = {
    'trial_days_text': '7 дней'  # Default fallback
}


def register_bot_services(
    *,
    build_subscription_url=None,
    send_subscription_bundle=None,
    ensure_user_trial=None,
    claim_operator_issued_subscription=None,
    trial_days_text=None,
) -> None:
    """Register bot-side callables and config that onboarding_logic needs.
    Call from telegram_bot_simple.main() once.
    """
    if build_subscription_url is not None:
        _SVC['build_subscription_url'] = build_subscription_url
    if send_subscription_bundle is not None:
        _SVC['send_subscription_bundle'] = send_subscription_bundle
    if ensure_user_trial is not None:
        _SVC['ensure_user_trial'] = ensure_user_trial
    if claim_operator_issued_subscription is not None:
        _SVC['claim_operator_issued_subscription'] = claim_operator_issued_subscription
    
    if trial_days_text is not None:
        _CONFIG['trial_days_text'] = trial_days_text


def _svc(name: str):
    fn = _SVC.get(name)
    if fn is None:
        raise RuntimeError(
            f"onboarding_logic: bot service '{name}' not registered. "
            f"telegram_bot_simple.main() must call register_bot_services() at startup."
        )
    return fn

# ============================================================================
# CONSTANTS & STATE SPACE
# ============================================================================

IN_FLIGHT: Set[str] = {
    'new:entry', 'new:has_app', 'new:pick_client', 'new:softdeny_offer',
    'new:pick_device', 'new:pick_client_for_device', 'new:install',
    'new:client_ready', 'new:trial_or_pay', 'new:delivery_preparing',
    'new:access_delivered', 'new:verify_import', 'new:verify_vpn',
    'add:entry', 'add:device_limit_check', 'add:has_app', 'add:pick_device',
    'add:pick_client_for_device', 'add:install', 'add:client_ready',
    'add:delivery_preparing', 'add:access_delivered',
    'add:verify_import', 'add:verify_vpn',
    'softdeny:manual_delivered', 'softdeny:verify_import_light', 'softdeny:verify_vpn',
}

TERMINAL: Set[Optional[str]] = {None, '', 'new:done', 'add:done', 'softdeny:done'}
PAID_PLANS = {'basic_1m', 'basic_3m', 'basic_6m', 'basic_12m'}
STEP_SCREEN_MAP: Dict[str, str] = {
    'new:entry': 'screen_1',
    'new:has_app': 'screen_has_app',
    'new:pick_client': 'screen_2',
    'new:softdeny_offer': 'screen_2_softdeny',
    'new:pick_device': 'screen_3',
    'new:pick_client_for_device': 'screen_4',
    'new:install': 'screen_5',
    'new:client_ready': 'screen_ready_for_access',
    'new:trial_or_pay': 'screen_6',
    'new:delivery_preparing': 'screen_7_preparing',
    'new:access_delivered': 'screen_8a',
    'new:verify_import': 'screen_8a',
    'new:verify_vpn': 'screen_8b',
    'new:done': 'screen_done',
    'add:entry': 'active_main',
    'add:device_limit_check': 'screen_active_device_limit',
    'add:has_app': 'screen_has_app_add',
    'add:pick_device': 'screen_3',
    'add:pick_client_for_device': 'screen_4',
    'add:install': 'screen_5',
    'add:client_ready': 'screen_ready_for_access',
    'add:delivery_preparing': 'screen_7_preparing',
    'add:access_delivered': 'screen_8a',
    'add:verify_import': 'screen_8a',
    'add:verify_vpn': 'screen_8b',
    'add:done': 'screen_done',
    'softdeny:manual_delivered': 'screen_8a_light',
    'softdeny:verify_import_light': 'screen_8a_light',
    'softdeny:verify_vpn': 'screen_8b',
}


def _ru_day_word(value: int) -> str:
    value = abs(int(value))
    if value % 10 == 1 and value % 100 != 11:
        return "день"
    if value % 10 in {2, 3, 4} and value % 100 not in {12, 13, 14}:
        return "дня"
    return "дней"


TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "7"))
TRIAL_CTA_TEXT = f"{TRIAL_DAYS} {_ru_day_word(TRIAL_DAYS)} бесплатно"

# DEVICE_LIMITS is the canonical plan→limit mapping. Mirrors the dict of the
# same name in telegram_bot_simple.py. Kept here as a static copy to avoid
# the circular import — telegram_bot_simple.py raises SystemExit at import
# time if TELEGRAM_BOT_TOKEN is not set, which is a problem for unit tests
# and any non-bot tooling that needs to reason about the state machine.
# Keep these two in sync on plan changes (see docs/ghost-access/EXECUTION_PLAN.md).
DEVICE_LIMITS = {"trial": 1, "basic_1m": 2, "basic_3m": 3, "basic_6m": 4, "basic_12m": 5}
PLAN_LABELS = {
    "basic_1m": "1 месяц",
    "basic_3m": "3 месяца",
    "basic_6m": "6 месяцев",
    "basic_12m": "12 месяцев",
}
PLAN_ALIASES = {
    "base": "basic_1m",
    "pro": "basic_3m",
    "plus": "basic_6m",
    "year": "basic_12m",
}


def resolve_plan_key(plan_value: str | None) -> str:
    value = (plan_value or "").strip()
    if not value:
        return "trial"
    if value in DEVICE_LIMITS:
        return value
    alias = PLAN_ALIASES.get(value.lower())
    if alias:
        return alias
    value_lower = value.lower()
    for plan_key, label in PLAN_LABELS.items():
        if value_lower == label.lower():
            return plan_key
    return value


def get_device_limit_for_user(user: dict | None) -> int:
    plan_key = resolve_plan_key((user or {}).get("plan"))
    return DEVICE_LIMITS.get(plan_key, 1)


def _screen_name_for_step(step: str | None) -> str:
    if not step:
        return "unknown"
    return STEP_SCREEN_MAP.get(step, step.replace(":", "_"))


def _log_screen_render(user_id: int, step: str | None, *, origin: str) -> None:
    logger.info(
        "onboarding_observe kind=screen_render user_id=%s step=%s screen=%s origin=%s",
        user_id,
        step or "",
        _screen_name_for_step(step),
        origin,
    )

# ============================================================================
# ENTRY POINT ROUTER
# ============================================================================

async def route_start(user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
    user = database.get_user(user_id)
    if not user:
        database.create_user(user_id)
        await update_step(user_id, 'new:entry')
        database.log_activity(user_id, "ob_funnel:fresh_start")
        return render_screen_1()

    step = user.get('onboarding_step')
    if step not in IN_FLIGHT and step not in TERMINAL:
        return render_error_unknown(user_id)

    if is_payment_pending(user_id):
        return render_payment_pending(user_id)

    if step in IN_FLIGHT:
        database.log_activity(user_id, f"ob_funnel:resume_{step}")
        _log_screen_render(user_id, step, origin="route_start_resume")
        return render_resume_prompt(user_id, step)

    if is_subscription_active(user) and user.get('plan') in PAID_PLANS:
        return render_active_main(user)

    if is_subscription_expired_or_cancelled(user):
        return render_expired_main(user)

    reset_onboarding(user_id, namespace='new')
    return render_screen_1()

# ============================================================================
# CALLBACK DISPATCHER
# ============================================================================

async def handle_onboarding_callback(callback: CallbackQuery) -> bool:
    user_id = callback.from_user.id
    data = callback.data
    if not data.startswith(("ob:", "pay:")): return False
        
    user = database.get_user(user_id)
    if not user: return False
    
    current_step = user.get('onboarding_step') or ''
    is_new = current_step.startswith('new') or current_step.startswith('softdeny')

    # Navigation Logic
    if data == "ob:new:start":
        await update_step(user_id, 'new:has_app')
        database.log_activity(user_id, "ob_funnel:step_has_app")
        await safe_edit_callback(callback, *render_screen_has_app())
    
    elif data == "ob:has_app:yes":
        await update_user_field(user_id, 'onboarding_has_app', True)
        await update_step(user_id, 'new:pick_client')
        database.log_activity(user_id, "ob_funnel:step_pick_client")
        await safe_edit_callback(callback, *render_screen_2(user_id))

    elif data == "ob:has_app:no":
        await update_user_field(user_id, 'onboarding_has_app', False)
        await update_step(user_id, 'new:pick_device')
        database.log_activity(user_id, "ob_funnel:step_pick_device")
        await safe_edit_callback(callback, *render_screen_3(user_id))

    elif data == "ob:add:start":
        limit = get_device_limit_for_user(user)
        devices = database.get_user_devices(user_id, include_revoked=False)
        if len(devices) >= limit:
            await update_step(user_id, 'add:device_limit_check')
            await safe_edit_callback(callback, *render_screen_active_device_limit(len(devices), limit))
        else:
            await update_step(user_id, 'add:has_app')
            database.log_activity(user_id, "ob_funnel:add_device_start")
            await safe_edit_callback(callback, *render_screen_has_app_add())

    elif data in {"ob:has_app:yes_add", "ob:has_app:no_add"}:
        await update_user_field(user_id, 'onboarding_has_app', data.endswith("yes_add"))
        await update_step(user_id, 'add:pick_device')
        await safe_edit_callback(callback, *render_screen_3(user_id))

    elif data.startswith("ob:set_client:"):
        client = data.split(":")[2]
        await update_user_field(user_id, 'onboarding_client', client)
        await update_user_field(user_id, 'onboarding_client_installed', True)
        user = database.get_user(user_id) # Refresh
        if not user.get('onboarding_device'):
            await update_step(user_id, 'new:pick_device' if is_new else 'add:pick_device')
            await safe_edit_callback(callback, *render_screen_3(user_id))
        else:
            if not is_new: await finish_to_delivery(user_id, callback)
            else:
                await update_step(user_id, 'new:client_ready')
                await safe_edit_callback(callback, *render_screen_ready_for_access(user_id))

    elif data.startswith("ob:set_device:"):
        device = data.split(":")[2]
        await update_user_field(user_id, 'onboarding_device', device)
        user = database.get_user(user_id) # Refresh
        if not user.get('onboarding_client'):
            await update_step(user_id, 'new:pick_client_for_device' if is_new else 'add:pick_client_for_device')
            await safe_edit_callback(callback, *render_screen_4(user_id, device))
        else:
            if not is_new: await finish_to_delivery(user_id, callback)
            else:
                await update_step(user_id, 'new:client_ready')
                await safe_edit_callback(callback, *render_screen_ready_for_access(user_id))

    elif data == "ob:client_ready":
        await update_user_field(user_id, 'onboarding_client_installed', True)
        if not is_new: await finish_to_delivery(user_id, callback)
        else:
            await update_step(user_id, 'new:client_ready')
            await safe_edit_callback(callback, *render_screen_ready_for_access(user_id))

    # Soft Deny Path (Implementation of Spec v3.3)
    elif data == "ob:new:softdeny_offer":
        await update_step(user_id, 'new:softdeny_offer')
        database.log_activity(user_id, "ob_funnel:softdeny_offer")
        await safe_edit_callback(callback, *render_screen_2_softdeny())
    
    elif data == "ob:softdeny_manual":
        await update_step(user_id, 'softdeny:manual_delivered')
        database.log_activity(user_id, "ob_funnel:softdeny_manual_request")
        await safe_edit_callback(callback, *render_screen_8a_light(user_id))
    
    elif data == "ob:new:pick_device":
        await update_step(user_id, 'new:pick_device')
        await safe_edit_callback(callback, *render_screen_3(user_id))

    elif data.startswith("ob:install:"):
        client = data.split(":")[2]
        cfg = get_delivery_config(user.get('onboarding_device') or 'iphone', client) or {}
        await update_user_field(user_id, 'onboarding_client', client)
        await update_user_field(user_id, 'onboarding_client_installed', False)
        await update_step(user_id, 'new:install' if is_new else 'add:install')
        await safe_edit_callback(
            callback,
            *render_screen_5(user_id, client, cfg.get('store_url', 'https://t.me/ghost_access_news/4')),
        )

    # Trial & Payment
    elif data == "ob:new:trial_or_pay":
        await update_step(user_id, 'new:trial_or_pay')
        database.log_activity(user_id, "ob_funnel:payment_choice")
        await safe_edit_callback(callback, *render_screen_6(user_id, not user.get('trial_used')))

    elif data == "ob:activate_trial":
        await update_step(user_id, 'new:delivery_preparing')
        database.log_activity(user_id, "ob_funnel:trial_activated")
        await safe_edit_callback(callback, *render_screen_7_preparing())
        build_subscription_url = _svc('build_subscription_url')
        send_subscription_bundle = _svc('send_subscription_bundle')
        ensure_user_trial = _svc('ensure_user_trial')

        try:
            trial_user = ensure_user_trial(user_id, callback.from_user.username)
        except Exception as exc:
            await update_step(user_id, 'new:trial_or_pay')
            await safe_edit_callback(callback, f"⚠️ Ошибка активации: {exc}", render_screen_6(user_id, True)[1])
            return True

        if not trial_user:
            await update_step(user_id, 'new:trial_or_pay')
            await safe_edit_callback(callback, *render_screen_6(user_id, False))
            return True

        await send_subscription_bundle(callback.message, trial_user)
        await update_step(user_id, 'new:access_delivered')
        delivery = render_delivery(
            trial_user.get('onboarding_device') or 'iphone',
            trial_user.get('onboarding_client') or 'happ',
            trial_user.get('vpn_config', ''),
            build_subscription_url(user_id),
        )
        await safe_edit_callback(callback, *render_screen_8a(user_id, delivery))
        return True

    elif data == "pay:poll":
        if is_payment_pending(user_id):
            await safe_edit_callback(callback, *render_payment_pending(user_id))
            await callback.answer("⏳ Платёж ещё обрабатывается")
            return True
        refreshed = database.get_user(user_id)
        if refreshed and (refreshed.get('onboarding_step') or '') in IN_FLIGHT:
            await handle_resume_action(callback, refreshed, refreshed.get('onboarding_step') or '')
        else:
            await safe_edit_callback(callback, *(await route_start(user_id)))
        return True

    elif data == "pay:cancel":
        cancelled = database.cancel_pending_payments_for_user(user_id)
        if cancelled:
            database.log_activity(user_id, f"ob_funnel:payment_cancelled_{cancelled}")
        target = get_payment_return_target(user_id)
        clear_payment_return_target(user_id)
        refreshed = database.get_user(user_id) or user
        if target == 'new_trial_or_pay':
            await update_step(user_id, 'new:trial_or_pay')
            await safe_edit_callback(callback, *render_screen_6(user_id, not refreshed.get('trial_used')))
        elif target == 'expired_main':
            await safe_edit_callback(callback, *render_expired_main(refreshed))
        elif target == 'active_main':
            await safe_edit_callback(callback, *render_active_main(refreshed))
        else:
            await safe_edit_callback(callback, *(await route_start(user_id)))
        return True

    elif data in {"ob:verify_import", "ob:verify_import_light"}:
        next_step = 'softdeny:verify_vpn' if 'softdeny' in current_step else ('new:verify_vpn' if is_new else 'add:verify_vpn')
        await update_step(user_id, next_step)
        await safe_edit_callback(callback, *render_screen_8b(user_id))
        return True

    elif data.startswith("ob:resume:"):
        step = data.split(":", 2)[2]
        await handle_resume_action(callback, user, step)
        return True

    elif data == "ob:reset_current":
        ns = 'new' if is_new else 'add'
        reset_onboarding(user_id, namespace=ns)
        if ns == 'new':
            await safe_edit_callback(callback, *render_screen_1())
        else:
            await safe_edit_callback(callback, *render_active_main(user))
        return True

    elif data in {"ob:reset_new_from_expired", "ob:reset_new"}:
        reset_onboarding(user_id, namespace='new')
        await safe_edit_callback(callback, *render_screen_1())
        return True

    elif data == "ob:help_stub":
        await callback.answer("Лучше выбрать поддерживаемое приложение: Happ или Hiddify.", show_alert=True)
        return True

    # Finalization
    elif data == "ob:verify_vpn":
        next_step = 'softdeny:verify_vpn' if 'softdeny' in current_step else ('new:verify_vpn' if is_new else 'add:verify_vpn')
        await update_step(user_id, next_step)
        await safe_edit_callback(callback, *render_screen_8b(user_id))

    elif data == "ob:done":
        await update_step(user_id, 'new:done' if is_new else 'add:done')
        database.log_activity(user_id, "ob_funnel:completed")
        await safe_edit_callback(callback, *render_screen_done())

    elif data == "ob:back":
        await handle_back_button(callback, user)

    else:
        # Unmatched ob:* / pay:* — log and surface, don't swallow silently
        logger.warning("onboarding_callback unhandled: user_id=%s data=%s step=%s", user_id, data, current_step)
        return False

    return True

async def finish_to_delivery(uid, callback):
    await update_step(uid, 'add:delivery_preparing')
    await safe_edit_callback(callback, *render_screen_7_preparing())
    build_subscription_url = _svc('build_subscription_url')
    send_subscription_bundle = _svc('send_subscription_bundle')
    user = database.get_user(uid)
    if not user:
        return
    await send_subscription_bundle(callback.message, user)
    await update_step(uid, 'add:access_delivered')
    delivery = render_delivery(
        user.get('onboarding_device') or 'iphone',
        user.get('onboarding_client') or 'happ',
        user.get('vpn_config', ''),
        build_subscription_url(uid),
    )
    await safe_edit_callback(callback, *render_screen_8a(uid, delivery))

# ============================================================================
# NAVIGATION & RENDERERS
# ============================================================================

async def handle_resume_action(callback: CallbackQuery, user: dict, step: str):
    user_id = user['user_id']
    device = user.get('onboarding_device') or 'iphone'
    client = user.get('onboarding_client') or 'happ'
    delivery = render_delivery(device, client, user.get('vpn_config', ''), '') 
    
    res_map = {
        'new:entry': render_screen_1, 'new:has_app': render_screen_1,
        'new:pick_client': lambda: render_screen_2(user_id),
        'new:softdeny_offer': render_screen_2_softdeny,
        'new:pick_device': lambda: render_screen_3(user_id),
        'new:pick_client_for_device': lambda: render_screen_4(user_id, device),
        'new:install': lambda: render_screen_5(user_id, client, delivery.get('store_url', '')),
        'new:client_ready': lambda: render_screen_ready_for_access(user_id),
        'new:trial_or_pay': lambda: render_screen_6(user_id, not user.get('trial_used')),
        'new:delivery_preparing': render_screen_7_preparing,
        'new:access_delivered': lambda: render_screen_8a(user_id, delivery),
        'new:verify_import': lambda: render_screen_8a(user_id, delivery),
        'new:verify_vpn': lambda: render_screen_8b(user_id),
        'add:entry': lambda: render_active_main(user),
        'add:device_limit_check': lambda: render_screen_active_device_limit(
            len(database.get_user_devices(user_id, include_revoked=False)),
            DEVICE_LIMITS.get(user.get('plan', 'trial'), 1),
        ),
        'add:has_app': render_screen_has_app_add,
        'add:pick_device': lambda: render_screen_3(user_id),
        'add:pick_client_for_device': lambda: render_screen_4(user_id, device),
        'add:install': lambda: render_screen_5(user_id, client, delivery.get('store_url', '')),
        'add:client_ready': lambda: render_screen_ready_for_access(user_id, is_new=False),
        'add:delivery_preparing': render_screen_7_preparing,
        'add:access_delivered': lambda: render_screen_8a(user_id, delivery),
        'add:verify_import': lambda: render_screen_8a(user_id, delivery),
        'add:verify_vpn': lambda: render_screen_8b(user_id),
        'softdeny:manual_delivered': lambda: render_screen_8a_light(user_id),
        'softdeny:verify_import_light': lambda: render_screen_8a_light(user_id),
        'softdeny:verify_vpn': lambda: render_screen_8b(user_id),
    }
    func = res_map.get(step, render_screen_1)
    try: t, k = func()
    except TypeError: t, k = func(user_id)
    _log_screen_render(user_id, step, origin="resume_action")
    await safe_edit_callback(callback, t, k)

async def handle_back_button(callback: CallbackQuery, _):
    user_id = callback.from_user.id
    user = database.get_user(user_id)
    step = user.get('onboarding_step')
    b_map = {
        'new:has_app': ('new:entry', render_screen_1),
        'new:pick_client': ('new:has_app', render_screen_has_app),
        'new:pick_device': ('new:has_app', render_screen_has_app),
        'new:pick_client_for_device': ('new:pick_device', render_screen_3),
        'new:install': ('new:pick_client_for_device', lambda u: render_screen_4(u, user.get('onboarding_device'))),
        'new:client_ready': ('new:pick_client_for_device', lambda u: render_screen_4(u, user.get('onboarding_device'))),
        'new:trial_or_pay': ('new:client_ready', render_screen_ready_for_access),
        'add:has_app': ('add:entry', lambda u: render_active_main(user)),
        'add:pick_device': ('add:has_app', render_screen_has_app_add),
        'add:pick_client_for_device': ('add:pick_device', render_screen_3),
        'add:install': ('add:pick_client_for_device', lambda u: render_screen_4(u, user.get('onboarding_device'))),
        'add:client_ready': ('add:pick_client_for_device', lambda u: render_screen_4(u, user.get('onboarding_device'))),
        # Nav Rule 2: no Back after commits. add:delivery_preparing and any
        # *:access_delivered / *:verify_* are post-commit states and are
        # intentionally absent from this map.
    }
    if step in b_map:
        ns, func = b_map[step]
        await update_step(user_id, ns)
        if step == 'new:pick_client': await update_user_field(user_id, 'onboarding_has_app', None)
        user = database.get_user(user_id)
        try: t, k = func(user_id)
        except TypeError: t, k = func()
        await safe_edit_callback(callback, t, k)

# ============================================================================
# DB WRAPPERS
# ============================================================================

async def update_step(uid, step):
    with database.get_db_connection() as c:
        c.cursor().execute("UPDATE users SET onboarding_step=? WHERE user_id=?", (step, uid))
    _log_screen_render(uid, step, origin="update_step")
async def update_user_field(uid, f, v):
    allowed = {'onboarding_step', 'onboarding_device', 'onboarding_client', 'onboarding_has_app', 'onboarding_client_installed', 'payment_return_target'}
    if f not in allowed: raise ValueError(f"Forbidden: {f}")
    with database.get_db_connection() as c: c.cursor().execute(f"UPDATE users SET {f}=? WHERE user_id=?", (v, uid))
async def safe_edit_callback(cb, t, k):
    try: await cb.message.edit_text(t, reply_markup=k)
    except: await cb.message.answer(t, reply_markup=k)

def is_payment_pending(uid):
    try: return database.get_recent_payments_for_user(uid, limit=1)[0].get('payment_status') == 'pending'
    except: return False
def is_subscription_active(u):
    try:
        expires_at = datetime.fromisoformat(u.get('expires_at').replace('Z', '+00:00'))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        else:
            expires_at = expires_at.astimezone(UTC)
        return expires_at > datetime.now(UTC)
    except: return False
def is_subscription_expired_or_cancelled(u): return u.get('expires_at') and not is_subscription_active(u)
def reset_onboarding(uid, namespace='new'):
    step = 'new:entry' if namespace == 'new' else 'add:entry'
    with database.get_db_connection() as c:
        c.cursor().execute("UPDATE users SET onboarding_step=?, onboarding_device=NULL, onboarding_client=NULL, onboarding_has_app=NULL, onboarding_client_installed=NULL WHERE user_id=?", (step, uid))

def set_payment_return_target(uid, t):
    with database.get_db_connection() as c: c.cursor().execute("UPDATE users SET payment_return_target=? WHERE user_id=?", (t, uid))
def clear_payment_return_target(uid):
    with database.get_db_connection() as c: c.cursor().execute("UPDATE users SET payment_return_target=NULL WHERE user_id=?", (uid,))
def get_payment_return_target(uid):
    u = database.get_user(uid)
    return u.get('payment_return_target') if u else None

def determine_payment_return_target(user: dict | None) -> str:
    if not user:
        return 'new_trial_or_pay'
    step = (user.get('onboarding_step') or '').strip()
    if step.startswith('new:') or step.startswith('softdeny:'):
        return 'new_trial_or_pay'
    if is_subscription_active(user) and user.get('plan') in PAID_PLANS:
        return 'active_main'
    return 'expired_main'

# ============================================================================
# SCREENS
# ============================================================================

def render_screen_1():
    text = "👋 Привет! Я помогу быстро настроить VPN."
    kb = InlineKeyboardBuilder().button(text="Начать", callback_data="ob:new:start")
    kb.button(text="🔍 Найти мою подписку", url="https://dash.x0tta6bl4.ai/sensor-detect")
    return text, kb.adjust(1).as_markup()

def render_screen_has_app(): return "У тебя уже установлено приложение?", InlineKeyboardBuilder().button(text="Да", callback_data="ob:has_app:yes").button(text="Нет", callback_data="ob:has_app:no").button(text="Назад", callback_data="ob:back").adjust(1).as_markup()
def render_screen_has_app_add(): return "На новом устройстве уже есть приложение?", InlineKeyboardBuilder().button(text="Да", callback_data="ob:has_app:yes_add").button(text="Нет", callback_data="ob:has_app:no_add").button(text="Назад", callback_data="ob:back").adjust(1).as_markup()

def render_screen_2(uid):
    kb = InlineKeyboardBuilder()
    for c in ["Happ", "Hiddify", "v2rayN", "v2rayTun"]: kb.button(text=c, callback_data=f"ob:set_client:{c.lower()}")
    kb.button(text="Другое / не знаю", callback_data="ob:new:softdeny_offer").button(text="Назад", callback_data="ob:back")
    return "Выбери приложение:", kb.adjust(1).as_markup()

def render_screen_3(uid):
    kb = InlineKeyboardBuilder()
    for d in ["iPhone", "Android", "Windows", "Mac"]: kb.button(text=d, callback_data=f"ob:set_device:{d.lower()}")
    kb.button(text="Назад", callback_data="ob:back")
    return "Выбери устройство:", kb.adjust(2, 2, 1).as_markup()

def render_screen_4(uid, d):
    c = {"iphone": "Happ", "android": "Hiddify", "windows": "v2rayN", "mac": "Hiddify"}.get(d, "Hiddify")
    return f"Рекомендую {c}. Есть оно?", InlineKeyboardBuilder().button(text=f"Установить {c}", callback_data=f"ob:install:{c.lower()}").button(text="Уже есть", callback_data=f"ob:set_client:{c.lower()}").button(text="Назад", callback_data="ob:back").adjust(1).as_markup()

def render_screen_5(uid, c, url):
    return f"Установи {c} и возвращайся.", InlineKeyboardBuilder().button(text=f"Скачать {c}", url=url).button(text="Установлено", callback_data="ob:client_ready").button(text="Назад", callback_data="ob:back").adjust(1).as_markup()

def render_screen_ready_for_access(uid, is_new=True):
    cb = "ob:new:trial_or_pay" if is_new else "ob:client_ready"
    return "Всё готово для выдачи доступа.", InlineKeyboardBuilder().button(text="Получить доступ", callback_data=cb).button(text="Назад", callback_data="ob:back").as_markup()
def render_screen_6(uid, st):
    kb = InlineKeyboardBuilder()
    if st:
        txt = f"{_CONFIG['trial_days_text']} бесплатно"
        kb.button(text=txt, callback_data="ob:activate_trial")
    kb.button(text="Оплатить", callback_data="buy").button(text="Назад", callback_data="ob:back")
    return "Выбери вариант:", kb.adjust(1).as_markup()

def render_screen_7_preparing(): return "⏳ Подготовка...", None
def render_screen_done(): return "🎉 Готово.", InlineKeyboardBuilder().button(text="Меню", callback_data="account").as_markup()
def render_screen_8a(uid, d):
    kb = InlineKeyboardBuilder()
    text = "✅ Готово! Добавь профиль."
    deep_link = d.get('deep_link')
    if deep_link:
        if deep_link.startswith(('http://', 'https://', 'tg://', 'tme://')):
            kb.button(text="Открыть подключение", url=deep_link)
        else:
            # Custom app schemes (happ://, hiddify://, …) are rejected by Bot API
            # in InlineKeyboardButton.url. Inline them so the user can tap in
            # the message body instead. safe_edit_callback does not set
            # parse_mode, so the link is plain text (still tappable on mobile).
            text = f"{text}\n\nНажми ссылку ниже:\n{deep_link}"
    kb.button(text="Да, профиль добавился", callback_data="ob:verify_import")
    return text, kb.adjust(1).as_markup()

def render_screen_8b(uid): return "VPN работает?", InlineKeyboardBuilder().button(text="Да!", callback_data="ob:done").as_markup()
def render_payment_pending(uid): return "Оплата обрабатывается...", InlineKeyboardBuilder().button(text="Обновить", callback_data="pay:poll").button(text="Отмена", callback_data="pay:cancel").as_markup()
def render_resume_prompt(uid, s): return "Продолжим настройку?", InlineKeyboardBuilder().button(text="Да", callback_data=f"ob:resume:{s}").button(text="Заново", callback_data="ob:reset_current").as_markup()
def render_active_main(u): return f"Активная подписка.", InlineKeyboardBuilder().button(text="Новое устройство", callback_data="ob:add:start").button(text="Продлить", callback_data="buy").as_markup()
def render_expired_main(u): return f"Истекла подписка. Продлить?", InlineKeyboardBuilder().button(text="Продлить", callback_data="buy").button(text="Заново", callback_data="ob:reset_new_from_expired").as_markup()
def render_error_unknown(uid): return "⚠️ Ошибка.", InlineKeyboardBuilder().button(text="Заново", callback_data="ob:reset_new").as_markup()

def render_screen_active_device_limit(n, l):
    text = f"У вас уже {n} устройств из {l} по тарифу."
    kb = InlineKeyboardBuilder().button(text="Мои устройства", callback_data="devices").button(text="Обновить тариф", callback_data="buy").button(text="Назад", callback_data="ob:back")
    return text, kb.adjust(1).as_markup()

def render_screen_2_softdeny():
    text = (
        "Я хорошо поддерживаю только Happ, Hiddify, v2rayTun и v2rayN.\n\n"
        "Если вы уже пользуетесь другим — могу дать обычную ссылку. "
        "Но проще и надёжнее поставить один из моих четырёх."
    )
    kb = (
        InlineKeyboardBuilder()
        .button(text="Выбрать приложение по устройству", callback_data="ob:new:pick_device")
        .button(text="Всё-таки дайте ссылку как есть", callback_data="ob:softdeny_manual")
        .button(text="Назад", callback_data="ob:back")
    )
    return text, kb.adjust(1).as_markup()

def render_screen_8a_light(uid): return "Добавил профиль?", InlineKeyboardBuilder().button(text="Да", callback_data="ob:verify_import_light").button(text="Нет", callback_data="ob:help_stub").as_markup()

async def handle_offline_bind(uid, t):
    claim_operator_issued_subscription = _svc('claim_operator_issued_subscription')

    record = database.get_offline_subscription_by_token(t)
    if not record: return "❌ Код недействителен.", render_screen_1()[1]
    try:
        claim_operator_issued_subscription(uid, None, str(record["claim_code"]))
        await update_step(uid, 'new:done')
        database.log_activity(uid, "ob_funnel:bind_success")
        return "✅ Подписка привязана!", render_screen_done()[1]
    except Exception as e:
        return f"⚠️ Ошибка: {e}", render_screen_1()[1]
