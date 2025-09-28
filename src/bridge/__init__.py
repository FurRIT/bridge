"""
Bridge to legacy server.
"""

from typing import NamedTuple
import sys
import os.path
import logging
import asyncio
import argparse
import textwrap
import itertools

import aiohttp
import playwright.async_api
import apscheduler.triggers.interval  # type: ignore
import apscheduler.schedulers.asyncio  # type: ignore

from bridge.config import ConfigParseError, Config, try_load_config
from bridge.cache import (
    load_sort_events,
    update_cache,
)
from bridge.event import Event
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

    async with ctx.play_lock:
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

    async with ctx.cache_lock:
        sort = load_sort_events(config.cache, events)
        to_push = itertools.chain(sort.new, sort.updated)

        for idx in to_push:
            event = events[idx]

            logging.info("pushing event id=%s to clients", event.uid)
            await push_event_to_clients(config, event)

        update_cache(config.cache, events, sort=sort)


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
