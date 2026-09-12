"""Legacy CLI entry points backed by the same isolated runner as the API."""

from core.runner import (
    CHAT_EDITOR_SELECTOR,
    CONVERSATION_ITEM_SELECTOR,
    CONVERSATION_LIST_SELECTOR,
    CONVERSATION_TITLE_SELECTOR,
    DeliveryResult,
    DouyinRunner,
)


def do_user_task(browser, username, cookies, targets) -> DeliveryResult:
    from core.msg_builder import build_message
    from utils.config import get_config

    runner = DouyinRunner(timeout_ms=get_config()["browserTimeout"])
    return runner.run(browser, cookies=cookies, targets=targets, message_factory=build_message)


def runTasks():
    from core.browser import get_browser
    from utils.config import get_config, get_userData
    from utils.logger import setup_logger

    logger = setup_logger(level=get_config().get("logLevel", "Info"))
    playwright, browser = get_browser()
    try:
        for user in get_userData():
            result = do_user_task(browser, user["username"], user["cookies"], user["targets"])
            logger.info("Task completed: %s submitted, %s not found", result.sent_count, result.missing_count)
    finally:
        browser.close()
        playwright.stop()
