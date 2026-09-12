"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setBusy(true);
    try { await apiFetch("/auth/register", { method: "POST", body: JSON.stringify(form) }); router.push("/"); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "注册失败"); } finally { setBusy(false); }
  }
  return <div><div className="mb-10 lg:hidden"><Link href="/" className="text-sm font-semibold">sparkflow</Link></div><div className="mb-8"><p className="font-mono text-[10px] uppercase tracking-[.2em] text-[#999]">Get started</p><h1 className="mt-3 text-2xl font-semibold tracking-[-.05em]">创建工作区</h1><p className="mt-2 text-sm text-[#777]">先从一个账号和一个任务开始。</p></div><form onSubmit={submit} className="space-y-4"><label className="block"><span className="mb-2 block text-xs font-medium">名称</span><input required minLength={2} value={form.name} onChange={(e) => setForm({...form, name:e.target.value})} placeholder="你的昵称或团队名" className="h-11 w-full rounded-[5px] border border-[#dedede] px-3 text-sm outline-none focus:border-[#161616]"/></label><label className="block"><span className="mb-2 block text-xs font-medium">邮箱</span><input required type="email" autoComplete="email" value={form.email} onChange={(e) => setForm({...form, email:e.target.value})} placeholder="you@company.com" className="h-11 w-full rounded-[5px] border border-[#dedede] px-3 text-sm outline-none focus:border-[#161616]"/></label><label className="block"><span className="mb-2 block text-xs font-medium">密码</span><input required type="password" minLength={8} autoComplete="new-password" value={form.password} onChange={(e) => setForm({...form, password:e.target.value})} placeholder="至少 8 位字符" className="h-11 w-full rounded-[5px] border border-[#dedede] px-3 text-sm outline-none focus:border-[#161616]"/></label>{error && <p role="alert" className="border border-[#f0c4be] bg-[#fff7f5] px-3 py-2 text-xs text-[#b43c2d]">{error}</p>}<Button disabled={busy} className="h-11 w-full">{busy ? <Loader2 size={15} className="animate-spin"/> : <ArrowRight size={15}/>}创建账户</Button></form><p className="mt-8 text-center text-xs text-[#777]">已有账户？ <Link href="/login" className="font-medium text-[#161616] underline underline-offset-4">返回登录</Link></p></div>;
}
