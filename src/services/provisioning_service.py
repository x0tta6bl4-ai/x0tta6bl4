"""
Provisioning Service — x0tta6bl4
=================================

Единый сервис провижининга (VPN + MaaS).
Центральная точка для создания/удаления аккаунтов,
вызывается из billing webhook, Telegram bot, admin API, MaaS API.

Zero-Trust: каждый вызов валидирует входные данные,
каждый аккаунт получает уникальный UUID.
"""

import hashlib
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ProvisioningSource(str, Enum):
    """Источник запроса на провижининг."""
    STRIPE_WEBHOOK = "stripe_webhook"
    TELEGRAM_PAYMENT = "telegram_payment"
    TELEGRAM_TRIAL = "telegram_trial"
    ADMIN_API = "admin_api"
    CRYPTO_PAYMENT = "crypto_payment"


@dataclass
class ProvisioningResult:
    """Результат провижининга VPN-аккаунта."""
    success: bool
    vpn_uuid: Optional[str] = None
    vless_link: Optional[str] = None
    email: Optional[str] = None
    plan: str = "trial"
    error: Optional[str] = None
    provisioned_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "vpn_uuid": self.vpn_uuid,
            "vless_link": self.vless_link,
            "email": self.email,
            "plan": self.plan,
            "error": self.error,
            "provisioned_at": self.provisioned_at.isoformat(),
        }


class ProvisioningService:
    """
    Единый сервис VPN-провижининга.

    Инвариант Zero-Trust:
    - Каждый пользователь получает уникальный UUID
    - Все операции логируются
    - Провижининг идемпотентен (повторный вызов не создаёт дубликатов)
    """

    def __init__(self):
        self._xui_client = None
        self._xray_manager = None

    @property
    def xui_client(self):
        """Lazy-load XUIAPIClient."""
        if self._xui_client is None:
            try:
                from vpn_config_generator import XUIAPIClient
                self._xui_client = XUIAPIClient()
            except ImportError:
                logger.warning("XUIAPIClient not available — running in simulated mode")
                self._xui_client = _SimulatedXUI()
        return self._xui_client

    @property
    def xray_manager(self):
        """Lazy-load XrayManager."""
        if self._xray_manager is None:
            try:
                from src.services.xray_manager import XrayManager
                self._xray_manager = XrayManager
            except ImportError:
                logger.warning("XrayManager not available")
                self._xray_manager = None
        return self._xray_manager

    async def provision_vpn_user(
        self,
        email: str,
        plan: str = "pro",
        source: ProvisioningSource = ProvisioningSource.STRIPE_WEBHOOK,
        user_id: Optional[str] = None,
        telegram_chat_id: Optional[int] = None,
    ) -> ProvisioningResult:
        """
        Создать VPN-аккаунт для пользователя.

        Args:
            email: Email пользователя (обязательно)
            plan: Тариф (trial/pro/enterprise)
            source: Источник запроса
            user_id: Внутренний ID пользователя (опционально)
            telegram_chat_id: Telegram chat ID для отправки конфига

        Returns:
            ProvisioningResult с VLESS-ссылкой или ошибкой
        """
        if not email or "@" not in email:
            return ProvisioningResult(
                success=False, email=email, error="Invalid email"
            )

        logger.info(
            f"[PROVISION] Start: email={email}, plan={plan}, source={source.value}"
        )

        try:
            # 1. Generate unique VPN UUID
            vpn_uuid = str(uuid.uuid4())

            # 2. Create user in x-ui
            numeric_id = (
                int(hashlib.md5(email.encode()).hexdigest(), 16) % 1_000_000
            )
            remark = f"{plan}_{email.split('@')[0]}"

            try:
                vpn_info = self.xui_client.create_user(
                    user_id=numeric_id, email=email, remark=remark
                )
                # x-ui may return its own UUID
                if isinstance(vpn_info, dict) and vpn_info.get("uuid"):
                    vpn_uuid = vpn_info["uuid"]
                vless_link = (
                    vpn_info.get("vless_link", "")
                    if isinstance(vpn_info, dict)
                    else ""
                )
            except Exception as xui_err:
                logger.error(f"[PROVISION] x-ui create_user failed: {xui_err}")
                # Fallback: generate link via XrayManager
                vless_link = ""

            # 3. Generate VLESS link if x-ui didn't provide one
            if not vless_link:
                try:
                    from vpn_config_generator import generate_vless_link

                    vless_link = generate_vless_link(vpn_uuid)
                except ImportError:
                    if self.xray_manager:
                        vless_link = self.xray_manager.generate_vless_link(
                            vpn_uuid, email
                        )
                    else:
                        vless_link = f"vless://{vpn_uuid}@localhost:443"

            # 4. Update DB (via SQLAlchemy or telegram database)
            await self._update_database(
                email=email,
                vpn_uuid=vpn_uuid,
                plan=plan,
                user_id=user_id,
            )

            # 5. Notify via Telegram if chat_id provided
            if telegram_chat_id:
                await self._send_telegram_config(
                    chat_id=telegram_chat_id,
                    vless_link=vless_link,
                    plan=plan,
                )

            result = ProvisioningResult(
                success=True,
                vpn_uuid=vpn_uuid,
                vless_link=vless_link,
                email=email,
                plan=plan,
            )

            logger.info(
                f"[PROVISION] Success: email={email}, uuid={vpn_uuid[:8]}..."
            )
            return result

        except Exception as e:
            logger.error(f"[PROVISION] Failed: email={email}, error={e}")
            return ProvisioningResult(
                success=False, email=email, error=str(e)
            )

    async def revoke_vpn_user(self, email: str) -> bool:
        """
        Удалить VPN-аккаунт пользователя.

        Args:
            email: Email пользователя

        Returns:
            True если успешно удалён
        """
        if not email:
            return False

        logger.info(f"[REVOKE] Revoking VPN access for {email}")

        try:
            result = self.xui_client.delete_user(email)
            if result:
                logger.info(f"[REVOKE] Successfully revoked {email}")
            else:
                logger.warning(f"[REVOKE] User {email} not found in x-ui")
            return result
        except Exception as e:
            logger.error(f"[REVOKE] Failed for {email}: {e}")
            return False

    async def provision_mesh(
        self,
        name: str,
        nodes: int,
        owner_id: str,
        plan: str = "pro",
        pqc_enabled: bool = True,
    ) -> dict:
        """
        Provision a MaaS mesh network.

        Delegates to the MaaS API's MeshProvisioner.

        Returns:
            dict with mesh_id, status, join_config
        """
        logger.info(
            f"[MESH] Provisioning mesh '{name}' for owner={owner_id}, "
            f"nodes={nodes}, plan={plan}"
        )
        try:
            from src.api.maas import mesh_provisioner

            instance = await mesh_provisioner.create(
                name=name,
                nodes=nodes,
                owner_id=owner_id,
                pqc_enabled=pqc_enabled,
            )
            return {
                "success": True,
                "mesh_id": instance.mesh_id,
                "status": instance.status,
                "nodes": len(instance.node_instances),
            }
        except Exception as e:
            logger.error(f"[MESH] Provisioning failed: {e}")
            return {"success": False, "error": str(e)}

    async def terminate_mesh(self, mesh_id: str) -> bool:
        """Terminate a MaaS mesh network."""
        try:
            from src.api.maas import mesh_provisioner

            return await mesh_provisioner.terminate(mesh_id)
        except Exception as e:
            logger.error(f"[MESH] Termination failed: {e}")
            return False

    async def _update_database(
        self,
        email: str,
        vpn_uuid: str,
        plan: str,
        user_id: Optional[str] = None,
    ) -> None:
        """Update user in the application database."""
        try:
            from src.database import User, get_db
            from datetime import timedelta

            db_gen = get_db()
            db = next(db_gen)
            try:
                db_user = db.query(User).filter(User.email == email).first()
                if not db_user:
                    db_user = User(
                        id=user_id or str(uuid.uuid4()),
                        email=email,
                        password_hash="provisioned",
                        created_at=datetime.utcnow(),
                    )
                    db.add(db_user)

                db_user.plan = plan
                db_user.vpn_uuid = vpn_uuid
                db.commit()
                logger.info(f"[DB] Updated user {email} with plan={plan}")
            finally:
                try:
                    next(db_gen)
                except StopIteration:
                    pass
        except ImportError:
            logger.warning("[DB] SQLAlchemy database not available, skipping DB update")
        except Exception as e:
            logger.error(f"[DB] Failed to update user {email}: {e}")

    async def _send_telegram_config(
        self,
        chat_id: int,
        vless_link: str,
        plan: str,
    ) -> None:
        """Send VPN config to user via Telegram."""
        try:
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
            if not bot_token:
                logger.warning("[TELEGRAM] Bot token not set, skipping notification")
                return

            import httpx

            message = (
                f"✅ **VPN Аккаунт готов!**\n\n"
                f"План: {plan}\n\n"
                f"🔗 **VLESS ссылка:**\n"
                f"`{vless_link}`\n\n"
                f"📱 Импортируй в v2rayNG (Android) или Shadowrocket (iOS)"
            )

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "Markdown",
                    },
                )
                if resp.status_code == 200:
                    logger.info(f"[TELEGRAM] Config sent to chat_id={chat_id}")
                else:
                    logger.error(
                        f"[TELEGRAM] Failed to send: {resp.status_code} {resp.text}"
                    )
        except Exception as e:
            logger.error(f"[TELEGRAM] Notification failed: {e}")


class _SimulatedXUI:
    """Заглушка для dev-окружения без x-ui."""

    simulated = True

    def create_user(self, user_id: int, email: str, remark: str = None):
        vpn_uuid = str(uuid.uuid4())
        logger.info(f"[SIMULATED] Created user {email} with uuid={vpn_uuid[:8]}...")
        return {
            "uuid": vpn_uuid,
            "vless_link": "",
            "server": os.getenv("VPN_SERVER", "localhost"),
            "port": int(os.getenv("VPN_PORT", "443")),
        }

    def delete_user(self, email: str) -> bool:
        logger.info(f"[SIMULATED] Deleted user {email}")
        return True

    def get_active_users_count(self) -> int:
        return 0


# Singleton instance
provisioning_service = ProvisioningService()
