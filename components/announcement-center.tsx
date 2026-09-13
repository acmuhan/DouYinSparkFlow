"use client";

import { FormEvent, useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Bell, Check, Pencil, Plus, RefreshCw, Save, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";

type Announcement = {
  id: string; title: string; content: string; active: boolean;
  created_at: string; read_at?: string | null;
};
const empty = { title: "", content: "", active: true };
const field = "mt-2 w-full rounded-[5px] border border-[#dcdcd9] bg-white px-3 py-2 text-sm";
const date = (value: string) => new Date(/(?:[Zz]|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`).toLocaleString("zh-CN");

export function AnnouncementManager() {
  const [items, setItems] = useState<Announcement[]>([]);
  const [draft, setDraft] = useState(empty);
  const [editing, setEditing] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  async function load() {
    const rows = await apiFetch<Announcement[]>("/admin/announcements");
    setItems(rows); setLoaded(true);
  }
  useEffect(() => {
    let active = true;
    apiFetch<Announcement[]>("/admin/announcements").then((rows) => {
      if (active) { setItems(rows); setLoaded(true); }
    }).catch((reason) => { if (active) setError(String(reason)); });
    return () => { active = false; };
  }, []);
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await apiFetch(editing ? `/admin/announcements/${editing}` : "/admin/announcements", {
        method: editing ? "PATCH" : "POST", body: JSON.stringify(draft),
      });
      setDraft(empty); setEditing(null); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "公告保存失败"); }
    finally { setBusy(false); }
  }
  async function remove(item: Announcement) {
    if (!window.confirm(`删除公告“${item.title}”？此操作不可撤销。`)) return;
    setBusy(true); setError("");
    try {
      await apiFetch(`/admin/announcements/${item.id}`, { method: "DELETE" });
      if (editing === item.id) { setEditing(null); setDraft(empty); }
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "删除失败"); }
    finally { setBusy(false); }
  }
  return <section className="mt-8 border-t border-[#e7e7e7] py-6">
    <h2 className="text-sm font-semibold">公告管理</h2>
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
    <form onSubmit={save} className="mt-4 grid gap-4">
      <label className="text-xs">标题<input required maxLength={160} className={field} value={draft.title}
        disabled={busy} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
      <label className="text-xs">正文<textarea required maxLength={10000} rows={4} className={field} value={draft.content}
        disabled={busy} onChange={(event) => setDraft({ ...draft, content: event.target.value })} /></label>
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={draft.active}
          disabled={busy} onChange={(event) => setDraft({ ...draft, active: event.target.checked })} />发布</label>
        <Button type="submit" disabled={busy}><Save size={14} />{editing ? "保存修改" : "创建公告"}</Button>
        {editing && <Button variant="outline" disabled={busy} onClick={() => { setEditing(null); setDraft(empty); }}><Plus size={14} />新建</Button>}
      </div>
    </form>
    <ul className="mt-6 divide-y border-y border-[#e7e7e7]">
      {items.map((item) => <li key={item.id} className="flex items-center gap-3 py-3">
        <div className="min-w-0 flex-1"><p className="break-words text-sm">{item.title}</p>
          <p className="mt-1 text-xs text-[#777]">{item.active ? "已发布" : "未发布"} · {date(item.created_at)}</p></div>
        <Button size="sm" variant="ghost" disabled={busy} title="编辑公告" aria-label={`编辑 ${item.title}`}
          onClick={() => { setEditing(item.id); setDraft({ title: item.title, content: item.content, active: item.active }); }}><Pencil size={16} /></Button>
        <Button size="sm" variant="ghost" disabled={busy} title="删除公告" aria-label={`删除 ${item.title}`} onClick={() => void remove(item)}><Trash2 size={16} /></Button>
      </li>)}
      {loaded && !items.length && <li className="py-5 text-sm text-[#777]">暂无公告</li>}
    </ul>
  </section>;
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Announcement[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const rows = await apiFetch<Announcement[]>("/notifications/announcements");
        if (active) { setItems(rows); setError(""); }
      } catch (reason) { if (active) setError(reason instanceof Error ? reason.message : "通知加载失败"); }
    }
    void load();
    const interval = window.setInterval(() => void load(), 30000);
    return () => { active = false; window.clearInterval(interval); };
  }, [open]);
  async function refresh() {
    setBusy(true);
    try { setItems(await apiFetch<Announcement[]>("/notifications/announcements")); setError(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "通知加载失败"); }
    finally { setBusy(false); }
  }
  async function markRead(id: string) {
    setBusy(true);
    try {
      await apiFetch(`/notifications/announcements/${id}/read`, { method: "PUT" });
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "标记已读失败"); }
    finally { setBusy(false); }
  }
  const unread = items.filter((item) => !item.read_at).length;
  return <Dialog.Root open={open} onOpenChange={setOpen}>
    <Dialog.Trigger asChild><Button variant="ghost" size="sm" title="通知" aria-label={`通知，${unread} 条未读`} className="relative">
      <Bell size={17} />{unread > 0 && <span className="absolute right-0 top-0 h-2 w-2 rounded-full bg-red-600" />}
    </Button></Dialog.Trigger>
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-50 bg-black/25" />
      <Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col bg-white p-5 shadow-xl">
        <div className="flex items-center justify-between gap-3">
          <Dialog.Title className="text-base font-semibold">通知</Dialog.Title>
          <div className="flex gap-1">
            <Button size="sm" variant="ghost" disabled={busy} title="刷新通知" aria-label="刷新通知" onClick={() => void refresh()}><RefreshCw size={16} /></Button>
            <Dialog.Close asChild><Button size="sm" variant="ghost" title="关闭通知" aria-label="关闭通知"><X size={16} /></Button></Dialog.Close>
          </div>
        </div>
        <Dialog.Description className="mt-2 text-xs text-[#777]">{unread} 条未读公告</Dialog.Description>
        {error && <p role="alert" className="mt-3 text-xs text-red-700">{error}</p>}
        <div className="mt-4 min-h-0 flex-1 overflow-y-auto">
          {items.map((item) => <article key={item.id} className="border-t border-[#e7e7e7] py-4">
            <h3 className="break-words text-sm font-semibold">{item.title}</h3>
            <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6">{item.content}</p>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <time className="text-xs text-[#777]">{date(item.created_at)}</time>
              {item.read_at ? <span className="text-xs text-[#777]">已读</span> :
                <Button size="sm" variant="outline" disabled={busy} onClick={() => void markRead(item.id)}><Check size={14} />标记已读</Button>}
            </div>
          </article>)}
          {!items.length && !error && <p className="py-6 text-sm text-[#777]">暂无公告通知</p>}
        </div>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}
