"use client";

import { FormEvent, useEffect, useState } from "react";
import { Check, Loader2, Pencil, Plus, RefreshCw, Save, Trash2, Users, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Account, FriendList, apiFetch, taskInputSchema } from "@/lib/api";

const field = "mt-2 h-10 w-full rounded-[5px] border border-[#dcdcd9] bg-white px-3 text-sm";
const waiting = (status: string | null) => status === "QUEUED" || status === "CHECKING";
const failure = (reason: unknown) => reason instanceof Error ? reason.message : "请求失败";

export function FriendPicker({ accountId, selected, onChange }: { accountId: string; selected?: string[]; onChange?: (ids: string[]) => void }) {
  const [list, setList] = useState<FriendList | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const value = await apiFetch<FriendList>(`/accounts/${accountId}/friends`);
        if (active) { setList(value); setError(""); }
      } catch (reason) { if (active) setError(failure(reason)); }
      finally { if (active) timer = setTimeout(() => void load(), 4000); }
    }
    void load();
    return () => { active = false; clearTimeout(timer); };
  }, [accountId]);
  async function refresh() {
    setBusy(true); setError("");
    try {
      await apiFetch(`/accounts/${accountId}/validate`, { method: "POST" });
      setList(await apiFetch<FriendList>(`/accounts/${accountId}/friends`));
    } catch (reason) { setError(failure(reason)); }
    finally { setBusy(false); }
  }
  const visible = list?.items.filter((item) => `${item.name} ${item.unique_id} ${item.id}`.toLowerCase().includes(query.toLowerCase())) ?? [];
  return <section className="mt-4 border-t border-[#e7e7e7] pt-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="text-sm font-semibold">目标好友</h3>
      <Button type="button" size="sm" variant="outline" disabled={busy || waiting(list?.inspection_status ?? null)} onClick={() => void refresh()}>
        <RefreshCw size={14} />{waiting(list?.inspection_status ?? null) ? "同步中" : "同步好友"}</Button></div>
    <input aria-label="搜索好友" placeholder="搜索好友" className={field} value={query} onChange={(event) => setQuery(event.target.value)} />
    {error && <p role="alert" className="mt-2 text-xs text-red-700">{error}</p>}
    <div className="mt-3 h-48 overflow-y-auto border-y border-[#e7e7e7]">
      {visible.map((item) => <label key={item.id} className="flex min-h-12 items-center gap-3 border-b border-[#eeeeec] px-2 py-2 text-sm">
        {onChange && <input type="checkbox" checked={selected?.includes(item.id) ?? false}
          disabled={!selected?.includes(item.id) && (selected?.length ?? 0) >= 100}
          onChange={(event) => onChange(event.target.checked ? [...(selected ?? []), item.id] : (selected ?? []).filter((id) => id !== item.id))} />}
        <span className="min-w-0"><span className="block break-words">{item.name}</span><span className="block break-all text-xs text-[#777]">{item.unique_id || item.id}</span></span>
      </label>)}
      {!list && !error && <p role="status" className="p-3 text-xs text-[#777]">加载中</p>}
      {list && !visible.length && <p className="p-3 text-xs text-[#777]">{waiting(list.inspection_status) ? "等待 Worker 获取好友" : "暂无匹配好友"}</p>}
    </div>
    <p className="mt-2 text-xs text-[#777]">{list?.complete ? "完整列表" : "当前聊天页已加载的好友，可能不完整"}{selected ? ` · 已选 ${selected.length}/100` : ""}</p>
  </section>;
}

export function Accounts() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [editor, setEditor] = useState<string | null>(null);
  const [friendsId, setFriendsId] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", unique_id: "", cookies: "" });
  async function load() { setAccounts(await apiFetch<Account[]>("/accounts")); }
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const rows = await apiFetch<Account[]>("/accounts");
        if (active) setAccounts(rows);
      } catch (reason) { if (active) setError(failure(reason)); }
      finally { if (active) timer = setTimeout(() => void poll(), 4000); }
    }
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, []);
  function edit(account?: Account) {
    setForm({ name: account?.name ?? "", unique_id: account?.unique_id ?? "", cookies: "" });
    setEditor(account?.id ?? "new"); setError("");
  }
  async function save(event: FormEvent) {
    event.preventDefault(); setError("");
    let cookies: unknown;
    try { cookies = JSON.parse(form.cookies); if (!Array.isArray(cookies) || !cookies.length) throw new Error(); }
    catch { setError("Cookie 必须是非空 JSON 数组"); return; }
    setBusy(true);
    try {
      const row = await apiFetch<Account>(editor === "new" ? "/accounts" : `/accounts/${editor}`, {
        method: editor === "new" ? "POST" : "PATCH", body: JSON.stringify({ name: form.name, unique_id: form.unique_id, cookies }),
      });
      setForm({ name: "", unique_id: "", cookies: "" }); setEditor(null); setFriendsId(row.id); await load();
    } catch (reason) { setError(failure(reason)); }
    finally { setBusy(false); }
  }
  async function act(account: Account, remove = false) {
    if (remove && !window.confirm(`删除资源“${account.name}”？关联任务将停用。`)) return;
    setBusy(true); setError("");
    try {
      await apiFetch(`/accounts/${account.id}${remove ? "" : "/validate"}`, { method: remove ? "DELETE" : "POST" });
      if (remove && friendsId === account.id) setFriendsId(null);
      await load();
    } catch (reason) { setError(failure(reason)); }
    finally { setBusy(false); }
  }
  return <section>
    <div className="flex items-center justify-between gap-3"><h2 className="text-sm font-semibold">抖音插件资源</h2><Button disabled={busy} onClick={() => edit()}><Plus size={14} />添加资源</Button></div>
    {error && <p role="alert" className="mt-4 text-xs text-red-700">{error}</p>}
    {editor && <form onSubmit={save} className="mt-5 grid gap-4 border-y border-[#e7e7e7] py-5 sm:grid-cols-2">
      <label className="text-xs">资源名称<input required maxLength={80} disabled={busy} className={field} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
      <label className="text-xs">抖音号<input required maxLength={80} disabled={busy} className={field} value={form.unique_id} onChange={(event) => setForm({ ...form, unique_id: event.target.value })} /></label>
      <label className="text-xs sm:col-span-2">Cookie JSON<textarea required disabled={busy} value={form.cookies} autoComplete="off"
        className="mt-2 min-h-28 w-full rounded-[5px] border border-[#dcdcd9] p-3 font-mono text-xs" onChange={(event) => setForm({ ...form, cookies: event.target.value })} /></label>
      <div className="flex gap-3 sm:col-span-2"><Button type="submit" disabled={busy}><Save size={14} />保存并验证</Button>
        <Button type="button" variant="outline" disabled={busy} onClick={() => { setEditor(null); setForm({ name: "", unique_id: "", cookies: "" }); }}><X size={14} />取消</Button></div>
    </form>}
    <ul className="mt-5 divide-y border-y border-[#e7e7e7]">
      {accounts.map((account) => <li key={account.id} className="py-4">
        <div className="flex flex-wrap items-center gap-3"><div className="min-w-0 flex-1"><h3 className="break-words text-sm font-semibold">{account.name}</h3><p className="mt-1 break-all text-xs text-[#777]">@{account.unique_id}</p></div>
          <span className="text-xs">{waiting(account.inspection_status) ? "检测中" : account.status === "READY" ? "已验证" : "未验证"}</span>
          <Button size="sm" variant="outline" disabled={busy || waiting(account.inspection_status)} onClick={() => void act(account)}><RefreshCw size={14} />验证</Button>
          <Button size="sm" variant="ghost" title="更新 Cookie" aria-label={`更新 ${account.name} Cookie`} disabled={busy} onClick={() => edit(account)}><Pencil size={16} /></Button>
          <Button size="sm" variant="ghost" title="查看好友" aria-label={`查看 ${account.name} 好友`} onClick={() => setFriendsId(friendsId === account.id ? null : account.id)}><Users size={16} /></Button>
          <Button size="sm" variant="ghost" title="删除资源" aria-label={`删除 ${account.name}`} disabled={busy} onClick={() => void act(account, true)}><Trash2 size={16} /></Button>
        </div>
        {account.inspection_message && <p className="mt-2 text-xs text-[#777]">{account.inspection_message}</p>}
        {friendsId === account.id && <FriendPicker key={account.id} accountId={account.id} />}
      </li>)}
      {!accounts.length && <li className="py-8 text-sm text-[#777]">暂无资源</li>}
    </ul>
  </section>;
}

export function TaskForm({ onCreated }: { onCreated: () => void }) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [plugins, setPlugins] = useState<{ id: string; name: string; authorized: boolean; requires_account: boolean; config_schema: Record<string, unknown> }[]>([]);
  const [configText, setConfigText] = useState("{}");
  const [form, setForm] = useState({ name: "", plugin_id: "douyin_streak", account_id: "", targets: [] as string[], message: "今天也要记得续上火花", schedule_time: "21:30", timezone: "Asia/Shanghai", enabled: false });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const selectedPlugin = plugins.find((plugin) => plugin.id === form.plugin_id);
  useEffect(() => {
    let active = true;
    Promise.all([apiFetch<Account[]>("/accounts"), apiFetch<typeof plugins>("/plugins")]).then(([rows, catalog]) => {
      if (active) { setAccounts(rows); setPlugins(catalog); }
    }).catch((reason) => { if (active) setError(failure(reason)); });
    return () => { active = false; };
  }, []);
  async function save(event: FormEvent) {
    event.preventDefault(); setError("");
    let pluginConfig: Record<string, unknown> | undefined;
    if (form.plugin_id !== "douyin_streak") {
      try {
        const value = JSON.parse(configText);
        if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error();
        pluginConfig = value;
      } catch { setError("插件配置必须是 JSON 对象"); return; }
    }
    const parsed = taskInputSchema.safeParse({
      ...form, account_id: selectedPlugin?.requires_account ? form.account_id : null,
      ...(pluginConfig ? { plugin_config: pluginConfig, targets: [], message: "" } : {}),
    });
    if (!parsed.success) { setError("请填写任务名称、选择资源及至少一位目标好友"); return; }
    setBusy(true);
    try { await apiFetch("/tasks", { method: "POST", body: JSON.stringify(parsed.data) }); onCreated(); }
    catch (reason) { setError(failure(reason)); }
    finally { setBusy(false); }
  }
  return <form onSubmit={save} className="space-y-4 p-5">
    <div className="grid gap-4 sm:grid-cols-2">
      <label className="text-xs">任务名称<input required maxLength={80} className={field} disabled={busy} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
      <label className="text-xs">插件<select aria-label="插件" required disabled={busy} className={field} value={form.plugin_id} onChange={(event) => { setForm({ ...form, plugin_id: event.target.value, account_id: "", targets: [] }); setConfigText("{}"); }}>
        <option value="">选择插件</option>{plugins.map((plugin) => <option key={plugin.id} value={plugin.id} disabled={!plugin.authorized}>{plugin.name}{plugin.authorized ? "" : "（未授权）"}</option>)}</select></label>
      {selectedPlugin?.requires_account && <label className="text-xs">执行资源<select aria-label="执行资源" required disabled={busy} className={field} value={form.account_id}
        onChange={(event) => setForm({ ...form, account_id: event.target.value, targets: [] })}>
        <option value="">选择已验证资源</option>{accounts.filter((account) => account.status === "READY").map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label>}
      <label className="text-xs">每日运行时间<input type="time" required disabled={busy} className={field} value={form.schedule_time} onChange={(event) => setForm({ ...form, schedule_time: event.target.value })} /></label>
    </div>
    {form.plugin_id === "douyin_streak" ? <>
      {form.account_id && <FriendPicker key={form.account_id} accountId={form.account_id} selected={form.targets} onChange={(targets) => setForm({ ...form, targets })} />}
      <label className="block text-xs">消息内容<textarea required maxLength={2000} disabled={busy} className="mt-2 min-h-24 w-full rounded-[5px] border border-[#dcdcd9] p-3 text-sm" value={form.message} onChange={(event) => setForm({ ...form, message: event.target.value })} /></label>
    </> : <section>
      <label className="block text-xs">插件配置 JSON<textarea required disabled={busy} value={configText}
        className="mt-2 min-h-36 w-full rounded-[5px] border border-[#dcdcd9] p-3 font-mono text-xs" onChange={(event) => setConfigText(event.target.value)} /></label>
      <details className="mt-3 text-xs"><summary>配置字段定义</summary><pre className="mt-2 max-h-60 overflow-auto whitespace-pre-wrap break-all">{JSON.stringify(selectedPlugin?.config_schema ?? {}, null, 2)}</pre></details>
    </section>}
    <label className="flex items-center gap-2 text-xs"><input type="checkbox" disabled={busy} checked={form.enabled} onChange={(event) => setForm({ ...form, enabled: event.target.checked })} />启用每日定时（Asia/Shanghai）</label>
    {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
    <Button type="submit" disabled={busy || !plugins.some((plugin) => plugin.id === form.plugin_id && plugin.authorized)}>{busy ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}创建任务</Button>
  </form>;
}
