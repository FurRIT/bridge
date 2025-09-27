"""
Module-Neutral Types.
"""

import asyncio
import dataclasses

import playwright.async_api

from bridge.config import Config


@dataclasses.dataclass(frozen=True)
class PlayPersist:
    """
    Persistent `playwright` status.
    """

    play: playwright.async_api.Playwright
    browser: playwright.async_api.Browser
    context: playwright.async_api.BrowserContext
    page: playwright.async_api.Page


@dataclasses.dataclass(frozen=True)
class AppContext:
    """
    App Synchronization Context.
    """

    config: Config
    persist: PlayPersist
    cache_lock: asyncio.Lock = dataclasses.field(default_factory=asyncio.Lock)
