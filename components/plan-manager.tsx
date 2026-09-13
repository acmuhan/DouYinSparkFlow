"use client";

import { FormEvent, useEffect, useState } from "react";
import { ArrowLeft, Plus, Save, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Plan, apiFetch } from "@/lib/api";

type Plugin = { id: string; name: string };
type Permission = { id: string; name: string; legacy: boolean };
const limits = [
  ["monthly_cents", "月付（分）"], ["quarterly_cents", "季付（分）"], ["yearly_cents", "年付（分）"],
  ["account_limit", "账号上限"], ["task_limit", "任务上限"], ["run_limit", "月运行额度"],
] as const;
const empty: Plan = {
  id: "", slug: "", name: "", description: "", monthly_cents: 100, quarterly_cents: 300, yearly_cents: 1200,
  account_limit: 1, task_limit: 1, run_limit: 100, features: [], plugin_permissions: [], permissions: [], active: true, sort_order: 0,
};

function PlanEditor({ plan, plugins, permissions, onChanged }: { plan?: Plan; plugins: Plugin[]; permissions: Permission[]; onChanged: () => Promise<void> }) {
  const [draft, setDraft] = useState<Plan>(plan ? {
    ...plan, plugin_permissions: plan.plugin_permissions ?? ["douyin_streak"],
    permissions: plan.permissions ?? permissions.filter((permission) => permission.legacy).map((permission) => permission.id),
  } : empty);
  const [features, setFeatures] = useState(plan?.features.join("\n") ?? "");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const field = "mt-2 h-10 w-full rounded-[5px] border border-[#dcdcd9] bg-white px-3 text-sm";
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      const { id, ...values } = draft;
      await apiFetch(plan ? `/admin/plans/${plan.id}` : "/admin/plans", {
        method: plan ? "PATCH" : "POST",
        body: JSON.stringify({ ...values, ...(!plan ? { id: id || null } : {}), features: features.split("\n").map((item) => item.trim()).filter(Boolean) }),
      });
      if (!plan) { setDraft(empty); setFeatures(""); }
      await onChanged(); setMessage("套餐已保存");
    } catch (reason) { setMessage(reason instanceof Error ? reason.message : "保存失败"); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!plan || !window.confirm(`删除套餐“${plan.name}”？已有订阅或订单的套餐将仅下架。`)) return;
    setBusy(true); setMessage("");
    try { await apiFetch(`/admin/plans/${plan.id}`, { method: "DELETE" }); await onChanged(); setMessage("已删除或下架"); }
    catch (reason) { setMessage(reason instanceof Error ? reason.message : "删除失败"); }
    finally { setBusy(false); }
  }
  return <form onSubmit={save} className="grid gap-4 border-b border-[#e7e7e7] py-6 sm:grid-cols-2 lg:grid-cols-3">
    <h3 className="text-sm font-semibold sm:col-span-2 lg:col-span-3">{plan ? plan.name : "新增套餐"}</h3>
    <label className="text-xs">套餐 ID<input disabled={busy || !!plan} maxLength={36} pattern="[A-Za-z0-9_-]+" placeholder="留空自动生成"
      value={draft.id} className={field} onChange={(event) => setDraft({ ...draft, id: event.target.value })} /></label>
    <label className="text-xs">套餐标识<input required disabled={busy} maxLength={40} pattern="[a-z0-9][a-z0-9_-]*"
      value={draft.slug} className={field} onChange={(event) => setDraft({ ...draft, slug: event.target.value })} /></label>
    <label className="text-xs">名称<input required disabled={busy} maxLength={80} value={draft.name} className={field} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
    <label className="text-xs sm:col-span-2 lg:col-span-3">说明<input disabled={busy} maxLength={255} value={draft.description} className={field} onChange={(event) => setDraft({ ...draft, description: event.target.value })} /></label>
    {limits.map(([key, label]) => <label key={key} className="text-xs">{label}<input type="number" required min={1} step={1} disabled={busy}
      value={draft[key]} className={field} onChange={(event) => setDraft({ ...draft, [key]: Number(event.target.value) })} /></label>)}
    <label className="text-xs">排序<input required type="number" min={0} step={1} disabled={busy} value={draft.sort_order} className={field}
      onChange={(event) => setDraft({ ...draft, sort_order: Number(event.target.value) })} /></label>
    <label className="text-xs sm:col-span-2">展示权益<textarea disabled={busy} value={features}
      className="mt-2 min-h-20 w-full rounded-[5px] border border-[#dcdcd9] p-3 text-sm" onChange={(event) => setFeatures(event.target.value)} /></label>
    <fieldset className="sm:col-span-2 lg:col-span-3"><legend className="mb-3 text-xs font-semibold">插件执行权限</legend>
      {plugins.map((plugin) => <label key={plugin.id} className="mr-5 inline-flex items-center gap-2 text-sm">
        <input type="checkbox" disabled={busy} checked={draft.plugin_permissions?.includes(plugin.id) ?? false} onChange={(event) => {
          setDraft({ ...draft, plugin_permissions: event.target.checked ? [...(draft.plugin_permissions ?? []), plugin.id] : draft.plugin_permissions?.filter((id) => id !== plugin.id) ?? [] });
        }} />{plugin.name}</label>)}
    </fieldset>
    <fieldset className="sm:col-span-2 lg:col-span-3"><legend className="mb-3 text-xs font-semibold">平台操作权限</legend>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{permissions.map((permission) => <label key={permission.id} className="flex items-start gap-2 text-sm">
        <input type="checkbox" className="mt-1" disabled={busy} checked={draft.permissions?.includes(permission.id) ?? false}
          onChange={(event) => setDraft({ ...draft, permissions: event.target.checked ?
            [...(draft.permissions ?? []), permission.id] : (draft.permissions ?? []).filter((id) => id !== permission.id) })} />
        <span>{permission.name}</span>
      </label>)}</div>
    </fieldset>
    <div className="flex flex-wrap items-center gap-3 sm:col-span-2 lg:col-span-3">
      <label className="flex items-center gap-2 text-xs"><input type="checkbox" disabled={busy} checked={draft.active}
        onChange={(event) => setDraft({ ...draft, active: event.target.checked })} />上架</label>
      <Button type="submit" disabled={busy}><Save size={14} />保存</Button>
      {plan && <Button type="button" variant="danger" disabled={busy} onClick={() => void remove()}><Trash2 size={14} />删除</Button>}
      {message && <p role="status" className="text-xs">{message}</p>}
    </div>
  </form>;
}

export function PlanManager({ onBack }: { onBack: () => void }) {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  async function load() { setPlans(await apiFetch<Plan[]>("/admin/plans")); }
  useEffect(() => {
    let active = true;
    Promise.all([apiFetch<Plan[]>("/admin/plans"), apiFetch<Plugin[]>("/plugins"), apiFetch<Permission[]>("/admin/permissions")])
      .then(([rows, catalog, actions]) => { if (active) { setPlans(rows); setPlugins(catalog); setPermissions(actions); } })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "加载失败"); });
    return () => { active = false; };
  }, []);
  return <section>
    <div className="flex flex-wrap items-center justify-between gap-3"><Button variant="outline" onClick={onBack}><ArrowLeft size={14} />返回管理控制台</Button>
      <h2 className="text-base font-semibold">套餐与权限</h2><Button onClick={() => setCreating(!creating)}><Plus size={14} />新增套餐</Button></div>
    <p className="mt-3 text-xs text-[#777]">保存影响后续购买和管理员调整订阅，不修改已有订阅的权益快照。</p>
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
    {creating && permissions.length > 0 && <PlanEditor plugins={plugins} permissions={permissions} onChanged={load} />}
    {permissions.length > 0 && plans.map((plan) => <PlanEditor key={JSON.stringify(plan)} plan={plan} plugins={plugins} permissions={permissions} onChanged={load} />)}
  </section>;
}
