import sys


def test_src_package_does_not_eagerly_import_security():
    sys.modules.pop("src", None)
    sys.modules.pop("src.security", None)

    import src  # noqa: F401

    assert "src.security" not in sys.modules


def test_coordination_import_does_not_require_security_dependencies():
    import src.coordination.events as events

    assert events.EventType.PIPELINE_STAGE_END.value == "pipeline.stage_end"
