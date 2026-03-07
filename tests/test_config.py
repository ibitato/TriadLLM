from pathlib import Path

from triadllm.config import ConfigManager


def test_load_profiles_from_yaml(tmp_path: Path) -> None:
    manager = ConfigManager(root=tmp_path)
    Path(manager.paths.profiles_path).write_text(
        """
profiles:
  demo:
    label: Demo
    provider: openai_compatible
    base_url: https://example.com/v1
    model: demo-model
    api_key_literal: dummy
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
    assert profiles["demo"].provider.value == "openai_compatible"
    assert profiles["demo"].api_key_literal == "dummy"
    assert profiles["demo"].context_window == 128000
    assert profiles["demo"].max_output_tokens_limit == 8192
    assert profiles["demo"].reasoning_effort == "medium"
    assert profiles["demo"].reasoning_summary == "auto"


def test_legacy_paths_are_migrated(tmp_path: Path) -> None:
    legacy_config = tmp_path / "legacy_config"
    legacy_data = tmp_path / "legacy_data"
    legacy_log = tmp_path / "legacy_log"
    legacy_config.mkdir()
    (legacy_data / "sessions").mkdir(parents=True)
    legacy_log.mkdir()
    (legacy_config / "settings.json").write_text('{"language":"en"}', encoding="utf-8")
    (legacy_config / "profiles.yaml").write_text("profiles: {}\n", encoding="utf-8")
    (legacy_data / "sessions" / "old.jsonl").write_text('{"kind":"system"}\n', encoding="utf-8")
    (legacy_log / "multibrain.log").write_text("legacy log\n", encoding="utf-8")

    manager = ConfigManager(root=tmp_path)
    manager._copy_if_missing(legacy_config / "settings.json", Path(manager.paths.settings_path))
    manager._copy_if_missing(legacy_config / "profiles.yaml", Path(manager.paths.profiles_path))
    manager._copy_tree_if_missing(legacy_data / "sessions", Path(manager.paths.sessions_dir))
    manager._copy_if_missing(legacy_log / "multibrain.log", Path(manager.paths.log_file))

    assert Path(manager.paths.settings_path).read_text(encoding="utf-8") == '{"language":"en"}'
    assert Path(manager.paths.profiles_path).read_text(encoding="utf-8") == "profiles: {}\n"
    assert (Path(manager.paths.sessions_dir) / "old.jsonl").exists()
    assert Path(manager.paths.log_file).read_text(encoding="utf-8") == "legacy log\n"
