"use client";

import { FormEvent, useEffect, useState } from "react";
import { Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";

type Settings = {
  enabled: boolean; epay_url: string; epay_version: "V1" | "V2"; epay_pid: string; epay_timestamp_tolerance: number;
  key_configured: boolean; private_key_configured: boolean; public_key_configured: boolean;
};
const secrets = [
  ["epay_key", "V1 商户密钥"], ["epay_private_key", "V2 商户私钥 PEM"], ["epay_public_key", "V2 网关公钥 PEM"],
] as const;

export function PaymentSettings() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [keys, setKeys] = useState({ epay_key: "", epay_private_key: "", epay_public_key: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    let active = true;
    apiFetch<Settings>("/admin/settings/payment").then((value) => { if (active) setSettings(value); })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "支付配置加载失败"); });
    return () => { active = false; };
  }, []);
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!settings) return;
    setBusy(true); setError(""); setSaved(false);
    try {
      const value = await apiFetch<Settings>("/admin/settings/payment", {
        method: "PUT", body: JSON.stringify({
          enabled: settings.enabled, epay_url: settings.epay_url, epay_pid: settings.epay_pid,
          epay_version: settings.epay_version, epay_timestamp_tolerance: settings.epay_timestamp_tolerance,
          epay_key: keys.epay_key || null, epay_private_key: keys.epay_private_key || null, epay_public_key: keys.epay_public_key || null,
        }),
      });
      setSettings(value); setKeys({ epay_key: "", epay_private_key: "", epay_public_key: "" }); setSaved(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "支付配置保存失败"); }
    finally { setBusy(false); }
  }
  const field = "mt-2 h-10 w-full rounded-[5px] border border-[#dcdcd9] bg-white px-3 text-sm";
  return <section className="mt-8 border-t border-[#e7e7e7] py-6">
    <h2 className="text-sm font-semibold">支付设置</h2>
    {settings && <form onSubmit={save} className="mt-4 grid gap-4 sm:grid-cols-2">
      <label className="flex items-center gap-2 text-xs sm:col-span-2"><input type="checkbox" disabled={busy} checked={settings.enabled}
        onChange={(event) => { setSettings({ ...settings, enabled: event.target.checked }); setSaved(false); }} />启用在线支付</label>
      <label className="text-xs">支付网关地址<input type="url" required={settings.enabled} disabled={busy} className={field} value={settings.epay_url}
        placeholder="https://pay.example.com" onChange={(event) => setSettings({ ...settings, epay_url: event.target.value })} /></label>
      <label className="text-xs">商户 ID<input required={settings.enabled} maxLength={64} disabled={busy} className={field} value={settings.epay_pid}
        onChange={(event) => setSettings({ ...settings, epay_pid: event.target.value })} /></label>
      <label className="text-xs">签名版本<select disabled={busy} className={field} value={settings.epay_version} onChange={(event) => setSettings({ ...settings, epay_version: event.target.value as "V1" | "V2" })}>
        <option value="V1">V1 / MD5</option><option value="V2">V2 / RSA-SHA256</option></select></label>
      <label className="text-xs">V2 回调时间容差（秒）<input required type="number" min={30} max={3600} disabled={busy} className={field}
        value={settings.epay_timestamp_tolerance} onChange={(event) => setSettings({ ...settings, epay_timestamp_tolerance: Number(event.target.value) })} /></label>
      {secrets.filter(([id]) => settings.epay_version === "V1" ? id === "epay_key" : id !== "epay_key").map(([id, label]) => <label key={id} className="text-xs sm:col-span-2">
        {label} · {settings[id === "epay_key" ? "key_configured" : id === "epay_private_key" ? "private_key_configured" : "public_key_configured"] ? "已配置" : "未配置"}
        {id === "epay_key" ? <input type="password" autoComplete="new-password" disabled={busy} value={keys[id]} className={field} placeholder="留空保留原密钥"
          onChange={(event) => setKeys({ ...keys, [id]: event.target.value })} /> :
          <textarea autoComplete="off" spellCheck={false} rows={4} disabled={busy} value={keys[id]} className="mt-2 w-full rounded-[5px] border border-[#dcdcd9] p-3 font-mono text-xs"
            placeholder="留空保留原密钥" onChange={(event) => setKeys({ ...keys, [id]: event.target.value })} />}
      </label>)}
      <div className="sm:col-span-2"><Button disabled={busy} type="submit"><Save size={14} />保存支付配置</Button></div>
    </form>}
    {error && <p role="alert" className="mt-3 text-xs text-red-700">{error}</p>}
    {saved && <p role="status" className="mt-3 text-xs text-green-700">支付配置已保存，旧订单保留原验签配置。</p>}
  </section>;
}
