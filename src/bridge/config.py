"""
Configuration loading.
"""

from typing import Any, cast
import tomllib
import dataclasses


@dataclasses.dataclass(frozen=True)
class ConfigParseError(Exception):
    """
    Some Configuration parsing error.
    """

    reason: str


@dataclasses.dataclass(frozen=True)
class Config:
    """
    Application Configuration.
    """

    host: str
    port: int


def _require_attribute(
    record: dict[str, Any], key: str, typ: type, prefix: str | None = None
) -> None:
    """Require an attribute with type."""
    if prefix is None:
        prefix = ""

    if not (key in record and isinstance(record[key], typ)):
        raise ConfigParseError(
            f"{prefix}.{key} does not exist or is not of type {typ.__name__}"
        )


def try_load_config(path: str) -> Config:
    """
    Try to load a Config from the path.

    Raises a ConfigParseError if the Config could not be loaded.
    """

    with open(path, "rb") as file:
        try:
            raw = tomllib.load(file)
        except tomllib.TOMLDecodeError as error:
            raise ConfigParseError("error occured during toml loading") from error

    _require_attribute(raw, "host", str)
    _require_attribute(raw, "port", int)

    host = cast(str, raw["host"])
    port = cast(int, raw["port"])

    return Config(host, port)

