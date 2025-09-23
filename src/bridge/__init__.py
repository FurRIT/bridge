"""
Bridge to legacy server.
"""

import asyncio

import playwright.async_api


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


def main() -> None:
    """
    Parse Arguments & Run Main.
    """
    asyncio.run(run())
