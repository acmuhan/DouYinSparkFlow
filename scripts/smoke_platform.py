"""Local-only integration smoke test, with isolated SQLite and real HTTP/UI."""

import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import time

import httpx
from playwright.sync_api import sync_playwright, expect


ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_ready(url, process):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited with code {process.returncode}")
        try:
            if httpx.get(url, timeout=3).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError("Local server startup timed out")


def stop(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=30)
    else:
        process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=15)


def main():
    runtime = ROOT / ".runtime" / f"smoke-{secrets.token_hex(4)}"
    runtime.mkdir(parents=True)
    api_port, web_port = free_port(), free_port()
    api = f"http://127.0.0.1:{api_port}"
    web = f"http://127.0.0.1:{web_port}"
    password = secrets.token_urlsafe(24)
    env = {
        **os.environ, "DATABASE_URL": f"sqlite:///{(runtime / 'smoke.db').as_posix()}",
        "AUTO_CREATE_TABLES": "true", "ENVIRONMENT": "development", "WORKER_ENABLED": "false",
        "ADMIN_EMAIL": "smoke-admin@example.test", "ADMIN_PASSWORD": password,
        "ADMIN_NAME": "Smoke Admin", "APP_URL": web, "WEB_ORIGIN": web,
        "ENCRYPTION_KEY": secrets.token_urlsafe(32), "BACKEND_URL": api,
        "NEXT_PUBLIC_API_URL": "/api/backend", "REGISTRATION_ENABLED": "true",
        "EPAY_URL": "", "EPAY_PID": "", "EPAY_KEY": "",
    }
    servers = []
    logs = []
    checks = []
    try:
        for name, command in [
            ("api", [sys.executable, "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", str(api_port)]),
            ("web", [shutil.which("node") or "node", "node_modules/next/dist/bin/next", "dev", "--hostname", "127.0.0.1", "--port", str(web_port)]),
        ]:
            log = (runtime / f"{name}.log").open("w", encoding="utf-8")
            logs.append(log)
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            servers.append(process)
        wait_ready(f"{api}/api/v1/health", servers[0])
        wait_ready(web, servers[1])
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 1000}, timezone_id="Asia/Shanghai")
            errors = []
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            login = context.request.post(f"{web}/api/backend/auth/login", data={
                "email": env["ADMIN_EMAIL"], "password": password,
            })
            assert login.status == 200, login.text()
            page.goto(web)
            expect(page.get_by_role("button", name="管理控制台", exact=True)).to_be_visible()
            checks.append("same-origin login cookie persists")
            page.get_by_role("button", name="管理控制台", exact=True).click()
            page.get_by_role("tab", name="系统设置", exact=True).click()
            settings = page.locator("section").filter(has=page.get_by_role("heading", name="系统设置", exact=True))
            expect(settings.get_by_label("开放用户注册")).to_be_enabled()
            expect(settings.get_by_label("开放用户注册")).to_be_checked()
            settings.get_by_label("开放用户注册").uncheck()
            expect(settings.get_by_label("开放用户注册")).not_to_be_checked()
            with page.expect_request(lambda request: request.method == "PUT" and request.url.endswith("/settings/general")) as saved_request:
                settings.get_by_role("button", name="保存", exact=True).click()
            assert saved_request.value.post_data_json["registration_enabled"] is False, saved_request.value.post_data_json
            expect(settings.get_by_role("status")).to_have_text("已保存")
            blocked = context.request.post(f"{web}/api/backend/auth/register", data={
                "email": "blocked@example.test", "name": "Blocked", "password": password,
            })
            assert blocked.status == 403, {
                "status": blocked.status, "settings": context.request.get(f"{web}/api/backend/admin/settings/general").json(),
            }
            checks.append("database registration switch rejects actual HTTP signup")
            page.get_by_role("tab", name="业务管理", exact=True).click()
            page.get_by_role("button", name="套餐配置", exact=True).click()
            page.get_by_role("button", name="新增套餐", exact=True).click()
            form = page.get_by_role("heading", name="新增套餐", exact=True).locator("..")
            form.get_by_label("套餐 ID", exact=True).fill("ui-custom")
            form.get_by_label("套餐标识", exact=True).fill("ui-custom")
            form.get_by_label("名称", exact=True).fill("UI Custom")
            form.get_by_label("抖音续火花", exact=True).check()
            form.get_by_label("创建和编辑任务", exact=True).check()
            form.get_by_role("button", name="保存", exact=True).click()
            expect(page.get_by_role("heading", name="UI Custom", exact=True)).to_be_visible()
            plans = context.request.get(f"{web}/api/backend/admin/plans").json()
            plan = next(item for item in plans if item["id"] == "ui-custom")
            assert plan["permissions"] == ["tasks.create"]
            assert plan["plugin_permissions"] == ["douyin_streak"]
            checks.append("custom plan and permission checkboxes persist")
            page.screenshot(path=str(runtime / "plans-desktop.png"))
            page.get_by_role("button", name="返回管理控制台", exact=True).click()
            page.get_by_role("tab", name="账户管理", exact=True).click()
            page.get_by_role("button", name="新增用户", exact=True).click()
            dialog = page.get_by_role("dialog")
            dialog.get_by_label("名称", exact=True).fill("UI User")
            dialog.get_by_label("邮箱", exact=True).fill("ui-user@example.test")
            dialog.get_by_label("初始密码", exact=True).fill(password)
            dialog.get_by_role("button", name="保存", exact=True).click()
            expect(dialog).not_to_be_visible()
            directory = page.locator("section").filter(has=page.get_by_role("heading", name="用户账户管理", exact=True))
            expect(directory.get_by_text("ui-user@example.test", exact=True)).to_be_visible()
            checks.append("create user through dialog")
            user_context = browser.new_context()
            login = user_context.request.post(f"{web}/api/backend/auth/login", data={
                "email": "ui-user@example.test", "password": password,
            })
            assert login.status == 200, login.text()
            user_id = login.json()["id"]
            permitted = context.request.patch(f"{web}/api/backend/admin/plans/ui-custom", data={
                **plan, "permissions": ["accounts.create", "accounts.validate", "tasks.create", "tasks.manual"],
            })
            assert permitted.status == 200, permitted.text()
            subscription = context.request.patch(f"{web}/api/backend/admin/users/{user_id}/subscription", data={
                "plan_id": "ui-custom", "months": 1, "reason": "Isolated local smoke test",
            })
            assert subscription.status == 200, subscription.text()
            user_page = user_context.new_page()
            user_page.on("pageerror", lambda error: errors.append(str(error)))
            user_page.goto(web)
            user_page.get_by_role("button", name="抖音资源", exact=True).click()
            user_page.get_by_role("button", name="添加资源", exact=True).click()
            user_page.get_by_label("资源名称", exact=True).fill("Synthetic Resource")
            user_page.get_by_label("抖音号", exact=True).fill("synthetic-user")
            user_page.get_by_label("Cookie JSON", exact=True).fill(json.dumps([
                {"name": "sessionid", "value": "synthetic-not-a-real-cookie", "domain": ".douyin.com", "path": "/"},
            ]))
            with user_page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith("/accounts")) as resource_response:
                user_page.get_by_role("button", name="保存并验证", exact=True).click()
            resource = resource_response.value.json()
            assert resource["status"] == "UNVERIFIED" and resource["inspection_status"] == "QUEUED"
            checks.append("resource UI stores synthetic cookie and queues asynchronous verification")
            # Provider data is synthetic: no browser worker or Douyin request is made.
            with sqlite3.connect(runtime / "smoke.db") as db:
                db.execute(
                    "UPDATE accounts SET status=?, inspection_status=?, friends=? WHERE id=?",
                    ("READY", "SUCCEEDED", json.dumps([{"id": "synthetic-friend", "name": "Synthetic Friend", "unique_id": "synthetic-friend"}]), resource["id"]),
                )
            user_page.get_by_role("button", name="任务中心", exact=True).click()
            user_page.get_by_role("button", name="新建任务", exact=True).click()
            user_page.get_by_label("任务名称", exact=True).fill("Local Task")
            user_page.get_by_label("执行资源", exact=True).select_option(resource["id"])
            user_page.get_by_role("checkbox", name="Synthetic Friend", exact=False).check()
            user_page.get_by_role("button", name="创建任务", exact=True).click()
            expect(user_page.get_by_text("Local Task", exact=True)).to_be_visible()
            with user_page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith("/run")) as queued_response:
                user_page.get_by_role("button", name="运行", exact=True).click()
            queued = queued_response.value.json()
            assert queued["status"] == "QUEUED", queued
            user_page.get_by_role("button", name=f"查看运行 {queued['id']} 日志", exact=True).click()
            details = user_page.get_by_role("dialog")
            expect(details.get_by_text("任务已进入执行队列", exact=True)).to_be_visible()
            cancelled = user_context.request.post(f"{web}/api/backend/runs/{queued['id']}/cancel")
            assert cancelled.status == 200, cancelled.text()
            expect(details.get_by_text("任务已取消，已提交的消息无法撤回", exact=True)).to_be_visible(timeout=10000)
            assert context.request.get(f"{web}/api/backend/runs/{queued['id']}/events").status == 404
            user_page.screenshot(path=str(runtime / "run-events-desktop.png"))
            user_page.set_viewport_size({"width": 390, "height": 844})
            user_page.screenshot(path=str(runtime / "run-events-mobile.png"))
            assert user_page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
            checks.append("synthetic API friend selection creates task; queued/cancelled logs poll in user drawer and reject another tenant")
            user_page.close()
            directory.get_by_role("button", name="编辑 ui-user@example.test", exact=True).click()
            dialog.get_by_label("邮箱", exact=True).fill("rebound@example.test")
            dialog.get_by_role("button", name="保存", exact=True).click()
            expect(dialog).not_to_be_visible()
            expect(directory.get_by_text("rebound@example.test", exact=True)).to_be_visible()
            assert user_context.request.get(f"{web}/api/backend/me").status == 401
            checks.append("email rebind through dialog revokes existing user session")
            directory.get_by_role("button", name="编辑 rebound@example.test", exact=True).click()
            dialog.get_by_role("button", name="删除用户", exact=True).click()
            dialog.get_by_role("button", name="确认删除", exact=True).click()
            expect(dialog).not_to_be_visible()
            expect(directory.get_by_text("rebound@example.test", exact=True)).not_to_be_visible()
            denied = user_context.request.post(f"{web}/api/backend/auth/login", data={
                "email": "rebound@example.test", "password": password,
            })
            assert denied.status == 401, denied.text()
            user_context.close()
            checks.append("delete user through confirmation prevents subsequent login")
            page.get_by_role("tab", name="公告管理", exact=True).click()
            announcements = page.locator("section").filter(has=page.get_by_role("heading", name="公告管理", exact=True))
            announcements.get_by_label("标题", exact=True).fill("Local Smoke Announcement")
            announcements.get_by_label("正文", exact=True).fill("Local-only integration test announcement.")
            announcements.get_by_role("button", name="创建公告", exact=True).click()
            expect(announcements.get_by_text("Local Smoke Announcement", exact=True)).to_be_visible()
            page.get_by_role("button", name="通知，", exact=False).click()
            notifications = page.get_by_role("dialog")
            expect(notifications.get_by_role("heading", name="Local Smoke Announcement")).to_be_visible()
            published = context.request.get(f"{web}/api/backend/notifications/announcements").json()[0]
            local_time = page.evaluate("(utc) => new Date(utc + 'Z').toLocaleString('zh-CN')", published["created_at"])
            expect(notifications.locator("time")).to_have_text(local_time)
            notifications.get_by_role("button", name="标记已读", exact=True).click()
            expect(notifications.get_by_text("已读", exact=True)).to_be_visible()
            page.screenshot(path=str(runtime / "notifications-desktop.png"))
            notifications.get_by_role("button", name="关闭通知", exact=True).click()
            checks.append("publish announcement and persist read state")
            page.get_by_role("button", name="抖音资源", exact=True).click()
            expect(page.get_by_role("heading", name="抖音插件资源")).to_be_visible()
            page.screenshot(path=str(runtime / "resources-desktop.png"))
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(runtime / "resources-mobile.png"))
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
            page.get_by_role("button", name="打开菜单", exact=True).click()
            page.get_by_role("button", name="任务中心", exact=True).click()
            expect(page.get_by_role("heading", name="任务中心", exact=True, level=2)).to_be_visible()
            page.screenshot(path=str(runtime / "tasks-mobile.png"))
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
            checks.append("mobile navigation and no page-level horizontal overflow")
            assert not errors, errors
            checks.append("no browser page errors")
            context.close()
            browser.close()
        (runtime / "result.json").write_text(json.dumps({"checks": checks, "database": "isolated SQLite"}, indent=2), encoding="utf-8")
        print(json.dumps({"passed": checks, "artifacts": str(runtime)}, ensure_ascii=True))
    finally:
        for process in reversed(servers):
            stop(process)
        for log in logs:
            log.close()
        print(f"Local test artifacts: {runtime}")


if __name__ == "__main__":
    main()
