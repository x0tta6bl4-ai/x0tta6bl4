import importlib

from _pytest.capture import CaptureFixture

import src.legacy_cli as cli


def test_cli_main(capsys: CaptureFixture[str]) -> None:
    rc = cli.main()
    captured = capsys.readouterr()
    assert rc == 0
    assert "x0tta6bl4 v1.0.0" in captured.out
    assert "x0tta6bl4-server" in captured.out
