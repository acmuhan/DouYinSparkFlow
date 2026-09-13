from pydantic import BaseModel, ConfigDict, Field, field_validator
from utils import norm


class DouyinConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    targets: list[str] = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=2000)
    hitokoto_types: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("targets")
    @classmethod
    def normalize_targets(cls, values: list[str]) -> list[str]:
        result = list(dict.fromkeys(norm(value) for value in values))
        if any(not value or len(value) > 128 for value in result):
            raise ValueError("invalid target")
        return result


def execute(*, cookies, snapshot, checkpoint, on_sent):
    # Browser dependencies are loaded only by the worker invoking this plugin.
    from playwright.sync_api import sync_playwright
    from core.msg_builder import build_message
    from core.runner import DouyinRunner

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            return DouyinRunner().run(
                browser, cookies=cookies, targets=snapshot.plugin_config["targets"],
                message_factory=lambda: build_message(snapshot.plugin_config["message"], snapshot.plugin_config["hitokoto_types"]),
                checkpoint=checkpoint, on_sent=on_sent,
            )
        finally:
            if browser.is_connected():
                browser.close()
