"""
Bridge to legacy server.
"""

from typing import Sequence
import sys
import json
import os.path
import hashlib
import logging
import asyncio
import argparse
import textwrap

import playwright.async_api

from bridge.config import ConfigParseError, Config, try_load_config
from bridge.event import Event
from bridge.site.auth import try_load_do_auth
from bridge.site.event import i_extract_event_ids, i_extract_event

logging.basicConfig(level=logging.INFO)


async def fetch_events(config: Config) -> Sequence[Event]:
    """
    Fetch Events from `site.host`.
    """
    play = await playwright.async_api.async_playwright().start()
    browser = await play.firefox.launch(headless=True)

    logging.info("performing authentication with %s", config.site.host)
    context, page = await try_load_do_auth(
        browser,
        config.site.host,
        config.authcache,
        config.site.username,
        config.site.password,
    )

    logging.info("querying %s for event ids", config.site.host)

    raw_uids = await i_extract_event_ids(page, config.site.host)
    uids = frozenset(raw_uids)

    logging.info("found event ids [%s]", ", ".join(iter(uids)))

    events = []
    for uid in uids:
        logging.info("querying details of event id=%s", uid)
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


def _hash_event(event: Event) -> bytes:
    """
    Hacky workaround to avoid implementing a __hash__ method for an Event.

    Assumption: equivalent Events will produce the same json.dumps output; so
    we hash the json.dumps output to get a unique hash.
    """
    se_dict = event.to_dict()
    se_str = json.dumps(se_dict)

    se_bytes = se_str.encode("utf-8")
    hasher = hashlib.blake2b(se_bytes)

    return hasher.digest()


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
