"use client";

import Link from "next/link";
import { createContext, useContext, useEffect, useState } from "react";
import { ArrowRight, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";

export type AuthUser = { id: string; email: string; name: string; role: "USER" | "ADMIN"; status: string };
const AuthContext = createContext<AuthUser | null>(null);

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<"loading" | "signed-out" | "signed-in">("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  useEffect(() => { apiFetch<AuthUser>("/me").then((value) => { setUser(value); setState("signed-in"); }).catch(() => setState("signed-out")); }, []);
  if (state === "loading") return <div className="grid min-h-screen place-items-center bg-[#fbfbfa]"><Loader2 className="animate-spin text-[#777]" size={18}/></div>;
  if (state === "signed-in" && user) return <AuthContext.Provider value={user}>{children}</AuthContext.Provider>;
  return <main className="grid min-h-screen place-items-center bg-[#fbfbfa] px-6"><div className="grid-paper w-full max-w-[520px] border border-[#e7e7e7] bg-white p-8 sm:p-12"><div className="flex h-9 w-9 items-center justify-center rounded-[6px] bg-[#161616] text-white"><Sparkles size={16}/></div><p className="mt-12 font-mono text-[10px] uppercase tracking-[.2em] text-[#999]">SparkFlow Console</p><h1 className="mt-4 text-3xl font-semibold tracking-[-.06em]">你的自动化工作区<br/>正在等你。</h1><p className="mt-5 max-w-[360px] text-sm leading-6 text-[#777]">登录后管理账号、任务、订阅和运行记录。所有抖音 Cookie 都会加密保存。</p><div className="mt-9 flex flex-col gap-3 sm:flex-row"><Link href="/login" className="flex-1"><Button className="w-full">登录工作区 <ArrowRight size={15}/></Button></Link><Link href="/register" className="flex-1"><Button variant="outline" className="w-full">创建账户</Button></Link></div><p className="mt-8 text-[11px] leading-5 text-[#999]">继续使用即表示你同意遵守抖音平台规则，并仅对有权管理的账号执行任务。</p></div></main>;
}
