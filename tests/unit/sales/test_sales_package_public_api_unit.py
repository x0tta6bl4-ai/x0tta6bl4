import sys

import src.sales as sales


def test_sales_package_exports_core_commercial_builders_lazily():
    sales.__dict__.pop("create_app", None)
    sys.modules.pop("src.sales.x402_paid_api", None)

    assert "build_product_idea_portfolio" in sales.__all__
    assert "build_paid_task_pipeline" in sales.__all__
    assert "create_app" in sales.__all__

    assert callable(sales.build_product_idea_portfolio)
    assert callable(sales.build_paid_task_pipeline)
    assert "src.sales.x402_paid_api" not in sys.modules


def test_sales_package_loads_x402_surface_only_when_requested():
    sales.__dict__.pop("create_app", None)
    sys.modules.pop("src.sales.x402_paid_api", None)

    assert callable(sales.create_app)
    assert "src.sales.x402_paid_api" in sys.modules


def test_sales_package_lazily_exports_telegram_bot_v2_helpers():
    sales.__dict__.pop("generate_code", None)
    sys.modules.pop("src.sales.telegram_bot_v2", None)

    assert "generate_code" in sales.__all__
    assert "generate_ref_link" in sales.__all__
    assert "TELEGRAM_AVAILABLE" in sales.__all__
    assert "src.sales.telegram_bot_v2" not in sys.modules

    assert callable(sales.generate_code)
    assert "src.sales.telegram_bot_v2" in sys.modules
