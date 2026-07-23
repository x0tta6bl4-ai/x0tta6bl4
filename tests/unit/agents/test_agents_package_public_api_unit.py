from __future__ import annotations

import sys

import src.agents as agents


def test_agents_package_lazily_exports_top_level_agents() -> None:
    agents.__dict__.pop("GTMAgent", None)
    agents.__dict__.pop("KimiHealingAgent", None)
    sys.modules.pop("src.agents.gtm_agent", None)
    sys.modules.pop("src.agents.kimi_healing_agent", None)

    assert "GTMAgent" in agents.__all__
    assert "KimiHealingAgent" in agents.__all__
    assert "src.agents.gtm_agent" not in sys.modules
    assert "src.agents.kimi_healing_agent" not in sys.modules

    assert agents.GTMAgent.__name__ == "GTMAgent"
    assert agents.KimiHealingAgent.__name__ == "KimiHealingAgent"
    assert "src.agents.gtm_agent" in sys.modules
    assert "src.agents.kimi_healing_agent" in sys.modules
