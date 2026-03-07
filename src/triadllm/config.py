from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml
from platformdirs import PlatformDirs

from triadllm.domain import AppPaths, ProviderProfile, UserSettings

APP_NAME = "TriadLLM"
LEGACY_APP_NAME = "MultiBrainLLM"
APP_AUTHOR = "David R. Lopez B"


class ConfigManager:
    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            dirs = PlatformDirs(APP_NAME, APP_AUTHOR, roaming=True)
            config_dir = Path(dirs.user_config_dir)
            data_dir = Path(dirs.user_data_dir)
            log_dir = Path(dirs.user_log_dir)
        else:
            config_dir = root / "config"
            data_dir = root / "data"
            log_dir = root / "logs"

        self.paths = AppPaths(
            config_dir=str(config_dir),
            data_dir=str(data_dir),
            log_dir=str(log_dir),
            settings_path=str(config_dir / "settings.json"),
            profiles_path=str(config_dir / "profiles.yaml"),
            sessions_dir=str(data_dir / "sessions"),
            log_file=str(log_dir / "triadllm.log"),
        )
        if root is None:
            self._migrate_legacy_paths()
        self.ensure_directories()

    def ensure_directories(self) -> None:
        for path in (
            self.paths.config_dir,
            self.paths.data_dir,
            self.paths.log_dir,
            self.paths.sessions_dir,
        ):
            Path(path).mkdir(parents=True, exist_ok=True)

    def load_settings(self) -> UserSettings:
        settings_path = Path(self.paths.settings_path)
        if not settings_path.exists():
            settings = UserSettings()
            self.save_settings(settings)
            return settings
        return UserSettings.model_validate_json(settings_path.read_text(encoding="utf-8"))

    def save_settings(self, settings: UserSettings) -> None:
        Path(self.paths.settings_path).write_text(
            settings.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def load_profiles(self) -> dict[str, ProviderProfile]:
        data = self._load_profiles_document()
        raw_profiles = data.get("profiles", {})
        profiles: dict[str, ProviderProfile] = {}
        for profile_id, payload in raw_profiles.items():
            payload = dict(payload or {})
            payload["id"] = profile_id
            profiles[profile_id] = ProviderProfile.model_validate(payload)
        return profiles

    def load_profile_default(self) -> str | None:
        data = self._load_profiles_document()
        default_profile = data.get("default_profile")
        if default_profile is None:
            return None
        return str(default_profile)

    def sample_profiles_path(self) -> Path:
        return Path(__file__).resolve().parent / "examples" / "profiles.yaml"

    def config_snapshot(self, settings: UserSettings, profiles: dict[str, ProviderProfile]) -> dict[str, Any]:
        return {
            "paths": self.paths.model_dump(),
            "settings": settings.model_dump(mode="json"),
            "profiles": {
                profile_id: profile.model_dump(mode="json")
                for profile_id, profile in profiles.items()
            },
            "sample_profiles": str(self.sample_profiles_path()),
        }

    def _load_profiles_document(self) -> dict[str, Any]:
        profiles_path = Path(self.paths.profiles_path)
        if not profiles_path.exists():
            return {}
        return yaml.safe_load(profiles_path.read_text(encoding="utf-8")) or {}

    def _migrate_legacy_paths(self) -> None:
        legacy_dirs = PlatformDirs(LEGACY_APP_NAME, APP_AUTHOR, roaming=True)
        legacy_config_dir = Path(legacy_dirs.user_config_dir)
        legacy_data_dir = Path(legacy_dirs.user_data_dir)
        legacy_log_dir = Path(legacy_dirs.user_log_dir)

        self._copy_if_missing(legacy_config_dir / "settings.json", Path(self.paths.settings_path))
        self._copy_if_missing(legacy_config_dir / "profiles.yaml", Path(self.paths.profiles_path))
        self._copy_tree_if_missing(legacy_data_dir / "sessions", Path(self.paths.sessions_dir))
        self._copy_if_missing(legacy_log_dir / "multibrain.log", Path(self.paths.log_file))

    def _copy_if_missing(self, source: Path, destination: Path) -> None:
        if not source.exists() or destination.exists():
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    def _copy_tree_if_missing(self, source: Path, destination: Path) -> None:
        if not source.exists():
            return
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, destination)
            return
        if any(destination.iterdir()):
            return
        for item in source.iterdir():
            target = destination / item.name
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
