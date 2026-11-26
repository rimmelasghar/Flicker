import pytest

from server.config import ConfigError, load_settings


def test_defaults_apply_when_only_host_ip_set():
    settings = load_settings({"HOST_IP": "192.168.1.50"})
    assert settings.host_ip == "192.168.1.50"
    assert settings.max_file_mb == 50
    assert settings.max_file_bytes == 50 * 1024 * 1024
    assert settings.angle_tolerance == 35
    assert (settings.puid, settings.pgid) == (1000, 1000)


def test_values_are_read_from_env():
    settings = load_settings(
        {
            "HOST_IP": "10.0.0.7",
            "MAX_FILE_MB": "10",
            "ANGLE_TOLERANCE": "20",
            "PUID": "501",
            "PGID": "20",
        }
    )
    assert settings.max_file_mb == 10
    assert settings.angle_tolerance == 20
    assert (settings.puid, settings.pgid) == (501, 20)


def test_blank_optional_values_use_defaults():
    settings = load_settings({"HOST_IP": "10.0.0.7", "MAX_FILE_MB": ""})
    assert settings.max_file_mb == 50


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"HOST_IP": ""},
        {"HOST_IP": "my-laptop"},
        {"HOST_IP": "10.0.0.7", "MAX_FILE_MB": "abc"},
        {"HOST_IP": "10.0.0.7", "MAX_FILE_MB": "0"},
        {"HOST_IP": "10.0.0.7", "ANGLE_TOLERANCE": "500"},
    ],
)
def test_invalid_env_raises(env):
    with pytest.raises(ConfigError):
        load_settings(env)
