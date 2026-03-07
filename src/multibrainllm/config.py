from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from platformdirs import PlatformDirs

from multibrainllm.domain import AppPaths, ProviderProfile, UserSettings

APP_NAME = "MultiBrainLLM"
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
            log_file=str(log_dir / "multibrain.log"),
        )
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
