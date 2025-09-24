"""
Authorization Functionality.
"""

import os.path
import playwright.async_api


_LOGIN_BUTTON_CSS_PATH = "html body main form div.flex-container.flex-justifyContent-center input.button.button-primary"


async def i_login(
    page: playwright.async_api.Page, host: str, username: str, password: str
) -> None:
    """
    Interact with a Browser context to login.
    """

    await page.goto(f"https://{host}/login")

    await page.get_by_placeholder("FurRIT Username").fill(username)
    await page.get_by_placeholder("Password").fill(password)
    await page.locator(_LOGIN_BUTTON_CSS_PATH).click()


async def check_auth(page: playwright.async_api.Page, host: str) -> bool:
    """
    Use the Page to check whether or not the Context a Page belongs to is
    authorized.
    """

    await page.goto(f"https://{host}/events")
    return not page.url.endswith("/login")


async def try_load_do_auth(
    browser: playwright.async_api.Browser,
    host: str,
    cache: str,
    username: str,
    password: str,
) -> tuple[playwright.async_api.BrowserContext, playwright.async_api.Page]:
    """
    Try to load authorization credentials from disk and create a new
    (BrowserContext, Page) with them.

    Create a new (BrowserContext, Page) if the credentials don't work.
    """
    fresh = not os.path.isfile(cache)

    context = await browser.new_context(storage_state=(cache if not fresh else None))
    page = await context.new_page()

    if fresh:
        await i_login(page, host, username, password)
        return (context, page)

    works = await check_auth(page, host)
    if works:
        return (context, page)

    await i_login(page, host, username, password)
    return (context, page)
