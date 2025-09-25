"""
Configuration loading.
"""

from typing import Any, cast
import os.path
import tomllib
import dataclasses


@dataclasses.dataclass(frozen=True)
class ConfigParseError(Exception):
    """
    Some Configuration parsing error.
    """

    reason: str


@dataclasses.dataclass(frozen=True)
class ClientSection:
    """
    A `client.*` section.
    """

    name: str
    host: str
    port: int


@dataclasses.dataclass(frozen=True)
class SiteSection:
    """
    A `site` section.
    """

    host: str
    username: str
    password: str


@dataclasses.dataclass(frozen=True)
class Config:
    """
    Application Configuration.
    """

    cache: str
    authcache: str
    frequency: int
    site: SiteSection
    clients: list[ClientSection]


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


def _load_site_section(table: dict[str, Any]) -> SiteSection:
    _require_attribute(table, "host", str, prefix="site")
    _require_attribute(table, "username", str, prefix="site")
    _require_attribute(table, "password", str, prefix="site")

    host: str = table["host"]
    username: str = table["username"]
    password: str = table["password"]

    return SiteSection(host, username, password)


def _load_client_section(name: str, table: dict[str, Any]) -> ClientSection:
    _require_attribute(table, "host", str, prefix=f"client.{name}")
    _require_attribute(table, "port", int, prefix=f"client.{name}")

    host: str = table["host"]
    port: int = table["port"]

    return ClientSection(name, host, port)


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
    _require_attribute(raw, "cache", str)
    _require_attribute(raw, "authcache", str)
    _require_attribute(raw, "frequency", int)

    cache = cast(str, raw["cache"])
    authcache = cast(str, raw["authcache"])
    frequency = cast(int, raw["frequency"])

    # XXX(mwp): resolve the cache path relative to the configuration file if it
    # is a relative path
    if not os.path.isabs(cache):
        cache = os.path.relpath(cache, start=os.path.dirname(path))

    if not ("site" in raw and isinstance(raw["site"], dict)):
        raise ConfigParseError(".site must be a dict")

    site = _load_site_section(raw["site"])

    if ("client" in raw) and (not isinstance(raw["client"], dict)):
        raise ConfigParseError(".client must be a dict")

    sections = []
    client_entries: dict[str, Any] = raw["client"] if "client" in raw else {}

    for name, table in client_entries.items():
        if not isinstance(table, dict):
            raise ConfigParseError(f".client.{name} must be a dict")

        section = _load_client_section(name, table)
        sections.append(section)

    return Config(cache, authcache, frequency, site, sections)
