from __future__ import annotations

import sys

import src.agents as agents


def test_agents_package_lazily_exports_top_level_agents() -> None:
    agents.__dict__.pop("MarketingAgent", None)
    agents.__dict__.pop("SalesBot", None)
    sys.modules.pop("src.agents.marketing_agent", None)
    sys.modules.pop("src.agents.sales_notify_bot", None)

    assert "MarketingAgent" in agents.__all__
    assert "SalesBot" in agents.__all__
    assert "src.agents.marketing_agent" not in sys.modules
    assert "src.agents.sales_notify_bot" not in sys.modules

    assert agents.MarketingAgent.__name__ == "MarketingAgent"
    assert agents.SalesBot.__name__ == "SalesBot"
    assert "src.agents.marketing_agent" in sys.modules
    assert "src.agents.sales_notify_bot" in sys.modules
