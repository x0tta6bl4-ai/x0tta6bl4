"""
Provisioning Service — x0tta6bl4
=================================

Единый сервис провижининга (VPN + MaaS).
Центральная точка для создания/удаления аккаунтов,
вызывается из billing webhook, Telegram bot, admin API, MaaS API.

Zero-Trust: каждый вызов валидирует входные данные,
каждый аккаунт получает уникальный UUID.
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union

from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata
from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_VPN_PROVISIONING_SOURCE_AGENT = "vpn-provisioning-service"
_VPN_PROVISIONING_LAYER = "service_vpn_provisioning_control_action"
VPN_PROVISIONING_CLAIM_BOUNDARY = (
    "VPN provisioning service evidence records local x-ui/VLESS generation, "
    "local DB update, Telegram notification attempt, and bounded result state "
    "only. It does not prove customer payment settlement, client installation, "
    "VPN dataplane reachability, DNS privacy, firewall correctness, or that "
    "customer traffic uses the VPN tunnel."
)
_MESH_PROVISIONING_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "dpi_bypass",
    "settlement_finality",
    "economy_finality",
    "bank_settlement",
    "revenue_recognition",
)
MESH_PROVISIONING_CLAIM_BOUNDARY = (
    "MaaS mesh provisioning service results record a local delegate call to the "
    "configured MeshProvisioner and bounded lifecycle fields only. success, "
    "status, and nodes do not prove external infrastructure provisioning, node "
    "reachability, node dataplane join, routing convergence, customer traffic, "
    "external DPI bypass, settlement finality, bank settlement, revenue "
    "recognition, production SLOs, or production readiness."
)


def _redacted_sha256_prefix(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _identity_evidence() -> Dict[str, Any]:
    identity = service_event_identity(service_name=_VPN_PROVISIONING_SOURCE_AGENT)
    return {
        "spiffe_id_present": bool(str(identity.get("spiffe_id") or "").strip()),
        "spiffe_id_hash": _redacted_sha256_prefix(identity.get("spiffe_id")),
        "did_present": bool(str(identity.get("did") or "").strip()),
        "did_hash": _redacted_sha256_prefix(identity.get("did")),
        "wallet_address_present": bool(
            str(identity.get("wallet_address") or "").strip()
        ),
        "wallet_address_hash": _redacted_sha256_prefix(
            identity.get("wallet_address")
        ),
        "raw_identity_redacted": True,
    }


def _event_evidence_reference(
    event_id: Optional[str],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "source_agent": _VPN_PROVISIONING_SOURCE_AGENT,
        "layer": _VPN_PROVISIONING_LAYER,
        "operation": payload.get("operation"),
        "stage": payload.get("stage"),
        "status": payload.get("status"),
        "reason": payload.get("reason"),
        "control_action": payload.get("control_action"),
        "claim_boundary": payload.get("claim_boundary"),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _mesh_provisioning_claim_gate(
    *,
    surface: str = "provisioning_service.provision_mesh",
    provisioner_available: bool | None = None,
    provisioner_create_succeeded: bool | None = None,
) -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.mesh_provisioning_service_claim_gate.v1",
        "surface": surface,
        "local_mesh_provisioner_delegate_claim_allowed": bool(
            provisioner_create_succeeded
        ),
        "local_mesh_lifecycle_claim_allowed": bool(provisioner_create_succeeded),
        "local_requested_node_count_claim_allowed": bool(
            provisioner_create_succeeded
        ),
        "mesh_provisioner_available": provisioner_available is True,
        "mesh_provisioner_create_succeeded": provisioner_create_succeeded is True,
        "external_infrastructure_provisioning_claim_allowed": False,
        "node_dataplane_join_claim_allowed": False,
        "node_reachability_claim_allowed": False,
        "routing_convergence_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "economy_finality_claim_allowed": False,
        "bank_settlement_claim_allowed": False,
        "revenue_recognition_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "claim_boundary": MESH_PROVISIONING_CLAIM_BOUNDARY,
    }


def _mesh_provisioning_cross_plane_gate(surface: str) -> Dict[str, Any]:
    return cross_plane_claim_gate_metadata(
        _MESH_PROVISIONING_CROSS_PLANE_CLAIMS,
        surface=surface,
    )


def _resolve_mesh_provisioner():
    """Support both legacy and refactored MaaS module layouts."""
    try:
        from src.api.maas import mesh_provisioner as provisioner
    except Exception:
        try:
            from src.api.maas_legacy import mesh_provisioner as provisioner
        except Exception:
            return None
    return provisioner


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
        self.event_bus: Optional[EventBus] = None
        self.event_project_root = "."
        self._last_event_evidence: Optional[Dict[str, Any]] = None

    def _event_bus_or_none(
        self,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ) -> Optional[EventBus]:
        if event_bus is not None:
            return event_bus
        if self.event_bus is not None:
            return self.event_bus
        try:
            self.event_bus = get_event_bus(event_project_root or self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize vpn-provisioning EventBus: %s", exc)
            return None

    def _publish_vpn_provisioning_event(
        self,
        *,
        event_bus: Optional[EventBus],
        event_project_root: str,
        started_at: float,
        stage: str,
        status: str,
        email: Optional[str],
        plan: str,
        source_label: str,
        user_id: Optional[str] = None,
        telegram_chat_id: Optional[int] = None,
        vpn_uuid: Optional[str] = None,
        vless_link: Optional[str] = None,
        xui_create_attempted: bool = False,
        xui_create_success: Optional[bool] = None,
        fallback_link_generated: bool = False,
        db_update_attempted: bool = False,
        telegram_notify_attempted: bool = False,
        reason: Optional[str] = None,
        error: Optional[Exception] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none(event_bus, event_project_root)
        if bus is None:
            return None
        payload = {
            "component": "services.provisioning_service",
            "operation": "provision_vpn_user",
            "service_name": _VPN_PROVISIONING_SOURCE_AGENT,
            "source_alias": _VPN_PROVISIONING_SOURCE_AGENT,
            "layer": _VPN_PROVISIONING_LAYER,
            "stage": stage,
            "status": status,
            "reason": reason,
            "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
            "plan": str(plan or "")[:40],
            "source_label": str(source_label or "")[:80],
            "email_hash": _redacted_sha256_prefix(
                str(email).lower() if email else None
            ),
            "email_present": bool(email),
            "user_id_hash": _redacted_sha256_prefix(user_id),
            "telegram_chat_id_hash": _redacted_sha256_prefix(telegram_chat_id),
            "telegram_chat_id_present": telegram_chat_id is not None,
            "vpn_uuid_hash": _redacted_sha256_prefix(vpn_uuid),
            "vpn_uuid_present": bool(vpn_uuid),
            "vless_link_present": bool(vless_link),
            "xui_create_attempted": bool(xui_create_attempted),
            "xui_create_success": xui_create_success,
            "fallback_link_generated": bool(fallback_link_generated),
            "db_update_attempted": bool(db_update_attempted),
            "telegram_notify_attempted": bool(telegram_notify_attempted),
            "error_hash": _redacted_sha256_prefix(error) if error else None,
            "control_action": True,
            "observed_state": False,
            "service_identity": _identity_evidence(),
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
            "claim_boundary": VPN_PROVISIONING_CLAIM_BOUNDARY,
        }
        try:
            event = bus.publish(
                EventType.PIPELINE_STAGE_END
                if status == "success"
                else EventType.TASK_BLOCKED,
                _VPN_PROVISIONING_SOURCE_AGENT,
                payload,
                priority=5,
            )
            self._last_event_evidence = _event_evidence_reference(
                event.event_id,
                payload,
            )
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish vpn-provisioning event: %s", exc)
            self._last_event_evidence = None
            return None

    def get_last_event_evidence(self) -> Optional[Dict[str, Any]]:
        """Return a redacted reference to the latest provisioning event."""
        if self._last_event_evidence is None:
            return None
        return dict(self._last_event_evidence)

    @property
    def xui_client(self):
        """Lazy-load XUIAPIClient."""
        if self._xui_client is None:
            try:
                from src.services.vpn_config_generator import XUIAPIClient
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
        source: Union[ProvisioningSource, str] = ProvisioningSource.STRIPE_WEBHOOK,
        user_id: Optional[str] = None,
        telegram_chat_id: Optional[int] = None,
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
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
        started_at = time.monotonic()
        source_label = source.value if isinstance(source, ProvisioningSource) else str(source)
        if not email or "@" not in email:
            self._publish_vpn_provisioning_event(
                event_bus=event_bus,
                event_project_root=event_project_root,
                started_at=started_at,
                stage="input_validation",
                status="blocked",
                email=email,
                plan=plan,
                source_label=source_label,
                user_id=user_id,
                telegram_chat_id=telegram_chat_id,
                reason="invalid_email",
            )
            return ProvisioningResult(
                success=False, email=email, error="Invalid email"
            )

        logger.info(
            f"[PROVISION] Start: email={email}, plan={plan}, source={source_label}"
        )

        xui_create_attempted = False
        xui_create_success: Optional[bool] = None
        fallback_link_generated = False
        db_update_attempted = False
        telegram_notify_attempted = False
        try:
            # 1. Generate unique VPN UUID
            vpn_uuid = str(uuid.uuid4())

            # 2. Create user in x-ui
            numeric_id = (
                int(hashlib.sha256(email.encode()).hexdigest(), 16) % 1_000_000
            )
            remark = f"{plan}_{email.split('@')[0]}"

            try:
                xui_create_attempted = True
                vpn_info = self.xui_client.create_user(
                    user_id=numeric_id, email=email, remark=remark
                )
                xui_create_success = True
                # x-ui may return its own UUID
                if isinstance(vpn_info, dict) and vpn_info.get("uuid"):
                    vpn_uuid = vpn_info["uuid"]
                vless_link = (
                    vpn_info.get("vless_link", "")
                    if isinstance(vpn_info, dict)
                    else ""
                )
            except Exception as xui_err:
                xui_create_success = False
                logger.error(f"[PROVISION] x-ui create_user failed: {xui_err}")
                # Fallback: generate link via XrayManager
                vless_link = ""

            # 3. Generate VLESS link if x-ui didn't provide one
            if not vless_link:
                try:
                    from vpn_config_generator import generate_vless_link

                    vless_link = generate_vless_link(vpn_uuid)
                    fallback_link_generated = True
                except ImportError:
                    if self.xray_manager:
                        vless_link = self.xray_manager.generate_vless_link(
                            vpn_uuid, email
                        )
                        fallback_link_generated = True
                    else:
                        vless_link = f"vless://{vpn_uuid}@localhost:443"
                        fallback_link_generated = True

            # 4. Update DB (via SQLAlchemy or telegram database)
            db_update_attempted = True
            await self._update_database(
                email=email,
                vpn_uuid=vpn_uuid,
                plan=plan,
                user_id=user_id,
            )

            # 5. Notify via Telegram if chat_id provided
            if telegram_chat_id:
                telegram_notify_attempted = True
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
            self._publish_vpn_provisioning_event(
                event_bus=event_bus,
                event_project_root=event_project_root,
                started_at=started_at,
                stage="vpn_provision",
                status="success",
                email=email,
                plan=plan,
                source_label=source_label,
                user_id=user_id,
                telegram_chat_id=telegram_chat_id,
                vpn_uuid=vpn_uuid,
                vless_link=vless_link,
                xui_create_attempted=xui_create_attempted,
                xui_create_success=xui_create_success,
                fallback_link_generated=fallback_link_generated,
                db_update_attempted=db_update_attempted,
                telegram_notify_attempted=telegram_notify_attempted,
            )
            return result

        except Exception as e:
            logger.error(f"[PROVISION] Failed: email={email}, error={e}")
            self._publish_vpn_provisioning_event(
                event_bus=event_bus,
                event_project_root=event_project_root,
                started_at=started_at,
                stage="vpn_provision",
                status="error",
                email=email,
                plan=plan,
                source_label=source_label,
                user_id=user_id,
                telegram_chat_id=telegram_chat_id,
                xui_create_attempted=xui_create_attempted,
                xui_create_success=xui_create_success,
                fallback_link_generated=fallback_link_generated,
                db_update_attempted=db_update_attempted,
                telegram_notify_attempted=telegram_notify_attempted,
                reason="exception",
                error=e,
            )
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
        provisioner_available = False
        provisioner_create_succeeded = False
        try:
            mesh_provisioner = _resolve_mesh_provisioner()
            if mesh_provisioner is None:
                raise RuntimeError("MaaS mesh provisioner not available")
            provisioner_available = True

            instance = await mesh_provisioner.create(
                name=name,
                nodes=nodes,
                owner_id=owner_id,
                pqc_enabled=pqc_enabled,
            )
            provisioner_create_succeeded = True
            return {
                "success": True,
                "mesh_id": instance.mesh_id,
                "status": instance.status,
                "nodes": len(instance.node_instances),
                "mesh_provisioning_claim_gate": _mesh_provisioning_claim_gate(
                    provisioner_available=provisioner_available,
                    provisioner_create_succeeded=provisioner_create_succeeded,
                ),
                "cross_plane_claim_gate": _mesh_provisioning_cross_plane_gate(
                    "provisioning_service.provision_mesh"
                ),
            }
        except Exception as e:
            logger.error(f"[MESH] Provisioning failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "mesh_provisioning_claim_gate": _mesh_provisioning_claim_gate(
                    provisioner_available=provisioner_available,
                    provisioner_create_succeeded=provisioner_create_succeeded,
                ),
                "cross_plane_claim_gate": _mesh_provisioning_cross_plane_gate(
                    "provisioning_service.provision_mesh"
                ),
            }

    async def terminate_mesh(self, mesh_id: str) -> bool:
        """Terminate a MaaS mesh network."""
        try:
            mesh_provisioner = _resolve_mesh_provisioner()
            if mesh_provisioner is None:
                logger.error("[MESH] Provisioner unavailable, cannot terminate %s", mesh_id)
                return False

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

