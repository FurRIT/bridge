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

from bridge.config import ConfigParseError, try_load_config


async def run() -> None:
    """
    Run Application.
    """
    play = await playwright.async_api.async_playwright().start()

    browser = await play.firefox.launch(headless=False)
    page = await browser.new_page()

    await page.goto("https://playwright.dev")

    await asyncio.sleep(30)
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

    # asyncio.run(run())
