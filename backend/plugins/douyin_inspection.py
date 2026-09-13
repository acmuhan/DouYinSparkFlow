from dataclasses import dataclass, field
from urllib.parse import urlparse

from utils import norm


@dataclass
class InspectionResult:
    status: str
    message: str
    friends: list[dict] = field(default_factory=list)


def parse_friends(payload: dict) -> list[dict]:
    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError("unexpected friend response")
    friends = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        identifier = item.get("sec_uid") or item.get("unique_id") or item.get("short_id")
        if not isinstance(identifier, (str, int)) or not str(identifier):
            continue
        target = norm(str(identifier))
        if len(target) > 128:
            continue
        friends[target] = {
            "id": target, "name": norm(str(item.get("remark_name") or item.get("nickname") or target))[:128],
            "unique_id": str(item.get("unique_id") or "")[:128],
        }
    return list(friends.values())


def inspect_cookies(cookies: list[dict]) -> InspectionResult:
    from playwright.sync_api import Error, TimeoutError, sync_playwright
    from core.runner import CONVERSATION_LIST_SELECTOR

    friends: dict[str, dict] = {}
    observed = False
    rejected = False
    malformed = False

    def response_received(response):
        nonlocal observed, rejected, malformed
        url = urlparse(response.url)
        if url.hostname != "www.douyin.com" or "/aweme/v1/web/im/user/info" not in url.path:
            return
        if response.status in (401, 403):
            rejected = True
            return
        if response.status != 200:
            return
        try:
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("status_code", 0) != 0:
                malformed = True
                return
            rows = parse_friends(payload)
            observed = True
            for item in rows:
                if len(friends) < 1000:
                    friends[item["id"]] = item
        except (ValueError, TypeError, Error):
            malformed = True

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                context.add_cookies(cookies)
                page = context.new_page()
                page.set_default_timeout(15000)
                page.on("response", response_received)
                page.goto("https://www.douyin.com/chat", wait_until="domcontentloaded", timeout=30000)
                for _ in range(8):
                    page.wait_for_timeout(1000)
                    container = page.locator(CONVERSATION_LIST_SELECTOR).first
                    if container.count():
                        container.evaluate("(element) => { element.scrollTop += 800; }")
                if rejected:
                    return InspectionResult("UNVERIFIED", "接口拒绝访问，可能需要重新登录或完成平台验证")
                if malformed:
                    return InspectionResult("UNVERIFIED", "好友接口响应不兼容，请更新适配器后重试")
                # A rendered chat shell alone is not proof of authenticated access.
                if observed and friends:
                    return InspectionResult("READY", "聊天接口可访问，已同步当前加载的好友", list(friends.values()))
                return InspectionResult("UNVERIFIED", "未获取到可验证的好友数据，请检查登录状态；空好友列表不能证明 Cookie 有效")
            finally:
                if browser.is_connected():
                    browser.close()
    except TimeoutError:
        return InspectionResult("UNVERIFIED", "检测超时，请检查网络后重试")
    except Error:
        return InspectionResult("UNVERIFIED", "浏览器检测失败，请检查 Worker 浏览器环境")
