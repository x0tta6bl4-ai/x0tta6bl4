"""Unit tests for src.vision.processor."""

from __future__ import annotations

import io
import sys

import pytest
from PIL import Image

from src.vision.processor import VisionProcessor


def _png_bytes(*, size: tuple[int, int] = (8, 8), color: tuple[int, int, int] = (12, 34, 56)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color=color).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_process_image_runs_local_analysis_without_api_key(monkeypatch):
    monkeypatch.delenv("VISION_API_KEY", raising=False)

    result = await VisionProcessor().process_image(_png_bytes())

    assert result["status"] == "success"
    assert result["provider"] == "local_pillow"
    assert result["image"]["format"] == "PNG"
    assert result["image"]["width"] == 8
    assert result["image"]["height"] == 8
    assert result["findings"]["external_provider_configured"] is False
    assert result["objects_detected"] == []


@pytest.mark.asyncio
async def test_process_image_preserves_structured_context_for_topology():
    context = {
        "objects_detected": [{"id": "node-a", "type": "router"}],
        "links": [{"source": "node-a", "target": "node-b"}],
        "findings": {"operator_note": "known topology fixture"},
        "text_extracted": ["Connection Refused"],
        "proposed_plan": [{"action": "restart_proxy"}],
    }

    result = await VisionProcessor(api_key="configured").process_image(_png_bytes(), context=context)

    assert result["objects_detected"] == context["objects_detected"]
    assert result["links"] == context["links"]
    assert result["text_extracted"] == ["Connection Refused"]
    assert result["proposed_plan"] == [{"action": "restart_proxy"}]
    assert result["findings"]["topology_source"] == "context"
    assert result["findings"]["external_provider_configured"] is True


@pytest.mark.asyncio
async def test_process_image_rejects_invalid_image_bytes():
    with pytest.raises(ValueError, match="Invalid image bytes"):
        await VisionProcessor().process_image(b"not an image")


@pytest.mark.asyncio
async def test_extract_text_returns_empty_string_without_tesseract(tmp_path, monkeypatch):
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(_png_bytes())
    monkeypatch.setitem(sys.modules, "pytesseract", None)

    text = await VisionProcessor().extract_text(str(image_path))

    assert text == ""


@pytest.mark.asyncio
async def test_extract_text_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        await VisionProcessor().extract_text("/missing/image.png")
