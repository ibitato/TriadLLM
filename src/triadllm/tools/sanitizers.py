from __future__ import annotations

import re


def _convert_markdown_to_text(content: str) -> str:
    """Convert markdown content to plain text, removing links, images, and formatting."""
    if not content or not isinstance(content, str):
        return content or ""

    content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
    content = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", content)
    content = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", content)
    content = re.sub(r"<[^>]+>", "", content)
    content = re.sub(r"^(#+)\s*", "", content, flags=re.MULTILINE)
    content = re.sub(r"(\*\*|\*|__|_)(.*?)\1", r"\2", content)
    content = re.sub(r"`([^`]*)`", r"\1", content)
    content = re.sub(r"^>\s*", "", content, flags=re.MULTILINE)
    content = re.sub(r"^[\-*_]{3,}\s*$", "", content, flags=re.MULTILINE)
    content = re.sub(r"^[\s]*[\-*+]\s+", "", content, flags=re.MULTILINE)
    content = re.sub(r"^[\s]*\d+\.\s+", "", content, flags=re.MULTILINE)
    content = re.sub(r"\n{3,}", "\n\n", content)
    content = content.strip()

    return content


def _sanitize_firecrawl_result(result: dict[str, object]) -> dict[str, object]:
    """Process Firecrawl result to reduce size and convert to plain text."""
    if not isinstance(result, dict):
        return result

    sanitized: dict[str, object] = {}
    for key, value in result.items():
        if key == "data" and isinstance(value, list):
            sanitized[key] = _sanitize_data_list(value)
        elif key == "data" and isinstance(value, dict):
            # Search API returns data as {"web": [...], ...}
            sanitized_data: dict[str, object] = {}
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, list):
                    sanitized_data[sub_key] = _sanitize_data_list(sub_value)
                else:
                    sanitized_data[sub_key] = sub_value
            sanitized[key] = sanitized_data
        elif key in ("content", "text", "description", "metadata", "markdown") and isinstance(value, str):
            sanitized[key] = _convert_markdown_to_text(value)
        else:
            sanitized[key] = value

    return sanitized


def _sanitize_data_list(items: list[object]) -> list[object]:
    """Sanitize a list of result items."""
    sanitized: list[object] = []
    for item in items:
        if isinstance(item, dict):
            processed_item: dict[str, object] = {}
            for item_key, item_value in item.items():
                if item_key in ("content", "text", "description", "markdown") and isinstance(item_value, str):
                    processed_item[item_key] = _convert_markdown_to_text(item_value)
                else:
                    processed_item[item_key] = item_value
            sanitized.append(processed_item)
        else:
            sanitized.append(item)
    return sanitized
