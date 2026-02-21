"""
Comprehensive unit tests for src/sales/telegram_bot.py
"""

import os
import secrets
import time
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


# ---------------------------------------------------------------------------
# We need to mock external deps BEFORE importing the module
# ---------------------------------------------------------------------------

# Create mock telegram classes
class FakeInlineKeyboardButton:
    def __init__(self, text, callback_data=None, url=None):
        self.text = text
        self.callback_data = callback_data
        self.url = url


class FakeInlineKeyboardMarkup:
    def __init__(self, keyboard):
        self.inline_keyboard = keyboard


class FakeUpdate:
    pass


class FakeContextTypes:
    DEFAULT_TYPE = None


class FakeApplication:
    pass


class FakeApplicationBuilder:
    def token(self, t):
        self._token = t
        return self

    def build(self):
        app = MagicMock()
        app.add_handler = MagicMock()
        app.run_polling = MagicMock()
        return app


class FakeCommandHandler:
    def __init__(self, command, callback):
        self.command = command
        self.callback = callback


class FakeCallbackQueryHandler:
    def __init__(self, callback, pattern=None):
        self.callback = callback
        self.pattern = pattern


# Patch telegram and external deps at module level before import
_telegram_mocks = {
    "telegram": MagicMock(
        InlineKeyboardButton=FakeInlineKeyboardButton,
        InlineKeyboardMarkup=FakeInlineKeyboardMarkup,
        Update=FakeUpdate,
    ),
    "telegram.ext": MagicMock(
        Application=MagicMock(builder=MagicMock(return_value=FakeApplicationBuilder())),
        CallbackQueryHandler=FakeCallbackQueryHandler,
        CommandHandler=FakeCommandHandler,
        ContextTypes=FakeContextTypes,
    ),
}

# Patch payment_verification and xray_manager
_payment_mock = MagicMock()
_xray_mock = MagicMock()


@pytest.fixture(autouse=True)
def _patch_externals(monkeypatch):
    """Patch telegram imports at the module level after import."""
    # This runs per-test but the module is already imported
    pass


# Now import with mocks in place
with patch.multiple(
    "src.sales.telegram_bot",
    InlineKeyboardButton=FakeInlineKeyboardButton,
    InlineKeyboardMarkup=FakeInlineKeyboardMarkup,
):
    pass

# We import the module - it will try to import telegram, payment_verification, xray_manager
# We need to ensure those are importable
try:
    from src.sales.telegram_bot import (
        Config,
        MANIFESTO,
        PRICE_TEXT,
        TokenGenerator,
        back_to_start,
        buy_tier,
        config,
        confirm_payment,
        faq_handler,
        how_it_works,
        main,
        show_prices,
        start_command,
        try_free,
        TELEGRAM_AVAILABLE,
    )
except ImportError as e:
    pytest.skip(f"Cannot import telegram_bot: {e}", allow_module_level=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_update_with_message():
    """Create a mock Update with message (for /start)."""
    update = MagicMock()
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    return update


def make_update_with_callback(callback_data="test"):
    """Create a mock Update with callback_query."""
    update = MagicMock()
    update.callback_query = AsyncMock()
    update.callback_query.data = callback_data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.from_user = MagicMock()
    update.callback_query.from_user.id = 123456789
    return update


def make_context():
    """Create a mock context."""
    return MagicMock()


# ===========================================================================
# TokenGenerator tests
# ===========================================================================


class TestTokenGenerator:
    def test_generate_basic_token(self):
        token = TokenGenerator.generate("basic")
        assert token.startswith("X0T-BAS-")
        parts = token.split("-")
        assert len(parts) == 4
        assert parts[1] == "BAS"

    def test_generate_pro_token(self):
        token = TokenGenerator.generate("pro")
        assert "PRO" in token
        assert token.startswith("X0T-PRO-")

    def test_generate_enterprise_token(self):
        token = TokenGenerator.generate("enterprise")
        assert "ENT" in token
        assert token.startswith("X0T-ENT-")

    def test_generate_unknown_tier_defaults_to_basic(self):
        token = TokenGenerator.generate("unknown_tier")
        assert "BAS" in token

    def test_generate_default_tier_is_basic(self):
        token = TokenGenerator.generate()
        assert "BAS" in token

    def test_generate_uniqueness(self):
        tokens = {TokenGenerator.generate("basic") for _ in range(50)}
        assert len(tokens) == 50, "Tokens should be unique"

    def test_generate_contains_timestamp(self):
        before = int(time.time())
        token = TokenGenerator.generate("basic")
        after = int(time.time())
        # Last part is hex timestamp
        ts_hex = token.split("-")[-1]
        ts_val = int(ts_hex, 16)
        assert before <= ts_val <= after

    def test_generate_order_id(self):
        order_id = TokenGenerator.generate_order_id()
        assert order_id.startswith("ORD-")
        # ORD- + 12 hex chars
        assert len(order_id) == 4 + 12

    def test_generate_order_id_uniqueness(self):
        ids = {TokenGenerator.generate_order_id() for _ in range(50)}
        assert len(ids) == 50


# ===========================================================================
# Config tests
# ===========================================================================


class TestConfig:
    def test_config_defaults(self):
        c = Config()
        assert c.PRICE_SOLO == 100
        assert c.PRICE_FAMILY == 50
        assert c.PRICE_APARTMENT == 30
        assert c.PRICE_NEIGHBORHOOD == 20

    def test_config_env_override(self):
        # Config defaults are evaluated at class-definition time, not instantiation time,
        # because they use os.getenv() as dataclass field defaults.
        # Pass the value directly as a constructor argument to test the field.
        c = Config(BOT_TOKEN="test_token_123")
        assert c.BOT_TOKEN == "test_token_123"

    def test_config_wallet_from_env(self):
        # Config defaults are evaluated at class-definition time, not instantiation time.
        # Pass values directly as constructor arguments to test the fields.
        c = Config(USDT_TRC20_WALLET="TTestWallet123", TON_WALLET="UQTestTonWallet")
        assert c.USDT_TRC20_WALLET == "TTestWallet123"
        assert c.TON_WALLET == "UQTestTonWallet"


# ===========================================================================
# Constants tests
# ===========================================================================


class TestConstants:
    def test_manifesto_not_empty(self):
        assert len(MANIFESTO) > 100

    def test_price_text_not_empty(self):
        assert len(PRICE_TEXT) > 100

    def test_manifesto_contains_key_phrases(self):
        assert "YouTube" in MANIFESTO
        assert "VPN" in MANIFESTO

    def test_price_text_contains_tiers(self):
        assert "SOLO" in PRICE_TEXT
        assert "FAMILY" in PRICE_TEXT
        assert "APARTMENT" in PRICE_TEXT
        assert "NEIGHBORHOOD" in PRICE_TEXT


# ===========================================================================
# Handler tests - start_command
# ===========================================================================


class TestStartCommand:
    @pytest.mark.asyncio
    async def test_start_command_sends_manifesto(self):
        update = make_update_with_message()
        ctx = make_context()

        await start_command(update, ctx)

        update.message.reply_text.assert_awaited_once()
        args, kwargs = update.message.reply_text.call_args
        assert args[0] == MANIFESTO
        assert kwargs["parse_mode"] == "Markdown"
        assert kwargs["reply_markup"] is not None

    @pytest.mark.asyncio
    async def test_start_command_keyboard_buttons(self):
        update = make_update_with_message()
        ctx = make_context()

        await start_command(update, ctx)

        _, kwargs = update.message.reply_text.call_args
        markup = kwargs["reply_markup"]
        # FakeInlineKeyboardMarkup stores in inline_keyboard
        buttons = markup.inline_keyboard
        assert len(buttons) == 3
        assert buttons[0][0].callback_data == "try_free"
        assert buttons[1][0].callback_data == "show_prices"
        assert buttons[2][0].callback_data == "how_it_works"


# ===========================================================================
# Handler tests - show_prices
# ===========================================================================


class TestShowPrices:
    @pytest.mark.asyncio
    async def test_show_prices_answers_callback(self):
        update = make_update_with_callback("show_prices")
        ctx = make_context()

        await show_prices(update, ctx)

        update.callback_query.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_show_prices_displays_price_text(self):
        update = make_update_with_callback("show_prices")
        ctx = make_context()

        await show_prices(update, ctx)

        update.callback_query.edit_message_text.assert_awaited_once()
        args, kwargs = update.callback_query.edit_message_text.call_args
        assert args[0] == PRICE_TEXT
        assert kwargs["parse_mode"] == "Markdown"

    @pytest.mark.asyncio
    async def test_show_prices_keyboard(self):
        update = make_update_with_callback("show_prices")
        ctx = make_context()

        await show_prices(update, ctx)

        _, kwargs = update.callback_query.edit_message_text.call_args
        buttons = kwargs["reply_markup"].inline_keyboard
        callback_datas = [b[0].callback_data for b in buttons]
        assert "buy_solo" in callback_datas
        assert "buy_family" in callback_datas
        assert "buy_apartment" in callback_datas
        assert "back_to_start" in callback_datas


# ===========================================================================
# Handler tests - try_free
# ===========================================================================


class TestTryFree:
    @pytest.mark.asyncio
    async def test_try_free_answers_callback(self):
        update = make_update_with_callback("try_free")
        ctx = make_context()

        await try_free(update, ctx)

        update.callback_query.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_try_free_generates_trial_token(self):
        update = make_update_with_callback("try_free")
        ctx = make_context()

        await try_free(update, ctx)

        args, kwargs = update.callback_query.edit_message_text.call_args
        text = args[0]
        assert "TRIAL-" in text
        assert "БЕСПЛАТНО" in text

    @pytest.mark.asyncio
    async def test_try_free_keyboard_has_download(self):
        update = make_update_with_callback("try_free")
        ctx = make_context()

        await try_free(update, ctx)

        _, kwargs = update.callback_query.edit_message_text.call_args
        buttons = kwargs["reply_markup"].inline_keyboard
        # First button should be download with url
        assert buttons[0][0].url is not None
        # Has prices and back buttons
        callback_datas = [b[0].callback_data for b in buttons if b[0].callback_data]
        assert "show_prices" in callback_datas
        assert "back_to_start" in callback_datas


# ===========================================================================
# Handler tests - how_it_works
# ===========================================================================


class TestHowItWorks:
    @pytest.mark.asyncio
    async def test_how_it_works_answers_callback(self):
        update = make_update_with_callback("how_it_works")
        ctx = make_context()

        await how_it_works(update, ctx)

        update.callback_query.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_how_it_works_displays_explanation(self):
        update = make_update_with_callback("how_it_works")
        ctx = make_context()

        await how_it_works(update, ctx)

        args, kwargs = update.callback_query.edit_message_text.call_args
        text = args[0]
        assert "КАК ЭТО РАБОТАЕТ" in text
        assert "VPN" in text

    @pytest.mark.asyncio
    async def test_how_it_works_keyboard(self):
        update = make_update_with_callback("how_it_works")
        ctx = make_context()

        await how_it_works(update, ctx)

        _, kwargs = update.callback_query.edit_message_text.call_args
        buttons = kwargs["reply_markup"].inline_keyboard
        callback_datas = [b[0].callback_data for b in buttons]
        assert "try_free" in callback_datas
        assert "back_to_start" in callback_datas


# ===========================================================================
# Handler tests - buy_tier
# ===========================================================================


class TestBuyTier:
    @pytest.mark.asyncio
    async def test_buy_solo(self):
        update = make_update_with_callback("buy_solo")
        ctx = make_context()

        await buy_tier(update, ctx)

        update.callback_query.answer.assert_awaited_once()
        args, kwargs = update.callback_query.edit_message_text.call_args
        text = args[0]
        assert "SOLO" in text
        assert "100" in text

    @pytest.mark.asyncio
    async def test_buy_family(self):
        update = make_update_with_callback("buy_family")
        ctx = make_context()

        await buy_tier(update, ctx)

        args, _ = update.callback_query.edit_message_text.call_args
        text = args[0]
        assert "FAMILY" in text
        assert "50" in text

    @pytest.mark.asyncio
    async def test_buy_apartment(self):
        update = make_update_with_callback("buy_apartment")
        ctx = make_context()

        await buy_tier(update, ctx)

        args, _ = update.callback_query.edit_message_text.call_args
        text = args[0]
        assert "APARTMENT" in text
        assert "30" in text

    @pytest.mark.asyncio
    async def test_buy_neighborhood(self):
        update = make_update_with_callback("buy_neighborhood")
        ctx = make_context()

        await buy_tier(update, ctx)

        args, _ = update.callback_query.edit_message_text.call_args
        text = args[0]
        assert "NEIGHBORHOOD" in text
        assert "20" in text

    @pytest.mark.asyncio
    async def test_buy_unknown_tier_defaults_to_100(self):
        update = make_update_with_callback("buy_unknown")
        ctx = make_context()

        await buy_tier(update, ctx)

        args, _ = update.callback_query.edit_message_text.call_args
        text = args[0]
        assert "100" in text

    @pytest.mark.asyncio
    async def test_buy_tier_has_order_id(self):
        update = make_update_with_callback("buy_solo")
        ctx = make_context()

        await buy_tier(update, ctx)

        args, _ = update.callback_query.edit_message_text.call_args
        text = args[0]
        assert "ORD-" in text

    @pytest.mark.asyncio
    async def test_buy_tier_keyboard_has_paid_button(self):
        update = make_update_with_callback("buy_solo")
        ctx = make_context()

        await buy_tier(update, ctx)

        _, kwargs = update.callback_query.edit_message_text.call_args
        buttons = kwargs["reply_markup"].inline_keyboard
        paid_button = buttons[0][0]
        assert paid_button.callback_data.startswith("paid_solo_")

    @pytest.mark.asyncio
    async def test_buy_tier_keyboard_has_try_free_and_cancel(self):
        update = make_update_with_callback("buy_solo")
        ctx = make_context()

        await buy_tier(update, ctx)

        _, kwargs = update.callback_query.edit_message_text.call_args
        buttons = kwargs["reply_markup"].inline_keyboard
        callback_datas = [b[0].callback_data for b in buttons if b[0].callback_data]
        assert "try_free" in callback_datas
        assert "show_prices" in callback_datas

    @pytest.mark.asyncio
    async def test_buy_tier_payment_text_contains_wallets(self):
        update = make_update_with_callback("buy_solo")
        ctx = make_context()

        await buy_tier(update, ctx)

        args, _ = update.callback_query.edit_message_text.call_args
        text = args[0]
        # Should contain wallet addresses (from config)
        assert "USDT" in text
        assert "TON" in text


# ===========================================================================
# Handler tests - confirm_payment
# ===========================================================================


class TestConfirmPayment:
    @pytest.mark.asyncio
    async def test_payment_not_verified_shows_not_found(self):
        update = make_update_with_callback("paid_solo_ORD-ABC123DEF456")
        ctx = make_context()

        mock_tron = MagicMock()
        mock_tron.verify_payment.return_value = {"verified": False}
        mock_ton = MagicMock()
        mock_ton.verify_payment.return_value = {"verified": False}

        with patch("src.sales.telegram_bot.TronScanVerifier", return_value=mock_tron), \
             patch("src.sales.telegram_bot.TONVerifier", return_value=mock_ton):
            await confirm_payment(update, ctx)

        # Should have been called twice: first "checking", then "not found"
        assert update.callback_query.edit_message_text.await_count == 2
        # Last call should be the "not found" message
        last_call_args = update.callback_query.edit_message_text.call_args_list[-1]
        text = last_call_args[0][0]
        assert "НЕ НАЙДЕН" in text

    @pytest.mark.asyncio
    async def test_payment_not_verified_has_retry_button(self):
        update = make_update_with_callback("paid_solo_ORD-ABC123DEF456")
        ctx = make_context()

        mock_tron = MagicMock()
        mock_tron.verify_payment.return_value = {"verified": False}
        mock_ton = MagicMock()
        mock_ton.verify_payment.return_value = {"verified": False}

        with patch("src.sales.telegram_bot.TronScanVerifier", return_value=mock_tron), \
             patch("src.sales.telegram_bot.TONVerifier", return_value=mock_ton):
            await confirm_payment(update, ctx)

        last_call_kwargs = update.callback_query.edit_message_text.call_args_list[-1][1]
        buttons = last_call_kwargs["reply_markup"].inline_keyboard
        retry_btn = buttons[0][0]
        assert "paid_solo_ORD-ABC123DEF456" in retry_btn.callback_data

    @pytest.mark.asyncio
    async def test_payment_verified_via_usdt(self):
        update = make_update_with_callback("paid_solo_ORD-ABC123DEF456")
        ctx = make_context()

        mock_tron = MagicMock()
        mock_tron.verify_payment.return_value = {
            "verified": True,
            "transaction_hash": "txhash123",
        }

        mock_xray = MagicMock()
        mock_xray.add_user = AsyncMock()
        mock_xray.generate_vless_link = MagicMock(return_value="vless://test-link")

        with patch("src.sales.telegram_bot.TronScanVerifier", return_value=mock_tron), \
             patch("src.sales.telegram_bot.XrayManager", mock_xray):
            # Patch database import to avoid real DB
            with patch("src.sales.telegram_bot.logger"):
                # Mock the database import inside confirm_payment
                mock_db_module = MagicMock()
                mock_session = MagicMock()
                mock_db_module.SessionLocal.return_value = mock_session
                with patch.dict("sys.modules", {"src.database": mock_db_module}):
                    await confirm_payment(update, ctx)

        # Last edit should be the success message
        last_call = update.callback_query.edit_message_text.call_args_list[-1]
        text = last_call[0][0]
        assert "ПОДТВЕРЖДЁН" in text
        assert "vless://test-link" in text
        assert "USDT" in text

    @pytest.mark.asyncio
    async def test_payment_verified_via_ton(self):
        update = make_update_with_callback("paid_family_ORD-XYZ789")
        ctx = make_context()

        mock_tron = MagicMock()
        mock_tron.verify_payment.return_value = {"verified": False}
        mock_ton = MagicMock()
        mock_ton.verify_payment.return_value = {
            "verified": True,
            "transaction_hash": "ton_hash_456",
        }

        mock_xray = MagicMock()
        mock_xray.add_user = AsyncMock()
        mock_xray.generate_vless_link = MagicMock(return_value="vless://ton-link")

        mock_db_module = MagicMock()
        mock_session = MagicMock()
        mock_db_module.SessionLocal.return_value = mock_session

        with patch("src.sales.telegram_bot.TronScanVerifier", return_value=mock_tron), \
             patch("src.sales.telegram_bot.TONVerifier", return_value=mock_ton), \
             patch("src.sales.telegram_bot.XrayManager", mock_xray), \
             patch.dict("sys.modules", {"src.database": mock_db_module}):
            await confirm_payment(update, ctx)

        last_call = update.callback_query.edit_message_text.call_args_list[-1]
        text = last_call[0][0]
        assert "ПОДТВЕРЖДЁН" in text
        assert "TON" in text

    @pytest.mark.asyncio
    async def test_payment_verified_xray_failure_shows_error_link(self):
        update = make_update_with_callback("paid_solo_ORD-FAIL123")
        ctx = make_context()

        mock_tron = MagicMock()
        mock_tron.verify_payment.return_value = {
            "verified": True,
            "transaction_hash": "tx_ok",
        }

        mock_xray = MagicMock()
        mock_xray.add_user = AsyncMock(side_effect=Exception("Xray down"))
        mock_xray.generate_vless_link = MagicMock(return_value="vless://ok")

        mock_db_module = MagicMock()
        mock_session = MagicMock()
        mock_db_module.SessionLocal.return_value = mock_session

        with patch("src.sales.telegram_bot.TronScanVerifier", return_value=mock_tron), \
             patch("src.sales.telegram_bot.XrayManager", mock_xray), \
             patch.dict("sys.modules", {"src.database": mock_db_module}):
            await confirm_payment(update, ctx)

        last_call = update.callback_query.edit_message_text.call_args_list[-1]
        text = last_call[0][0]
        assert "ERROR_GENERATING_LINK_CONTACT_SUPPORT" in text

    @pytest.mark.asyncio
    async def test_payment_verified_db_failure_doesnt_crash(self):
        """Database failure should not crash the handler."""
        update = make_update_with_callback("paid_solo_ORD-DBFAIL")
        ctx = make_context()

        mock_tron = MagicMock()
        mock_tron.verify_payment.return_value = {
            "verified": True,
            "transaction_hash": "tx_ok",
        }

        mock_xray = MagicMock()
        mock_xray.add_user = AsyncMock()
        mock_xray.generate_vless_link = MagicMock(return_value="vless://ok")

        # Make database import fail
        with patch("src.sales.telegram_bot.TronScanVerifier", return_value=mock_tron), \
             patch("src.sales.telegram_bot.XrayManager", mock_xray), \
             patch.dict("sys.modules", {"src.database": None}):
            # Should not raise even if database import fails
            await confirm_payment(update, ctx)

        # Success message should still be sent
        last_call = update.callback_query.edit_message_text.call_args_list[-1]
        text = last_call[0][0]
        assert "ПОДТВЕРЖДЁН" in text

    @pytest.mark.asyncio
    async def test_payment_checking_message_shown_first(self):
        update = make_update_with_callback("paid_solo_ORD-CHECK1")
        ctx = make_context()

        mock_tron = MagicMock()
        mock_tron.verify_payment.return_value = {"verified": False}
        mock_ton = MagicMock()
        mock_ton.verify_payment.return_value = {"verified": False}

        with patch("src.sales.telegram_bot.TronScanVerifier", return_value=mock_tron), \
             patch("src.sales.telegram_bot.TONVerifier", return_value=mock_ton):
            await confirm_payment(update, ctx)

        # First call should be the "checking" message
        first_call = update.callback_query.edit_message_text.call_args_list[0]
        text = first_call[0][0]
        assert "ПРОВЕРКА ПЛАТЕЖА" in text

    @pytest.mark.asyncio
    async def test_confirm_payment_parses_tier_and_order(self):
        """Verify correct tier/order parsing from callback_data."""
        update = make_update_with_callback("paid_apartment_ORD-PARSE123")
        ctx = make_context()

        mock_tron = MagicMock()
        mock_tron.verify_payment.return_value = {"verified": False}
        mock_ton = MagicMock()
        mock_ton.verify_payment.return_value = {"verified": False}

        with patch("src.sales.telegram_bot.TronScanVerifier", return_value=mock_tron), \
             patch("src.sales.telegram_bot.TONVerifier", return_value=mock_ton):
            await confirm_payment(update, ctx)

        # Check price was calculated correctly for apartment (30 RUB)
        first_text = update.callback_query.edit_message_text.call_args_list[0][0][0]
        assert "30" in first_text

    @pytest.mark.asyncio
    async def test_confirm_payment_usdt_amount_calculation(self):
        """Verify correct USDT conversion (price_rub / 95)."""
        update = make_update_with_callback("paid_solo_ORD-CALC1")
        ctx = make_context()

        mock_tron = MagicMock()
        mock_tron.verify_payment.return_value = {"verified": False}
        mock_ton = MagicMock()
        mock_ton.verify_payment.return_value = {"verified": False}

        with patch("src.sales.telegram_bot.TronScanVerifier", return_value=mock_tron) as tron_cls, \
             patch("src.sales.telegram_bot.TONVerifier", return_value=mock_ton):
            await confirm_payment(update, ctx)

        # solo = 100 RUB, 100/95 = 1.05
        call_args = mock_tron.verify_payment.call_args
        amount_usdt = call_args[0][1]
        assert abs(amount_usdt - round(100 / 95.0, 2)) < 0.01

    @pytest.mark.asyncio
    async def test_confirm_payment_ton_amount_calculation(self):
        """Verify correct TON conversion (price_rub / 2)."""
        update = make_update_with_callback("paid_solo_ORD-CALC2")
        ctx = make_context()

        mock_tron = MagicMock()
        mock_tron.verify_payment.return_value = {"verified": False}
        mock_ton = MagicMock()
        mock_ton.verify_payment.return_value = {"verified": False}

        with patch("src.sales.telegram_bot.TronScanVerifier", return_value=mock_tron), \
             patch("src.sales.telegram_bot.TONVerifier", return_value=mock_ton):
            await confirm_payment(update, ctx)

        # solo = 100 RUB, 100/2 = 50.0
        call_args = mock_ton.verify_payment.call_args
        amount_ton = call_args[0][1]
        assert amount_ton == 50.0

    @pytest.mark.asyncio
    async def test_payment_verified_stores_in_db(self):
        """Verify DB storage is attempted on successful payment."""
        update = make_update_with_callback("paid_solo_ORD-DB123")
        ctx = make_context()

        mock_tron = MagicMock()
        mock_tron.verify_payment.return_value = {
            "verified": True,
            "transaction_hash": "txdb123",
        }

        mock_xray = MagicMock()
        mock_xray.add_user = AsyncMock()
        mock_xray.generate_vless_link = MagicMock(return_value="vless://db-link")

        mock_db_module = MagicMock()
        mock_session = MagicMock()
        mock_db_module.SessionLocal.return_value = mock_session

        with patch("src.sales.telegram_bot.TronScanVerifier", return_value=mock_tron), \
             patch("src.sales.telegram_bot.XrayManager", mock_xray), \
             patch.dict("sys.modules", {"src.database": mock_db_module}):
            await confirm_payment(update, ctx)

        # DB session should have had add and commit called
        assert mock_session.add.call_count == 2  # Payment + License
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_payment_verified_db_error_rolls_back(self):
        """Verify DB rollback on commit failure."""
        update = make_update_with_callback("paid_solo_ORD-ROLL1")
        ctx = make_context()

        mock_tron = MagicMock()
        mock_tron.verify_payment.return_value = {
            "verified": True,
            "transaction_hash": "txroll1",
        }

        mock_xray = MagicMock()
        mock_xray.add_user = AsyncMock()
        mock_xray.generate_vless_link = MagicMock(return_value="vless://roll-link")

        mock_db_module = MagicMock()
        mock_session = MagicMock()
        mock_session.commit.side_effect = Exception("DB commit error")
        mock_db_module.SessionLocal.return_value = mock_session

        with patch("src.sales.telegram_bot.TronScanVerifier", return_value=mock_tron), \
             patch("src.sales.telegram_bot.XrayManager", mock_xray), \
             patch.dict("sys.modules", {"src.database": mock_db_module}):
            await confirm_payment(update, ctx)

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


# ===========================================================================
# Handler tests - faq_handler
# ===========================================================================


class TestFaqHandler:
    @pytest.mark.asyncio
    async def test_faq_answers_callback(self):
        update = make_update_with_callback("faq")
        ctx = make_context()

        await faq_handler(update, ctx)

        update.callback_query.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_faq_displays_questions(self):
        update = make_update_with_callback("faq")
        ctx = make_context()

        await faq_handler(update, ctx)

        args, kwargs = update.callback_query.edit_message_text.call_args
        text = args[0]
        assert "FAQ" in text
        assert "YouTube" in text

    @pytest.mark.asyncio
    async def test_faq_keyboard_has_back(self):
        update = make_update_with_callback("faq")
        ctx = make_context()

        await faq_handler(update, ctx)

        _, kwargs = update.callback_query.edit_message_text.call_args
        buttons = kwargs["reply_markup"].inline_keyboard
        assert buttons[0][0].callback_data == "back_to_start"


# ===========================================================================
# Handler tests - back_to_start
# ===========================================================================


class TestBackToStart:
    @pytest.mark.asyncio
    async def test_back_to_start_answers_callback(self):
        update = make_update_with_callback("back_to_start")
        ctx = make_context()

        await back_to_start(update, ctx)

        update.callback_query.answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_back_to_start_shows_manifesto(self):
        update = make_update_with_callback("back_to_start")
        ctx = make_context()

        await back_to_start(update, ctx)

        args, kwargs = update.callback_query.edit_message_text.call_args
        assert args[0] == MANIFESTO
        assert kwargs["parse_mode"] == "Markdown"

    @pytest.mark.asyncio
    async def test_back_to_start_same_keyboard_as_start(self):
        update = make_update_with_callback("back_to_start")
        ctx = make_context()

        await back_to_start(update, ctx)

        _, kwargs = update.callback_query.edit_message_text.call_args
        buttons = kwargs["reply_markup"].inline_keyboard
        callback_datas = [b[0].callback_data for b in buttons]
        assert "try_free" in callback_datas
        assert "show_prices" in callback_datas
        assert "how_it_works" in callback_datas


# ===========================================================================
# main() tests
# ===========================================================================


class TestMain:
    def test_main_no_telegram(self):
        with patch("src.sales.telegram_bot.TELEGRAM_AVAILABLE", False), \
             patch("builtins.print") as mock_print:
            main()
            mock_print.assert_any_call("❌ python-telegram-bot not installed")

    def test_main_no_bot_token(self):
        with patch("src.sales.telegram_bot.TELEGRAM_AVAILABLE", True), \
             patch("src.sales.telegram_bot.config") as mock_config, \
             patch("builtins.print") as mock_print:
            mock_config.BOT_TOKEN = None
            main()
            # Should print error about missing token
            calls = [str(c) for c in mock_print.call_args_list]
            assert any("TELEGRAM_BOT_TOKEN" in c for c in calls)

    def test_main_with_valid_config(self):
        mock_app = MagicMock()
        mock_builder = MagicMock()
        mock_builder.token.return_value = mock_builder
        mock_builder.build.return_value = mock_app

        mock_application = MagicMock()
        mock_application.builder.return_value = mock_builder

        with patch("src.sales.telegram_bot.TELEGRAM_AVAILABLE", True), \
             patch("src.sales.telegram_bot.config") as mock_config, \
             patch("src.sales.telegram_bot.Application", mock_application), \
             patch("src.sales.telegram_bot.CommandHandler", FakeCommandHandler), \
             patch("src.sales.telegram_bot.CallbackQueryHandler", FakeCallbackQueryHandler), \
             patch("builtins.print"):
            mock_config.BOT_TOKEN = "test_token_123"
            main()

        mock_builder.token.assert_called_once_with("test_token_123")
        mock_builder.build.assert_called_once()
        assert mock_app.add_handler.call_count == 8  # 1 command + 7 callback handlers
        mock_app.run_polling.assert_called_once()
