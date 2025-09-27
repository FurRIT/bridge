"""
Module-Neutral Types.
"""

import asyncio
import dataclasses


@dataclasses.dataclass(frozen=True)
class AppContext:
    """
    App Synchronization Context.
    """

    cache_lock: asyncio.Lock = dataclasses.field(default_factory=asyncio.Lock)
