"""
Bridge to legacy server.
"""

import sys
import os.path
import logging
import asyncio
import argparse
import textwrap

import playwright.async_api

from bridge.config import ConfigParseError, Config, try_load_config
from bridge.site.auth import i_login, try_load_do_auth
from bridge.site.event import i_extract_event_ids, i_extract_event


async def run(config: Config) -> None:
    """
    Run Application.
    """
    play = await playwright.async_api.async_playwright().start()

    browser = await play.firefox.launch(headless=False)
    context, page = await try_load_do_auth(
        browser,
        config.site.host,
        config.cache,
        config.site.username,
        config.site.password,
    )

    head, *_ = await i_extract_event_ids(page, config.site.host)
    await i_extract_event(context, config.site.host, head)

    await page.close()

    await context.storage_state(path=config.cache)
    await context.close()

    await browser.close()


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
