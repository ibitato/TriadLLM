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
    reasoning_effort: medium
""",
        encoding="utf-8",
    )

    profiles = manager.load_profiles()

    assert profiles["demo"].id == "demo"
    assert profiles["demo"].model == "demo-model"
    assert profiles["demo"].reasoning_effort == "medium"
