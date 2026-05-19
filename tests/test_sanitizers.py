"""Tests for sanitizer functions."""

from __future__ import annotations

from triadllm.tools.sanitizers import (
    _convert_markdown_to_text,
    _sanitize_firecrawl_result,
)


class TestConvertMarkdownToText:
    def test_convert_markdown_removes_links(self):
        text = "Visit [Google](https://google.com) for more."
        result = _convert_markdown_to_text(text)
        assert "https://google.com" not in result
        assert "Google" in result

    def test_convert_markdown_removes_images(self):
        text = "Here is an image: ![alt text](https://img.com/pic.png)"
        result = _convert_markdown_to_text(text)
        assert "https://img.com" not in result
        assert "![" not in result

    def test_convert_markdown_keeps_text(self):
        text = "This is plain text content that should remain."
        result = _convert_markdown_to_text(text)
        assert result == text


class TestSanitizeFirecrawlResult:
    def test_sanitize_firecrawl_result_processes_data_list(self):
        result = {
            "data": [
                {
                    "content": "Visit [link](http://example.com) for info.",
                    "title": "Test",
                },
                {
                    "text": "![img](http://img.com/x.png) Some text here.",
                    "url": "http://example.com",
                },
            ]
        }
        sanitized = _sanitize_firecrawl_result(result)
        assert isinstance(sanitized["data"], list)
        assert len(sanitized["data"]) == 2
        # Links should be removed from content
        assert "http://example.com" not in sanitized["data"][0]["content"]
        assert "link" in sanitized["data"][0]["content"]
        # Images should be removed from text
        assert "![img]" not in sanitized["data"][1]["text"]
        # Non-content fields preserved
        assert sanitized["data"][0]["title"] == "Test"
        assert sanitized["data"][1]["url"] == "http://example.com"
