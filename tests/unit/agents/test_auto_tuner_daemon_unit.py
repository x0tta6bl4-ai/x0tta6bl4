"""Unit test for Background Auto-Tuner Daemon script."""

from scripts.agents.auto_tuner_daemon import main, run_daemon_step


def test_run_daemon_step():
    delta = run_daemon_step(target_agent="agent-2", dry_run=True)
    assert isinstance(delta, float)


def test_auto_tuner_daemon_main():
    import sys
    sys.argv = ["auto_tuner_daemon.py", "--once"]
    exit_code = main()
    assert exit_code == 0
