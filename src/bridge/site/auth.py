"""
Authorization Functionality.
"""

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
