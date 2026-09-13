"use client";

import { FormEvent, useEffect, useState } from "react";
import { Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";

type GeneralSettings = { registration_enabled: boolean; worker_enabled: boolean; worker_timeout: number };

export function PlatformSettings() {
  const [settings, setSettings] = useState<GeneralSettings | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    let active = true;
    apiFetch<GeneralSettings>("/admin/settings/general")
      .then((value) => { if (active) setSettings(value); })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "加载失败"); });
    return () => { active = false; };
  }, []);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!settings) return;
    setBusy(true); setError(""); setSaved(false);
    try {
      const value = await apiFetch<GeneralSettings>("/admin/settings/general", {
        method: "PUT", body: JSON.stringify(settings),
      });
      setSettings(value); setSaved(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存失败");
    } finally { setBusy(false); }
  }

  return <section className="mt-8 border-t border-[#e7e7e7] py-6">
    <h2 className="text-sm font-semibold">系统设置</h2>
    <form onSubmit={save} className="mt-4 flex flex-wrap items-center gap-4">
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" disabled={!settings || busy}
          checked={settings?.registration_enabled ?? false}
          onChange={(event) => { if (settings) setSettings({ ...settings, registration_enabled: event.target.checked }); setSaved(false); }} />
        开放用户注册
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" disabled={!settings || busy} checked={settings?.worker_enabled ?? false}
          onChange={(event) => { if (settings) setSettings({ ...settings, worker_enabled: event.target.checked }); setSaved(false); }} />
        Worker 领取新任务
      </label>
      <label className="text-sm">任务超时（秒）
        <input type="number" required min={10} max={3600} step={1} disabled={!settings || busy}
          value={settings?.worker_timeout ?? 300} className="ml-3 h-10 w-24 rounded-[5px] border border-[#dcdcd9] px-3 text-sm"
          onChange={(event) => { if (settings) setSettings({ ...settings, worker_timeout: Number(event.target.value) }); setSaved(false); }} />
      </label>
      <Button type="submit" size="sm" disabled={!settings || busy}><Save size={14} />{busy ? "保存中" : "保存"}</Button>
      {saved && <p role="status" className="text-xs text-[#287b42]">已保存</p>}
      {error && <p role="alert" className="text-xs text-[#b43c2d]">{error}</p>}
    </form>
  </section>;
}
