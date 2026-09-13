"use client";

import { FormEvent, useEffect, useState } from "react";
import { Save, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";

type Settings = {
  enabled: boolean; host: string; port: number; security: "STARTTLS" | "SSL";
  username: string; from_email: string; password_configured: boolean;
};

export function SmtpSettings() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [password, setPassword] = useState("");
  const [clearPassword, setClearPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    let active = true;
    apiFetch<Settings>("/admin/settings/smtp").then((value) => { if (active) setSettings(value); })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "SMTP 加载失败"); });
    return () => { active = false; };
  }, []);
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!settings) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const { password_configured: configured, ...payload } = settings;
      void configured;
      const value = await apiFetch<Settings>("/admin/settings/smtp", {
        method: "PUT", body: JSON.stringify({ ...payload, password: clearPassword ? "" : password || null }),
      });
      setSettings(value); setPassword(""); setClearPassword(false); setMessage("SMTP 配置已保存");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "SMTP 保存失败"); }
    finally { setBusy(false); }
  }
  async function test() {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiFetch("/admin/settings/smtp/test", { method: "POST" });
      setMessage("SMTP 已接受测试邮件，请检查当前管理员邮箱");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "测试邮件发送失败"); }
    finally { setBusy(false); }
  }
  const field = "mt-2 h-10 w-full rounded-[5px] border border-[#dcdcd9] bg-white px-3 text-sm";
  return <section className="mt-8 border-t border-[#e7e7e7] py-6">
    <h2 className="text-sm font-semibold">SMTP 发信设置</h2>
    {settings && <form onSubmit={save} className="mt-4 grid gap-4 sm:grid-cols-2">
      <label className="flex items-center gap-2 text-xs sm:col-span-2"><input type="checkbox" disabled={busy}
        checked={settings.enabled} onChange={(event) => setSettings({ ...settings, enabled: event.target.checked })} />启用 SMTP</label>
      <label className="text-xs">SMTP 主机<input required={settings.enabled} disabled={busy} className={field} value={settings.host}
        onChange={(event) => setSettings({ ...settings, host: event.target.value })} /></label>
      <label className="text-xs">端口<input type="number" min={1} max={65535} required disabled={busy} className={field} value={settings.port}
        onChange={(event) => setSettings({ ...settings, port: Number(event.target.value) })} /></label>
      <label className="text-xs">传输加密<select disabled={busy} className={field} value={settings.security}
        onChange={(event) => setSettings({ ...settings, security: event.target.value as Settings["security"] })}><option value="STARTTLS">STARTTLS</option><option value="SSL">TLS / SSL</option></select></label>
      <label className="text-xs">发件人邮箱<input type="email" required={settings.enabled} disabled={busy} className={field} value={settings.from_email}
        onChange={(event) => setSettings({ ...settings, from_email: event.target.value })} /></label>
      <label className="text-xs">用户名<input disabled={busy} autoComplete="off" className={field} value={settings.username}
        onChange={(event) => setSettings({ ...settings, username: event.target.value })} /></label>
      <label className="text-xs">SMTP 密码{settings.password_configured ? "（已配置）" : ""}<input type="password" autoComplete="new-password" disabled={busy || clearPassword} className={field}
        value={password} onChange={(event) => setPassword(event.target.value)} placeholder="留空保留原密码" /></label>
      <label className="flex items-center gap-2 text-xs sm:col-span-2"><input type="checkbox" disabled={busy}
        checked={clearPassword} onChange={(event) => setClearPassword(event.target.checked)} />清除已保存密码</label>
      <div className="flex flex-wrap gap-3 sm:col-span-2"><Button type="submit" disabled={busy}><Save size={14} />保存配置</Button>
        <Button type="button" variant="outline" disabled={busy} onClick={() => void test()}><Send size={14} />使用已保存配置发送测试邮件</Button></div>
    </form>}
    {error && <p role="alert" className="mt-3 text-xs text-red-700">{error}</p>}
    {message && <p role="status" className="mt-3 text-xs text-green-700">{message}</p>}
  </section>;
}
