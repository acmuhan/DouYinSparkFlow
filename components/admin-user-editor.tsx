"use client";

import { FormEvent, useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Pencil, Plus, Save, Send, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { User, apiFetch } from "@/lib/api";

export function AdminUserDirectory() {
  const [users, setUsers] = useState<User[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  async function load() {
    try { setUsers(await apiFetch<User[]>("/admin/users")); setError(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "用户加载失败"); }
  }
  useEffect(() => {
    let active = true;
    apiFetch<User[]>("/admin/users").then((rows) => { if (active) setUsers(rows); })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "用户加载失败"); });
    return () => { active = false; };
  }, []);
  const visible = users.filter((user) => `${user.email} ${user.name}`.toLowerCase().includes(query.trim().toLowerCase()));
  return <section className="mt-8 border-t border-[#e7e7e7] py-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-sm font-semibold">用户账户管理</h2><AdminUserEditor onChanged={load} /></div>
    <input aria-label="搜索用户" placeholder="搜索姓名或邮箱" value={query} onChange={(event) => setQuery(event.target.value)}
      className="mt-4 h-10 w-full rounded-[5px] border border-[#dcdcd9] px-3 text-sm" />
    {error && <p role="alert" className="mt-3 text-xs text-red-700">{error}</p>}
    <ul className="mt-3 max-h-96 divide-y overflow-y-auto border-y border-[#e7e7e7]">
      {visible.map((user) => <li className="flex items-center gap-3 py-3" key={user.id}>
        <div className="min-w-0 flex-1"><p className="break-words text-sm">{user.name}</p><p className="break-all text-xs text-[#777]">{user.email}</p></div>
        <span className="text-xs text-[#777]">{user.status}</span><AdminUserEditor user={user} onChanged={load} />
      </li>)}
      {!visible.length && <li className="py-4 text-sm text-[#777]">暂无匹配用户</li>}
    </ul>
  </section>;
}

export function AdminUserEditor({ user, onChanged }: { user?: User; onChanged: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(user?.name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [mailStatus, setMailStatus] = useState("");
  const field = "mt-2 h-10 w-full rounded-[5px] border border-[#dcdcd9] px-3 text-sm";
  if (user?.role === "ADMIN") return null;
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await apiFetch(user ? `/admin/users/${user.id}` : "/admin/users", {
        method: user ? "PATCH" : "POST",
        body: JSON.stringify(user ? { name, email } : { name, email, password }),
      });
      setPassword(""); setOpen(false); await onChanged();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "保存失败"); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!user) return;
    setBusy(true); setError("");
    try {
      await apiFetch(`/admin/users/${user.id}`, { method: "DELETE" });
      setOpen(false); await onChanged();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "删除失败"); }
    finally { setBusy(false); }
  }
  async function send(event: FormEvent) {
    event.preventDefault();
    if (!user) return;
    setBusy(true); setError(""); setMailStatus("");
    try {
      await apiFetch(`/admin/users/${user.id}/email`, { method: "POST", body: JSON.stringify({ subject, body }) });
      setMailStatus("SMTP 已接受邮件，最终送达请以收件箱为准。");
      setSubject(""); setBody("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "邮件发送失败"); }
    finally { setBusy(false); }
  }
  function changeOpen(value: boolean) {
    if (busy) return;
    setOpen(value); setError(""); setDeleting(false); setPassword("");
    setSubject(""); setBody(""); setMailStatus("");
    setName(user?.name ?? ""); setEmail(user?.email ?? "");
  }
  return <Dialog.Root open={open} onOpenChange={changeOpen}>
    <Dialog.Trigger asChild><Button type="button" size="sm" variant="outline" title={user ? "编辑用户" : "新增用户"}
      aria-label={user ? `编辑 ${user.email}` : "新增用户"}>{user ? <Pencil size={14} /> : <><Plus size={14} />新增用户</>}</Button></Dialog.Trigger>
    <Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-black/25" />
      <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-md bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between"><Dialog.Title className="text-base font-semibold">{user ? "编辑用户" : "新增用户"}</Dialog.Title>
          <Dialog.Close asChild><Button type="button" disabled={busy} variant="ghost" size="sm" aria-label="关闭"><X size={16} /></Button></Dialog.Close></div>
        <Dialog.Description className="mt-2 text-xs text-[#777]">{user ? "换绑邮箱将撤销该用户的所有登录会话及 API 密钥。" : "创建普通用户账户。"}</Dialog.Description>
        <form onSubmit={save} className="mt-5 space-y-4">
          <label className="block text-xs">名称<input required minLength={2} maxLength={80} value={name} disabled={busy} className={field} onChange={(event) => setName(event.target.value)} /></label>
          <label className="block text-xs">邮箱<input required type="email" maxLength={254} value={email} disabled={busy} className={field} onChange={(event) => setEmail(event.target.value)} /></label>
          {!user && <label className="block text-xs">初始密码<input required type="password" autoComplete="new-password" minLength={8} maxLength={128} value={password} disabled={busy} className={field} onChange={(event) => setPassword(event.target.value)} /></label>}
          <div className="flex flex-wrap justify-between gap-3">
            <Button type="submit" disabled={busy}><Save size={14} />保存</Button>
            {user && <Button type="button" variant="danger" disabled={busy} onClick={() => setDeleting(true)}><Trash2 size={14} />删除用户</Button>}
          </div>
        </form>
        {user && <form onSubmit={send} className="mt-5 space-y-3 border-t border-[#e7e7e7] pt-4">
          <h3 className="text-sm font-medium">发信给 {user.email}</h3>
          <label className="block text-xs">主题<input required maxLength={160} disabled={busy} value={subject} className={field} onChange={(event) => setSubject(event.target.value)} /></label>
          <label className="block text-xs">正文<textarea required maxLength={20000} disabled={busy} value={body} className="mt-2 min-h-24 w-full rounded-[5px] border border-[#dcdcd9] p-3 text-sm" onChange={(event) => setBody(event.target.value)} /></label>
          <Button type="submit" variant="outline" disabled={busy}><Send size={14} />发送邮件</Button>
          {mailStatus && <p role="status" className="text-xs text-green-700">{mailStatus}</p>}
        </form>}
        {deleting && <div className="mt-5 border-t border-red-200 pt-4">
          <p className="text-sm text-red-700">确认注销 {user?.email}？此操作会清除资源 Cookie、停用任务并撤销登录权限，历史账单保留。操作不可撤销。</p>
          <div className="mt-3 flex gap-2"><Button type="button" variant="danger" disabled={busy} onClick={() => void remove()}>确认删除</Button>
            <Button type="button" variant="outline" disabled={busy} onClick={() => setDeleting(false)}>取消</Button></div>
        </div>}
        {error && <p role="alert" className="mt-4 text-xs text-red-700">{error}</p>}
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}
