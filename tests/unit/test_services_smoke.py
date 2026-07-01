"""
Smoke tests for src.services modules.
Ensures all service modules can be imported without errors.
"""


def test_dao_enforcement_import():
    """src.services.dao_enforcement imports successfully."""
    import src.services.dao_enforcement  # noqa: F401


def test_maas_analytics_service_import():
    """src.services.maas_analytics_service imports successfully."""
    import src.services.maas_analytics_service  # noqa: F401


def test_maas_auth_service_import():
    """src.services.maas_auth_service imports successfully."""
    import src.services.maas_auth_service  # noqa: F401


def test_maas_orchestrator_import():
    """src.services.maas_orchestrator imports successfully."""
    import src.services.maas_orchestrator  # noqa: F401


def test_marketplace_events_import():
    """src.services.marketplace_events imports successfully."""
    import src.services.marketplace_events  # noqa: F401


def test_marketplace_janitor_import():
    """src.services.marketplace_janitor imports successfully."""
    import src.services.marketplace_janitor  # noqa: F401


def test_marketplace_settlement_import():
    """src.services.marketplace_settlement imports successfully."""
    import src.services.marketplace_settlement  # noqa: F401


def test_node_manager_service_import():
    """src.services.node_manager_service imports successfully."""
    import src.services.node_manager_service  # noqa: F401


def test_pqc_logic_contract_import():
    """src.services.pqc_logic_contract imports successfully."""
    import src.services.pqc_logic_contract  # noqa: F401


def test_pqc_rotator_service_import():
    """src.services.pqc_rotator_service imports successfully."""
    import src.services.pqc_rotator_service  # noqa: F401


def test_provisioning_service_import():
    """src.services.provisioning_service imports successfully."""
    import src.services.provisioning_service  # noqa: F401


def test_reward_events_import():
    """src.services.reward_events imports successfully."""
    import src.services.reward_events  # noqa: F401


def test_run_janitor_import():
    """src.services.run_janitor imports successfully."""
    import src.services.run_janitor  # noqa: F401


def test_service_event_identity_import():
    """src.services.service_event_identity imports successfully."""
    import src.services.service_event_identity  # noqa: F401


def test_service_event_trace_import():
    """src.services.service_event_trace imports successfully."""
    import src.services.service_event_trace  # noqa: F401


def test_service_identity_registry_import():
    """src.services.service_identity_registry imports successfully."""
    import src.services.service_identity_registry  # noqa: F401


def test_share_to_earn_service_import():
    """src.services.share_to_earn_service imports successfully."""
    import src.services.share_to_earn_service  # noqa: F401


def test_xray_manager_import():
    """src.services.xray_manager imports successfully."""
    import src.services.xray_manager  # noqa: F401
