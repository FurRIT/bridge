"""
Bridge to legacy server.
"""

from typing import Sequence
import sys
import os.path
import logging
import asyncio
import argparse
import textwrap

import playwright.async_api

from bridge.config import ConfigParseError, Config, try_load_config
from bridge.event import Event
from bridge.site.auth import i_login, try_load_do_auth
from bridge.site.event import i_extract_event_ids, i_extract_event


async def fetch_events(config: Config) -> Sequence[Event]:
    """
    Fetch Events from `site.host`.
    """
    play = await playwright.async_api.async_playwright().start()
    browser = await play.firefox.launch(headless=True)

    context, page = await try_load_do_auth(
        browser,
        config.site.host,
        config.authcache,
        config.site.username,
        config.site.password,
    )

    logging.info("querying site for event ids")

    raw_uids = await i_extract_event_ids(page, config.site.host)
    uids = frozenset(raw_uids)

    logging.info("found event ids %s", uids)

    events = []
    for uid in uids:
        get_event_resp = await i_extract_event(context, config.site.host, uid)
        if get_event_resp is None:
            logging.warning("encountered error querying details of event id=%s", uid)
            continue

        event = Event.from_raw_event(get_event_resp["data"])
        events.append(event)

    await page.close()

    await context.storage_state(path=config.authcache)
    await context.close()

    await browser.close()
    await play.stop()

    return events


async def run(config: Config) -> None:
    """
    Run Application.
    """
    events = await fetch_events(config)


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
