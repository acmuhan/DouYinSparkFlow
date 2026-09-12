"use client";

import { useState } from "react";
import { useEffect } from "react";
import { Activity, ArrowUpRight, BarChart3, Bell, Check, ChevronRight, CircleHelp, CreditCard, KeyRound, LayoutDashboard, LogOut, Menu, Plus, ReceiptText, Server, Settings2, Sparkles, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { apiFetch, taskInputSchema } from "@/lib/api";

type View = "overview" | "tasks" | "accounts" | "billing" | "keys" | "admin";

const nav = [
  { id: "overview" as View, label: "概览", icon: LayoutDashboard },
  { id: "tasks" as View, label: "任务中心", icon: Activity },
  { id: "accounts" as View, label: "抖音资源", icon: Server },
  { id: "billing" as View, label: "订阅与账单", icon: CreditCard },
  { id: "keys" as View, label: "API 密钥", icon: KeyRound },
];

const tasks = [
  { name: "晚间火花维护", account: "主账号 · sunny_lab", schedule: "每天 21:30", state: "运行中", sent: "1,248", next: "今天 21:30" },
  { name: "工作室客户组", account: "运营账号 · studio_02", schedule: "每天 09:00", state: "已暂停", sent: "862", next: "手动触发" },
  { name: "周末好友维护", account: "主账号 · sunny_lab", schedule: "周六 10:00", state: "运行中", sent: "316", next: "周六 10:00" },
];

function SideNav({ active, onSelect, onClose }: { active: View; onSelect: (view: View) => void; onClose?: () => void }) {
  return <aside className="flex h-full w-[244px] shrink-0 flex-col border-r border-[#e7e7e7] bg-[#fbfbfa]">
    <div className="flex h-[72px] items-center justify-between border-b border-[#e7e7e7] px-6">
      <div className="flex items-center gap-2.5"><div className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-[#161616] text-white"><Sparkles size={14} /></div><span className="font-semibold tracking-[-.03em]">sparkflow</span></div>
      {onClose && <Button variant="ghost" size="sm" aria-label="关闭菜单" onClick={onClose}><X size={16} /></Button>}
    </div>
    <div className="px-3 py-5">
      <div className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[.18em] text-[#9a9a9a]">Workspace</div>
      {nav.map((item) => { const Icon = item.icon; return <button key={item.id} onClick={() => { onSelect(item.id); onClose?.(); }} className={cn("flex h-10 w-full items-center gap-3 rounded-[5px] px-3 text-sm transition", active === item.id ? "bg-[#161616] text-white" : "text-[#707070] hover:bg-[#f0f0ee] hover:text-[#161616]")}><Icon size={16} strokeWidth={1.8} /><span>{item.label}</span>{item.id === "billing" && <Badge tone="orange" className="ml-auto border-0 bg-[#f6e7d0] text-[10px]">PRO</Badge>}</button>; })}
      <div className="mb-2 mt-8 px-3 text-[10px] font-semibold uppercase tracking-[.18em] text-[#9a9a9a]">System</div>
      <button onClick={() => onSelect("admin")} className={cn("flex h-10 w-full items-center gap-3 rounded-[5px] px-3 text-sm transition", active === "admin" ? "bg-[#161616] text-white" : "text-[#707070] hover:bg-[#f0f0ee] hover:text-[#161616]")}><BarChart3 size={16} strokeWidth={1.8} /><span>管理控制台</span></button>
    </div>
    <div className="mt-auto border-t border-[#e7e7e7] p-4">
      <div className="flex items-center gap-3 rounded-[6px] p-2"><div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#e8e8e6] text-xs font-semibold">SL</div><div className="min-w-0 flex-1"><p className="truncate text-xs font-medium">sunny.lab</p><p className="truncate text-[11px] text-[#909090]">Pro workspace</p></div><Settings2 size={15} className="text-[#909090]" /></div>
    </div>
  </aside>;
}

function Topbar({ title, onMenu }: { title: string; onMenu: () => void }) {
  return <header className="flex h-[72px] items-center justify-between border-b border-[#e7e7e7] bg-[#fbfbfa] px-5 sm:px-8"><div className="flex items-center gap-3"><Button variant="ghost" size="sm" className="md:hidden" aria-label="打开菜单" onClick={onMenu}><Menu size={18} /></Button><div><div className="text-[11px] text-[#9a9a9a]">Workspace / Console</div><h1 className="text-[17px] font-semibold tracking-[-.03em]">{title}</h1></div></div><div className="flex items-center gap-2"><Button variant="ghost" size="sm" aria-label="帮助"><CircleHelp size={17} /></Button><Button variant="ghost" size="sm" aria-label="通知"><Bell size={17} /></Button><div className="ml-2 h-6 w-px bg-[#e7e7e7]" /><Button variant="ghost" size="sm" aria-label="退出登录"><LogOut size={16} /></Button></div></header>;
}

function Overview({ onSelect }: { onSelect: (view: View) => void }) {
  return <div className="space-y-6">
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {[["本月已发送", "2,426", "+18.2%", "↑"], ["活跃任务", "2 / 3", "1 个已暂停", "·"], ["订阅有效期", "2026.12.08", "还有 87 天", "→"], ["本月额度", "2,426 / 3,000", "剩余 574 次", "↗"]].map(([label, value, hint, mark], index) => <Card key={label} className="p-5"><div className="flex items-center justify-between text-xs text-[#858585]"><span>{label}</span><span className={index === 0 ? "text-[#287b42]" : "text-[#aaa]"}>{mark}</span></div><div className="mt-4 text-[26px] font-semibold tracking-[-.05em]">{value}</div><div className="mt-1 text-xs text-[#909090]">{hint}</div>{index === 3 && <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-[#eeeeec]"><div className="h-full w-[81%] rounded-full bg-[#161616]" /></div>}</Card>)}
    </div>
    <div className="grid gap-6 xl:grid-cols-[1.3fr_.7fr]">
      <Card className="overflow-hidden"><div className="flex items-center justify-between border-b border-[#e7e7e7] px-5 py-4"><div><h2 className="text-sm font-semibold">最近运行</h2><p className="mt-1 text-xs text-[#909090]">过去 7 天的执行概览</p></div><Button variant="ghost" size="sm" onClick={() => onSelect("tasks")}>查看全部 <ArrowUpRight size={14} /></Button></div><div className="p-5"><div className="flex h-[190px] items-end gap-2 border-b border-[#eeeeec] bg-[linear-gradient(to_top,rgba(22,22,22,.045)_1px,transparent_1px)] bg-[length:100%_38px] px-2 pb-0 pt-8">{[35, 42, 38, 55, 48, 66, 61, 73, 54, 82, 75, 88, 70, 94, 79, 87, 92, 76, 86, 72, 98, 89, 100, 82, 95, 90, 100, 84, 92, 78].map((height, i) => <div key={i} className={cn("group relative flex-1 rounded-t-[2px] transition hover:bg-[#ff5c35]", i > 23 ? "bg-[#161616]" : "bg-[#cfcfcb]")} style={{ height: `${height}%` }} />)}</div><div className="mt-3 flex justify-between text-[10px] text-[#a1a1a1]"><span>09/06</span><span>09/08</span><span>09/10</span><span>09/12</span></div></div></Card>
      <Card><div className="border-b border-[#e7e7e7] px-5 py-4"><h2 className="text-sm font-semibold">当前计划</h2><p className="mt-1 text-xs text-[#909090]">Pro · 按月订阅</p></div><div className="p-5"><div className="flex items-end justify-between"><div><span className="text-[34px] font-semibold tracking-[-.06em]">¥49</span><span className="ml-1 text-xs text-[#909090]">/ 月</span></div><Badge tone="green">运行正常</Badge></div><div className="mt-6 space-y-3 border-t border-[#eeeeec] pt-4">{["5 个抖音账号", "30 个自动化任务", "3,000 次运行额度"].map((item) => <div key={item} className="flex items-center gap-2 text-xs text-[#5c5c5c]"><Check size={14} className="text-[#287b42]" />{item}</div>)}</div><Button className="mt-6 w-full" variant="outline" onClick={() => onSelect("billing")}>管理订阅 <ChevronRight size={14} /></Button></div></Card>
    </div>
    <Card className="overflow-hidden"><div className="flex items-center justify-between border-b border-[#e7e7e7] px-5 py-4"><div><h2 className="text-sm font-semibold">任务概览</h2><p className="mt-1 text-xs text-[#909090]">已配置任务的即时状态</p></div><Button size="sm" onClick={() => onSelect("tasks")}><Plus size={14} /> 新建任务</Button></div><TaskTable compact /></Card>
  </div>;
}

type ApiTask = { id: string; name: string; account_id: string; targets: string[]; schedule_time: string; enabled: boolean; archived: boolean; next_run_at: string | null; };
function TaskTable({ compact = false, onRefresh }: { compact?: boolean; onRefresh?: () => void }) {
  const [items, setItems] = useState<ApiTask[] | null>(null);
  const [error, setError] = useState("");
  const [running, setRunning] = useState("");
  useEffect(() => { apiFetch<ApiTask[]>("/tasks").then(setItems).catch((reason) => setError(reason instanceof Error ? reason.message : "任务加载失败")); }, []);
  async function run(id: string) {
    setRunning(id); setError("");
    try { await apiFetch(`/tasks/${id}/run`, { method: "POST" }); onRefresh?.(); } catch (reason) { setError(reason instanceof Error ? reason.message : "无法启动任务"); } finally { setRunning(""); }
  }
  const rows: Array<{ id?: string; name: string; account: string; schedule: string; sent: string; next: string; state: string }> = items?.length ? items.map((item) => ({ id: item.id, name: item.name, account: `资源 ${item.account_id.slice(0, 8)}`, schedule: `每天 ${item.schedule_time}`, sent: "—", next: item.next_run_at ? new Date(item.next_run_at).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : "手动触发", state: item.enabled ? "运行中" : "已暂停" })) : tasks;
  return <div className="overflow-x-auto"><div className="px-5 pt-3">{error && <p role="alert" className="text-xs text-[#b43c2d]">{error}</p>}</div><table className="w-full min-w-[700px] text-left text-xs"><thead className="bg-[#fafaf9] text-[10px] uppercase tracking-[.14em] text-[#989898]"><tr><th className="px-5 py-3 font-medium">任务</th><th className="px-5 py-3 font-medium">计划</th><th className="px-5 py-3 font-medium">已发送</th><th className="px-5 py-3 font-medium">下次运行</th><th className="px-5 py-3 font-medium">状态</th><th className="px-5 py-3" /></tr></thead><tbody className="divide-y divide-[#eeeeec]">{rows.slice(0, compact ? 3 : 10).map((task) => <tr key={task.id ?? task.name} className="group hover:bg-[#fcfcfb]"><td className="px-5 py-4"><div className="font-medium">{task.name}</div><div className="mt-1 text-[11px] text-[#999]">{task.account}</div></td><td className="px-5 py-4 text-[#666]">{task.schedule}</td><td className="px-5 py-4 font-mono text-[11px]">{task.sent}</td><td className="px-5 py-4 text-[#666]">{task.next}</td><td className="px-5 py-4"><Badge tone={task.state === "运行中" ? "green" : "orange"}>{task.state}</Badge></td><td className="px-5 py-4 text-right">{task.id && items?.length ? <Button variant="ghost" size="sm" disabled={running === task.id} onClick={() => { if (task.id) void run(task.id); }}>{running === task.id ? "启动中" : "运行"} <ArrowUpRight size={14} /></Button> : <Button variant="ghost" size="sm" aria-label={`打开${task.name}`}><ChevronRight size={15} /></Button>}</td></tr>)}</tbody></table></div>;
}

function TaskForm({ onCreated }: { onCreated: () => void }) {
  const [accounts, setAccounts] = useState<{ id: string; name: string }[]>([]);
  const [form, setForm] = useState({ account_id: "", name: "", targets: "", message: "今天也要记得续上火花", hitokoto_types: [] as string[], schedule_time: "21:30", timezone: "Asia/Shanghai", enabled: false });
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => { apiFetch<{ id: string; name: string }[]>("/accounts").then(setAccounts).catch(() => undefined); }, []);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setError("");
    const parsed = taskInputSchema.safeParse({ ...form, targets: form.targets.split(/[,，\n]/).map((item) => item.trim()).filter(Boolean) });
    if (!parsed.success) { setError(parsed.error.issues[0]?.message ?? "请检查表单"); return; }
    if (!parsed.data.account_id) { setError("请先添加抖音资源"); return; }
    setBusy(true);
    try { await apiFetch("/tasks", { method: "POST", body: JSON.stringify(parsed.data) }); onCreated(); } catch (reason) { setError(reason instanceof Error ? reason.message : "创建失败"); } finally { setBusy(false); }
  }
  return <form onSubmit={submit} className="space-y-4 border-t border-[#e7e7e7] bg-[#fcfcfb] p-5"><div className="grid gap-4 sm:grid-cols-2"><label className="block"><span className="mb-2 block text-xs font-medium">任务名称</span><input required value={form.name} onChange={(event) => setForm({...form, name:event.target.value})} className="h-10 w-full rounded-[5px] border border-[#dcdcd9] bg-white px-3 text-sm outline-none focus:border-[#161616]" placeholder="例如：晚间火花维护"/></label><label className="block"><span className="mb-2 block text-xs font-medium">执行资源</span><select required value={form.account_id} onChange={(event) => setForm({...form, account_id:event.target.value})} className="h-10 w-full rounded-[5px] border border-[#dcdcd9] bg-white px-3 text-sm outline-none focus:border-[#161616]"><option value="">选择抖音账号</option>{accounts.map((account) => <option value={account.id} key={account.id}>{account.name}</option>)}</select></label></div><label className="block"><span className="mb-2 block text-xs font-medium">目标好友</span><textarea required value={form.targets} onChange={(event) => setForm({...form, targets:event.target.value})} className="min-h-[72px] w-full rounded-[5px] border border-[#dcdcd9] bg-white px-3 py-2 text-sm outline-none focus:border-[#161616]" placeholder="每行或逗号分隔"/></label><div className="grid gap-4 sm:grid-cols-2"><label className="block"><span className="mb-2 block text-xs font-medium">消息模板</span><input required value={form.message} onChange={(event) => setForm({...form, message:event.target.value})} className="h-10 w-full rounded-[5px] border border-[#dcdcd9] bg-white px-3 text-sm outline-none focus:border-[#161616]"/></label><label className="block"><span className="mb-2 block text-xs font-medium">每日运行时间</span><input required type="time" value={form.schedule_time} onChange={(event) => setForm({...form, schedule_time:event.target.value})} className="h-10 w-full rounded-[5px] border border-[#dcdcd9] bg-white px-3 text-sm outline-none focus:border-[#161616]"/></label></div>{error && <p role="alert" className="text-xs text-[#b43c2d]">{error}</p>}<div className="flex justify-end gap-2"><Button type="submit" disabled={busy}>{busy ? "创建中…" : "创建任务"}</Button></div></form>;
}

function Billing() {
  const plans = [{ name: "Starter", price: "19", desc: "个人入门", features: ["1 个账号", "5 个任务", "300 次 / 月"], current: false }, { name: "Pro", price: "49", desc: "稳定运营", features: ["5 个账号", "30 个任务", "3,000 次 / 月"], current: true }, { name: "Studio", price: "129", desc: "团队工作区", features: ["20 个账号", "200 个任务", "20,000 次 / 月"], current: false }];
  return <div className="space-y-6"><Card className="flex flex-col justify-between gap-5 p-6 sm:flex-row sm:items-center"><div><div className="flex items-center gap-2"><span className="text-sm font-semibold">Pro plan</span><Badge tone="green">生效中</Badge></div><p className="mt-2 text-xs text-[#777]">下一次续费：2026 年 12 月 08 日 · 自动续费已关闭</p></div><Button variant="outline">查看订单记录 <ReceiptText size={14} /></Button></Card><div><div className="mb-4"><h2 className="text-sm font-semibold">选择一个计划</h2><p className="mt-1 text-xs text-[#909090]">所有计划都包含任务调度和运行历史。</p></div><div className="grid gap-4 lg:grid-cols-3">{plans.map((plan) => <Card key={plan.name} className={cn("relative p-5", plan.current && "border-[#161616]")}><div className="flex items-start justify-between"><div><h3 className="font-semibold">{plan.name}</h3><p className="mt-1 text-xs text-[#888]">{plan.desc}</p></div>{plan.current && <Badge>当前计划</Badge>}</div><div className="mt-6"><span className="text-3xl font-semibold tracking-[-.06em]">¥{plan.price}</span><span className="text-xs text-[#888]"> / 月</span></div><div className="my-5 space-y-3 border-y border-[#eeeeec] py-5">{plan.features.map((feature) => <div key={feature} className="flex items-center gap-2 text-xs text-[#555]"><Check size={14} className="text-[#287b42]" />{feature}</div>)}</div><Button className="w-full" variant={plan.current ? "outline" : "solid"} disabled={plan.current}>{plan.current ? "当前使用中" : "升级计划"}</Button></Card>)}</div></div></div>;
}

function Accounts() {
  return <div className="space-y-6"><div className="flex items-end justify-between"><div><h2 className="text-sm font-semibold">抖音资源</h2><p className="mt-1 text-xs text-[#909090]">Cookie 加密存储，只在 Runner 执行时解密。</p></div><Button><Plus size={14} /> 添加账号</Button></div><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{[{name:"主账号",id:"sunny_lab",tasks:"2 个任务",status:"在线",color:"bg-[#e9f5eb]"},{name:"运营账号",id:"studio_02",tasks:"1 个任务",status:"待验证",color:"bg-[#fff3e1]"}].map((account)=><Card key={account.id} className="p-5"><div className="flex items-start justify-between"><div className={cn("flex h-10 w-10 items-center justify-center rounded-[6px] text-sm font-semibold",account.color)}>{account.name.slice(0,1)}</div><Badge tone={account.status==="在线"?"green":"orange"}>{account.status}</Badge></div><h3 className="mt-5 text-sm font-semibold">{account.name}</h3><p className="mt-1 font-mono text-[11px] text-[#888]">@{account.id}</p><div className="mt-5 flex items-center justify-between border-t border-[#eeeeec] pt-4 text-xs text-[#777]"><span>{account.tasks}</span><Button variant="ghost" size="sm">管理 <ChevronRight size={14}/></Button></div></Card>)}</div></div>;
}

function Keys() {
  return <div className="space-y-6"><Card className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="text-sm font-semibold">个人 API 密钥</h2><p className="mt-1 max-w-xl text-xs leading-5 text-[#777]">用于触发任务和读取运行状态。密钥只在创建时显示一次，请妥善保存。</p></div><Button><Plus size={14}/> 创建密钥</Button></Card><Card className="overflow-hidden"><div className="border-b border-[#e7e7e7] px-5 py-4"><h2 className="text-sm font-semibold">已创建的密钥</h2></div><div className="divide-y divide-[#eeeeec]">{[{name:"本地开发",key:"sf_live_••••••••••••91kP",date:"2026-08-12",status:"有效"},{name:"自动化服务器",key:"sf_live_••••••••••••G7t2",date:"2026-07-30",status:"已撤销"}].map(key=><div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center" key={key.name}><KeyRound size={16} className="text-[#888]"/><div className="min-w-0 flex-1"><div className="text-xs font-medium">{key.name}</div><div className="mt-1 font-mono text-[11px] text-[#888]">{key.key}</div></div><span className="text-[11px] text-[#999]">{key.date}</span><Badge tone={key.status==="有效"?"green":"neutral"}>{key.status}</Badge><Button variant="ghost" size="sm" aria-label={`撤销${key.name}`}><X size={14}/></Button></div>)}</div></Card></div>;
}

function Admin() {
  return <div className="space-y-6"><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[["总用户", "1,284", "+12.8%"], ["活跃订阅", "936", "+8.4%"], ["本月流水", "¥48,620", "+21.3%"], ["转化率", "13.6%", "+2.1%"]].map(([label,value,change])=><Card className="p-5" key={label}><div className="text-xs text-[#858585]">{label}</div><div className="mt-4 text-[26px] font-semibold tracking-[-.05em]">{value}</div><div className="mt-1 text-xs text-[#287b42]">{change} <span className="text-[#999]">较上月</span></div></Card>)}</div><div className="grid gap-6 xl:grid-cols-[1fr_.8fr]"><Card className="overflow-hidden"><div className="flex items-center justify-between border-b border-[#e7e7e7] px-5 py-4"><div><h2 className="text-sm font-semibold">近期交易</h2><p className="mt-1 text-xs text-[#909090]">最近 30 天订单状态</p></div><Button variant="ghost" size="sm">导出 CSV <ArrowUpRight size={14}/></Button></div><div className="divide-y divide-[#eeeeec]">{[["#SF-10284","sunny.lab","Pro / 月","¥49.00","已支付"],["#SF-10283","blueframe","Starter / 季","¥49.00","已支付"],["#SF-10282","mori_studio","Pro / 月","¥49.00","待支付"]].map(order=><div className="flex items-center gap-4 px-5 py-4 text-xs" key={order[0]}><span className="font-mono text-[11px] text-[#888]">{order[0]}</span><span className="min-w-0 flex-1 font-medium">{order[1]}</span><span className="hidden text-[#777] sm:block">{order[2]}</span><span className="font-mono">{order[3]}</span><Badge tone={order[4]==="已支付"?"green":"orange"}>{order[4]}</Badge></div>)}</div></Card><Card><div className="border-b border-[#e7e7e7] px-5 py-4"><h2 className="text-sm font-semibold">系统状态</h2></div><div className="space-y-4 p-5">{[["任务 Worker","在线 · 3 个节点"],["Epay 网关","响应正常"],["MySQL 8.0","连接池稳定"],["最近失败率","0.8% · 正常"]].map(([label,value])=><div className="flex items-center justify-between text-xs" key={label}><span className="text-[#777]">{label}</span><span className="flex items-center gap-2 font-medium"><span className="h-1.5 w-1.5 rounded-full bg-[#3eaa5d]"/>{value}</span></div>)}</div></Card></div></div>;
}

export function ConsoleShell() {
  const [active, setActive] = useState<View>("overview");
  const [mobileOpen, setMobileOpen] = useState(false);
  const titles: Record<View, string> = { overview: "概览", tasks: "任务中心", accounts: "抖音资源", billing: "订阅与账单", keys: "API 密钥", admin: "管理控制台" };
  const [newTask, setNewTask] = useState(false);
  return <div className="flex min-h-screen"><div className="hidden md:block"><SideNav active={active} onSelect={setActive}/></div>{mobileOpen && <div className="fixed inset-0 z-40 flex md:hidden"><button className="absolute inset-0 bg-black/20" aria-label="关闭菜单" onClick={() => setMobileOpen(false)}/><div className="relative z-10 h-full"><SideNav active={active} onSelect={setActive} onClose={() => setMobileOpen(false)}/></div></div>}<main className="min-w-0 flex-1"><Topbar title={titles[active]} onMenu={() => setMobileOpen(true)}/><div className="grid-paper min-h-[calc(100vh-72px)] p-5 sm:p-8"><div className="mx-auto max-w-[1280px]">{active === "overview" && <Overview onSelect={setActive}/>} {active === "tasks" && <div className="space-y-6"><div className="flex items-end justify-between"><div><h2 className="text-sm font-semibold">任务中心</h2><p className="mt-1 text-xs text-[#909090]">创建、调度并监控你的自动化任务。</p></div><Button onClick={() => setNewTask((value) => !value)}><Plus size={14}/> {newTask ? "收起表单" : "新建任务"}</Button></div>{newTask && <Card><TaskForm onCreated={() => setNewTask(false)} /></Card>}<Card><TaskTable /></Card></div>} {active === "accounts" && <Accounts />} {active === "billing" && <Billing />} {active === "keys" && <Keys />} {active === "admin" && <Admin />}</div></div></main></div>;
}
