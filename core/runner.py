from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from utils import norm

CONVERSATION_ITEM_SELECTOR = ".conversationConversationItemwrapper"
CONVERSATION_TITLE_SELECTOR = ".conversationConversationItemtitle"
CONVERSATION_LIST_SELECTOR = ".conversationConversationListwrapper"
CHAT_EDITOR_SELECTOR = ".messageEditorimChatEditorContainer"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeliveryResult:
    # Submitted to the browser UI, not a provider delivery/read receipt.
    sent_count: int
    missing_count: int


class DouyinRunner:
    def __init__(self, *, timeout_ms: int = 30_000):
        self.timeout_ms = timeout_ms
        self.identities: dict[str, set[str]] = {}

    def _handle_response(self, response) -> None:
        if "aweme/v1/web/im/user/info" not in response.url:
            return
        try:
            for item in response.json().get("data", []):
                nickname = norm(str(item.get("nickname") or ""))
                remark = norm(str(item.get("remark_name") or nickname))
                aliases = {
                    norm(str(item[key]))
                    for key in ("short_id", "unique_id", "sec_uid", "nickname", "remark_name")
                    if item.get(key)
                }
                for label in (nickname, remark):
                    if label:
                        self.identities.setdefault(label, set()).update(aliases)
        except (ValueError, TypeError, AttributeError):
            logger.warning("Ignored malformed conversation metadata")

    def _select_targets(self, page, targets: list[str], checkpoint: Callable[[], None]) -> Iterator[str]:
        seen: set[str] = set()
        remaining = set(targets)
        empty_scrolls = 0
        while remaining and empty_scrolls < 10:
            checkpoint()
            before = len(seen)
            for element in page.locator(CONVERSATION_ITEM_SELECTOR).all():
                checkpoint()
                label = norm(element.locator(CONVERSATION_TITLE_SELECTOR).inner_text())
                if label in seen:
                    continue
                seen.add(label)
                aliases = self.identities.get(label, set()) | {label}
                match = next((target for target in targets if target in remaining and target in aliases), None)
                if match:
                    element.click()
                    yield match
                    remaining.remove(match)
                    if not remaining:
                        return
            empty_scrolls = empty_scrolls + 1 if len(seen) == before else 0
            container = page.locator(CONVERSATION_LIST_SELECTOR).element_handle()
            if container is None:
                return
            previous = page.evaluate("(element) => element.scrollTop", container)
            page.evaluate("(element) => element.scrollTop += 800", container)
            page.wait_for_timeout(1500)
            if page.evaluate("(element) => element.scrollTop", container) == previous:
                empty_scrolls += 2

    def run(
        self, browser, *, cookies: list[dict], targets: list[str],
        message_factory: Callable[[], str],
        checkpoint: Callable[[], None] = lambda: None,
        on_sent: Callable[[int], None] = lambda count: None,
    ) -> DeliveryResult:
        self.identities.clear()
        targets = list(dict.fromkeys(norm(target) for target in targets))
        sent = 0
        checkpoint()
        context = browser.new_context()
        try:
            context.set_default_navigation_timeout(self.timeout_ms)
            context.set_default_timeout(self.timeout_ms)
            context.add_cookies(cookies)
            page = context.new_page()
            page.on("response", self._handle_response)
            page.goto("https://www.douyin.com/chat", wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            for _ in self._select_targets(page, targets, checkpoint):
                checkpoint()
                page.wait_for_selector(CHAT_EDITOR_SELECTOR)
                editor = page.locator(CHAT_EDITOR_SELECTOR)
                message = message_factory()
                if not message.strip():
                    raise ValueError("message is empty")
                # Clear stale drafts. Never retry Enter after an uncertain send.
                editor.fill("")
                lines = message.replace("\\n", "\n").split("\n")
                for index, line in enumerate(lines):
                    checkpoint()
                    editor.type(line)
                    if index < len(lines) - 1:
                        editor.press("Shift+Enter")
                checkpoint()
                editor.press("Enter")
                sent += 1
                on_sent(sent)
                page.wait_for_timeout(2000)
            return DeliveryResult(sent_count=sent, missing_count=len(targets) - sent)
        finally:
            context.close()
            self.identities.clear()
