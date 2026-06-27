from __future__ import annotations

import json

from src.dao import check_balance


def test_main_reads_balance_from_stats_file(tmp_path, capsys, monkeypatch):
    stats_file = tmp_path / "node_stats.json"
    stats_file.write_text(
        json.dumps(
            {
                "node_id": "node-21",
                "balance": "1002.50",
                "earnings_today": "1.25",
                "packets": 42,
                "bytes": 8192,
                "uptime": 3600,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("X0T_USD_PRICE", "0.20")

    result = check_balance.main(["--detailed", "--stats-file", str(stats_file)])

    assert result == 0
    output = capsys.readouterr().out
    assert "Node: node-21" in output
    assert "Баланс: 1,002.5000 X0T" in output
    assert "Заработок сегодня: 1.2500 X0T" in output
    assert "Месячная проекция: 37.50 X0T ($7.50 @ $0.20)" in output


def test_main_fails_closed_when_stats_file_is_missing(tmp_path, capsys):
    missing_file = tmp_path / "missing_node_stats.json"

    result = check_balance.main(["--stats-file", str(missing_file)])

    assert result == 2
    output = capsys.readouterr().out
    assert "balance stats file not found" in output


def test_main_rejects_non_numeric_balance(tmp_path, capsys):
    stats_file = tmp_path / "node_stats.json"
    stats_file.write_text(
        json.dumps(
            {
                "node_id": "node-22",
                "balance": "not-a-number",
                "earnings_today": "1.25",
            }
        ),
        encoding="utf-8",
    )

    result = check_balance.main(["--stats-file", str(stats_file)])

    assert result == 2
    output = capsys.readouterr().out
    assert "balance must be numeric" in output
