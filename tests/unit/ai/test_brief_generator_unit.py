"""Alias tests for brief_generator module — see test_ai_navigation_unit.py for full suite."""
import json
import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.ai.navigation.brief_generator import BriefGenerator, load_brief_inputs, main


class TestBriefGeneratorModule:
    def test_import(self):
        assert BriefGenerator is not None

    def test_instantiate(self):
        bg = BriefGenerator()
        assert hasattr(bg, "generate_markdown")

    def test_generate_markdown_returns_string(self):
        bg = BriefGenerator()
        result = bg.generate_markdown(
            [{"title": "Test", "summary": "Summary", "url": "http://t.co",
              "relevance_score": 0.9, "source": "test", "category": "security"}],
            actions=["monitor PQC standards"],
        )
        assert isinstance(result, str)


def test_load_brief_inputs_from_combined_json(tmp_path):
    payload_path = tmp_path / "brief-input.json"
    payload_path.write_text(
        json.dumps(
            {
                "filtered_news": [
                    {
                        "title": "PQC standard update",
                        "url": "https://example.test/pqc",
                        "category": "BENCHMARK",
                        "relevance_score": 0.8,
                    }
                ],
                "actions": ["Review standards delta"],
            }
        ),
        encoding="utf-8",
    )

    news, actions = load_brief_inputs(str(payload_path))
    assert news[0]["title"] == "PQC standard update"
    assert actions == ["Review standards delta"]


def test_main_generates_markdown_from_json_files(tmp_path, capsys):
    news_path = tmp_path / "news.json"
    actions_path = tmp_path / "actions.json"
    news_path.write_text(
        json.dumps(
            [
                {
                    "title": "Mesh benchmark",
                    "url": "https://example.test/mesh",
                    "category": "BENCHMARK",
                    "relevance_score": 0.6,
                }
            ]
        ),
        encoding="utf-8",
    )
    actions_path.write_text(json.dumps(["Compare throughput"]), encoding="utf-8")

    assert main(
        [
            "--project-name",
            "mesh-review",
            "--news",
            str(news_path),
            "--actions",
            str(actions_path),
        ]
    ) == 0
    output = capsys.readouterr().out
    assert "mesh-review Visionary Brief" in output
    assert "Mesh benchmark" in output
    assert "Compare throughput" in output
