"""Settings loaded from environment variables (see AGENTS.md, Config)."""

import ipaddress
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

PHONE_PORT = 8443
PAIR_PORT = 8080


class ConfigError(ValueError):
    """Raised when a required setting is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    host_ip: str
    max_file_mb: int = 50
    max_video_mb: int = 2048
    angle_tolerance: int = 35
    puid: int = 1000
    pgid: int = 1000
    data_dir: Path = Path("/data")
    inbox_dir: Path = Path("/inbox")
    # Host path of the inbox (INBOX_DIR), only for showing it to the user.
    inbox_label: str = ""

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024

    @property
    def max_video_bytes(self) -> int:
        return self.max_video_mb * 1024 * 1024


def _int(env: Mapping[str, str], name: str, default: int, low: int, high: int) -> int:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a whole number, got {raw!r}") from exc
    if not low <= value <= high:
        raise ConfigError(f"{name} must be between {low} and {high}, got {value}")
    return value


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build Settings from env (defaults to os.environ)."""
    env = os.environ if env is None else env
    host_ip = env.get("HOST_IP", "").strip()
    if not host_ip:
        raise ConfigError("HOST_IP is required (the laptop's LAN IP address)")
    try:
        ipaddress.ip_address(host_ip)
    except ValueError as exc:
        raise ConfigError(f"HOST_IP must be an IP address, got {host_ip!r}") from exc
    return Settings(
        host_ip=host_ip,
        max_file_mb=_int(env, "MAX_FILE_MB", 50, 1, 10_000),
        max_video_mb=_int(env, "MAX_VIDEO_MB", 2048, 1, 100_000),
        angle_tolerance=_int(env, "ANGLE_TOLERANCE", 35, 1, 180),
        puid=_int(env, "PUID", 1000, 0, 2**32 - 1),
        pgid=_int(env, "PGID", 1000, 0, 2**32 - 1),
        inbox_label=env.get("INBOX_DIR", "").strip(),
    )
