"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setBusy(true);
    try { await apiFetch("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }); router.push("/"); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "登录失败"); } finally { setBusy(false); }
  }
  return <div><div className="mb-10 lg:hidden"><Link href="/" className="text-sm font-semibold">sparkflow</Link></div><div className="mb-8"><p className="font-mono text-[10px] uppercase tracking-[.2em] text-[#999]">Welcome back</p><h1 className="mt-3 text-2xl font-semibold tracking-[-.05em]">登录工作区</h1><p className="mt-2 text-sm text-[#777]">继续管理你的自动化任务。</p></div><form onSubmit={submit} className="space-y-4"><label className="block"><span className="mb-2 block text-xs font-medium">邮箱</span><input required type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" className="h-11 w-full rounded-[5px] border border-[#dedede] px-3 text-sm outline-none transition placeholder:text-[#aaa] focus:border-[#161616]"/></label><label className="block"><span className="mb-2 block text-xs font-medium">密码</span><input required type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="至少 8 位字符" className="h-11 w-full rounded-[5px] border border-[#dedede] px-3 text-sm outline-none transition placeholder:text-[#aaa] focus:border-[#161616]"/></label>{error && <p role="alert" className="border border-[#f0c4be] bg-[#fff7f5] px-3 py-2 text-xs text-[#b43c2d]">{error}</p>}<Button disabled={busy} className="h-11 w-full">{busy ? <Loader2 size={15} className="animate-spin"/> : <ArrowRight size={15}/>}登录</Button></form><p className="mt-8 text-center text-xs text-[#777]">还没有工作区？ <Link href="/register" className="font-medium text-[#161616] underline underline-offset-4">创建账户</Link></p></div>;
}
