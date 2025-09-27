"""
Bridge to legacy server.
"""

from typing import NamedTuple
import sys
import base64
import os.path
import logging
import asyncio
import argparse
import textwrap

import aiohttp
import playwright.async_api
import apscheduler.triggers.interval  # type: ignore
import apscheduler.schedulers.asyncio  # type: ignore

from bridge.config import ConfigParseError, Config, try_load_config
from bridge.cache import CacheEntry, load_cache, write_cache
from bridge.event import Event, hash_event
from bridge.types import AppContext, PlayPersist
from bridge.server import routes
from bridge.client import push_event_to_clients
from bridge.site.auth import try_load_do_auth
from bridge.site.event import i_fetch_extract_events

logging.basicConfig(level=logging.INFO)


class _PartialCacheEntry(NamedTuple):
    """
    Partial Cache Entry; for indexing by uid.
    """

    hash: str
    rev_id: int


async def fetch_push_events(ctx: AppContext, config: Config) -> None:
    """
    Run fetch_events then push_event for each one.

    Updates the Cache with seen events.
    """

    await ctx.cache_lock.acquire()
    await try_load_do_auth(
        config.site.host,
        config.authcache,
        config.site.username,
        config.site.password,
        context=ctx.persist.context,
        page=ctx.persist.page,
    )
    await ctx.persist.context.storage_state(path=config.authcache)
    raw_events = await i_fetch_extract_events(
        ctx.persist.context, ctx.persist.page, config.site.host
    )

    events = list(map(Event.from_raw_event, raw_events))

    hashes: list[str] = list(
        map(
            lambda bytes: bytes.decode("utf-8"),
            map(base64.b64encode, map(hash_event, events)),
        )
    )

    entries = load_cache(config.cache)
    entry_uid_to_partial: dict[str, _PartialCacheEntry] = dict(
        map(
            lambda entry: (
                entry.uid,
                _PartialCacheEntry(entry.hash, entry.rev_id),
            ),
            entries,
        )
    )

    to_push: list[int] = []

    for i, event in enumerate(events):
        if event.uid in entry_uid_to_partial:
            entry_hash = entry_uid_to_partial[event.uid].hash

            if entry_hash == hashes[i]:
                continue

        to_push.append(i)

    for idx in to_push:
        event = events[idx]

        logging.info("pushing event id=%s to clients", event.uid)
        await push_event_to_clients(config, event)

    updated_event_uids = frozenset(
        map(lambda event: event.uid, map(lambda i: events[i], to_push))
    )

    def _derive_entry(i: int) -> CacheEntry:
        """
        Derive a CacheEntry from an Event.

        If the Event is new create a new CacheEntry with rev_id = 0;
        Otherwise, make an entry with a incremented rev_id.
        """
        event = events[i]
        ehash = hashes[i]

        if event.uid not in entry_uid_to_partial:
            return CacheEntry(event.uid, ehash, 0)

        existing = entry_uid_to_partial[event.uid]
        return CacheEntry(event.uid, ehash, existing.rev_id + 1)

    n_entries: list[CacheEntry] = []
    n_entries.extend(filter(lambda entry: entry.uid not in updated_event_uids, entries))
    n_entries.extend(map(_derive_entry, to_push))

    write_cache(config.cache, n_entries)
    ctx.cache_lock.release()


async def run(config: Config) -> None:
    """
    Run Application.
    """
    play = await playwright.async_api.async_playwright().start()
    browser = await play.firefox.launch(headless=True)

    context, page = await try_load_do_auth(
        config.site.host,
        config.authcache,
        config.site.username,
        config.site.password,
        browser=browser,
    )

    persist = PlayPersist(play, browser, context, page)
    ctx = AppContext(config, persist)

    scheduler = apscheduler.schedulers.asyncio.AsyncIOScheduler()

    scheduler.add_job(
        fetch_push_events,
        apscheduler.triggers.interval.IntervalTrigger(seconds=config.frequency),
        args=[ctx, config],
    )

    scheduler.start()

    app = aiohttp.web.Application()
    app.add_routes(routes)

    app["ctx"] = ctx
    runner = aiohttp.web.AppRunner(app)

    await runner.setup()

    site = aiohttp.web.TCPSite(runner, config.api.host, config.api.port)
    await site.start()

    await asyncio.Future()


def _error(msg: str) -> None:
    print(
        "\n".join(textwrap.wrap(f"error: {msg}", subsequent_indent="       ")),
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    """
    Parse Arguments & Run Main.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        default="config.toml",
        help="path to config (default %(default)s)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.config):
        _error(f"config file {args.config} does not exist or is not a file")

    try:
        config = try_load_config(args.config)
    except ConfigParseError as error:
        _error(f"error: occured during config parsing; {error.reason}")

    asyncio.run(run(config))
