from pathlib import Path

from multibrainllm.config import ConfigManager


def test_load_profiles_from_yaml(tmp_path: Path) -> None:
    manager = ConfigManager(root=tmp_path)
    Path(manager.paths.profiles_path).write_text(
        """
profiles:
  demo:
    label: Demo
    base_url: https://example.com/v1
    model: demo-model
    api_key_env: DEMO_KEY
    context_window: 128000
    max_output_tokens_limit: 8192
    reasoning_effort: medium
    reasoning_summary: auto
""",
        encoding="utf-8",
    )

    profiles = manager.load_profiles()

    assert profiles["demo"].id == "demo"
    assert profiles["demo"].model == "demo-model"
    assert profiles["demo"].context_window == 128000
    assert profiles["demo"].max_output_tokens_limit == 8192
    assert profiles["demo"].reasoning_effort == "medium"
    assert profiles["demo"].reasoning_summary == "auto"
