"use client";

import { FormEvent, useEffect, useState } from "react";
import { Check, Loader2, RefreshCw, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Plan, User, apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

type AdminOverview = { users: number; active_users: number; orders: number; paid_orders: number; order_conversion_rate: number; gross_cents: number; queued_runs: number; failed_runs: number };
type AdminUser = User & { subscription: { plan_id: string; snapshot: Record<string, unknown>; expires_at: string | null } | null };
type AdminOrder = { id: string; plan_id: string; cycle: string; amount_cents: number; status: string; provider_trade_no: string | null; created_at: string };
type AdminRun = { id: string; task_id: string; status: string; trigger_type: string; sent_count: number; result: string | null; cancel_requested: boolean; worker_id: string | null; created_at: string; finished_at: string | null };
type Worker = { id: string; heartbeat_at: string; status: string };
type AuditLog = { id: string; actor_id: string | null; action: string; target_id: string | null; detail: Record<string, unknown>; created_at: string };
type Refund = { id: string; order_id: string; status: string; amount_cents: number; reason: string; provider_refund_no: string | null; error: string | null; created_at: string; updated_at: string };
type Section = "users" | "plans" | "orders" | "runs" | "audit";

const sections: { id: Section; label: string }[] = [
  { id: "users", label: "用户与配额" },
  { id: "plans", label: "套餐配置" },
  { id: "orders", label: "订单审计" },
  { id: "runs", label: "运行调度" },
  { id: "audit", label: "系统日志" },
];

function statusTone(status: string) {
  if (["ACTIVE", "PAID", "SUCCEEDED", "ONLINE"].includes(status)) return "green" as const;
  if (["PENDING", "QUEUED", "RUNNING", "CLAIMED"].includes(status)) return "orange" as const;
  return "red" as const;
}

function UserRow({ user, plans, onChanged }: { user: AdminUser; plans: Plan[]; onChanged: () => Promise<void> }) {
  const [status, setStatus] = useState(user.status);
  const [planId, setPlanId] = useState(user.subscription?.plan_id ?? plans[0]?.id ?? "");
  const [months, setMonths] = useState("1");
  const [quota, setQuota] = useState("100");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  async function updateStatus(value: string) {
    setBusy("status"); setError("");
    try { await apiFetch(`/admin/users/${user.id}/status`, { method: "PATCH", body: JSON.stringify({ status: value }) }); setStatus(value); await onChanged(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "状态更新失败"); }
    finally { setBusy(""); }
  }
  async function updateSubscription(event: FormEvent) {
    event.preventDefault(); setBusy("subscription"); setError("");
    try { await apiFetch(`/admin/users/${user.id}/subscription`, { method: "PATCH", body: JSON.stringify({ plan_id: planId, months: Number(months), reason: "管理员控制台调整" }) }); await onChanged(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "订阅调整失败"); }
    finally { setBusy(""); }
  }
  async function adjustQuota(event: FormEvent) {
    event.preventDefault(); setBusy("quota"); setError("");
    try { await apiFetch(`/admin/users/${user.id}/quota-adjustments`, { method: "POST", body: JSON.stringify({ period: new Date().toISOString().slice(0, 7), amount: Number(quota), reason: "管理员控制台调整" }) }); setQuota("100"); await onChanged(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "配额调整失败"); }
    finally { setBusy(""); }
  }
  return <tr className="align-top hover:bg-[#fcfcfb]"><td className="px-4 py-4"><div className="font-medium">{user.name}</div><div className="mt-1 text-[11px] text-[#888]">{user.email}</div></td><td className="px-4 py-4"><Badge tone={statusTone(status)}>{status}</Badge><select aria-label={`${user.email} 状态`} value={status} disabled={busy === "status"} onChange={(event) => void updateStatus(event.target.value)} className="mt-2 block h-8 rounded-[5px] border border-[#dcdcd9] bg-white px-2 text-xs"><option value="ACTIVE">ACTIVE</option><option value="SUSPENDED">SUSPENDED</option><option value="BANNED">BANNED</option></select></td><td className="px-4 py-4 text-xs text-[#666]">{user.subscription?.expires_at ? new Date(user.subscription.expires_at).toLocaleDateString("zh-CN") : "未订阅"}</td><td className="min-w-[310px] px-4 py-4"><form onSubmit={updateSubscription} className="flex flex-wrap gap-2"><select aria-label={`${user.email} 订阅套餐`} required value={planId} onChange={(event) => setPlanId(event.target.value)} className="h-8 min-w-[120px] rounded-[5px] border border-[#dcdcd9] bg-white px-2 text-xs"><option value="">选择套餐</option>{plans.map((plan) => <option value={plan.id} key={plan.id}>{plan.name}</option>)}</select><input aria-label={`${user.email} 订阅月数`} required min="1" max="120" type="number" value={months} onChange={(event) => setMonths(event.target.value)} className="h-8 w-16 rounded-[5px] border border-[#dcdcd9] px-2 text-xs" /><Button size="sm" variant="outline" type="submit" disabled={busy !== ""}>订阅</Button></form><form onSubmit={adjustQuota} className="mt-2 flex gap-2"><input aria-label={`${user.email} 配额调整`} required type="number" value={quota} onChange={(event) => setQuota(event.target.value)} className="h-8 w-20 rounded-[5px] border border-[#dcdcd9] px-2 text-xs" /><Button size="sm" variant="outline" type="submit" disabled={busy !== ""}>调整本月配额</Button></form>{error && <p className="mt-2 text-[11px] text-[#b43c2d]">{error}</p>}</td></tr>;
}

function PlanRow({ plan, onChanged }: { plan: Plan; onChanged: () => Promise<void> }) {
  const [draft, setDraft] = useState({ name: plan.name, description: plan.description, monthly_cents: plan.monthly_cents, quarterly_cents: plan.quarterly_cents, yearly_cents: plan.yearly_cents, account_limit: plan.account_limit, task_limit: plan.task_limit, run_limit: plan.run_limit, features: plan.features.join(", "), active: plan.active, sort_order: plan.sort_order });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setMessage("");
    try { await apiFetch(`/admin/plans/${plan.id}`, { method: "PATCH", body: JSON.stringify({ ...draft, features: draft.features.split(/[,，\n]/).map((item) => item.trim()).filter(Boolean) }) }); setMessage("已保存"); await onChanged(); }
    catch (reason) { setMessage(reason instanceof Error ? reason.message : "保存失败"); }
    finally { setBusy(false); }
  }
  return <form onSubmit={save} className="grid gap-3 border-b border-[#eeeeec] p-5 last:border-b-0 md:grid-cols-4"><div className="md:col-span-2"><label className="text-xs font-medium">套餐名称<input required value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} className="mt-2 h-9 w-full rounded-[5px] border border-[#dcdcd9] px-3 text-sm" /></label><label className="mt-3 block text-xs font-medium">说明<input value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} className="mt-2 h-9 w-full rounded-[5px] border border-[#dcdcd9] px-3 text-xs" /></label></div><div className="grid grid-cols-3 gap-2"><label className="text-[11px] text-[#666]">月付<input type="number" min="1" value={draft.monthly_cents} onChange={(event) => setDraft({ ...draft, monthly_cents: Number(event.target.value) })} className="mt-2 h-9 w-full rounded-[5px] border border-[#dcdcd9] px-2 text-xs" /></label><label className="text-[11px] text-[#666]">季付<input type="number" min="1" value={draft.quarterly_cents} onChange={(event) => setDraft({ ...draft, quarterly_cents: Number(event.target.value) })} className="mt-2 h-9 w-full rounded-[5px] border border-[#dcdcd9] px-2 text-xs" /></label><label className="text-[11px] text-[#666]">年付<input type="number" min="1" value={draft.yearly_cents} onChange={(event) => setDraft({ ...draft, yearly_cents: Number(event.target.value) })} className="mt-2 h-9 w-full rounded-[5px] border border-[#dcdcd9] px-2 text-xs" /></label></div><div className="grid grid-cols-3 gap-2"><label className="text-[11px] text-[#666]">账号上限<input type="number" min="1" value={draft.account_limit} onChange={(event) => setDraft({ ...draft, account_limit: Number(event.target.value) })} className="mt-2 h-9 w-full rounded-[5px] border border-[#dcdcd9] px-2 text-xs" /></label><label className="text-[11px] text-[#666]">任务上限<input type="number" min="1" value={draft.task_limit} onChange={(event) => setDraft({ ...draft, task_limit: Number(event.target.value) })} className="mt-2 h-9 w-full rounded-[5px] border border-[#dcdcd9] px-2 text-xs" /></label><label className="text-[11px] text-[#666]">运行额度<input type="number" min="1" value={draft.run_limit} onChange={(event) => setDraft({ ...draft, run_limit: Number(event.target.value) })} className="mt-2 h-9 w-full rounded-[5px] border border-[#dcdcd9] px-2 text-xs" /></label></div><div className="md:col-span-3"><label className="text-xs font-medium">权益标签<input value={draft.features} onChange={(event) => setDraft({ ...draft, features: event.target.value })} className="mt-2 h-9 w-full rounded-[5px] border border-[#dcdcd9] px-3 text-xs" /></label></div><div className="flex items-end justify-between gap-3"><label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={draft.active} onChange={(event) => setDraft({ ...draft, active: event.target.checked })} />启用</label><Button size="sm" type="submit" disabled={busy}>{busy ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}保存</Button></div>{message && <p className={cn("text-[11px] md:col-span-4", message === "已保存" ? "text-[#287b42]" : "text-[#b43c2d]")}>{message}</p>}</form>;
}

function OrderRow({ order, refund, onChanged, onError }: { order: AdminOrder; refund?: Refund; onChanged: () => Promise<void>; onError: (message: string) => void }) {
  const [mode, setMode] = useState<"reconcile" | "refund" | "complete" | null>(null);
  const [tradeNo, setTradeNo] = useState("");
  const [providerMoney, setProviderMoney] = useState((order.amount_cents / 100).toFixed(2));
  const [reason, setReason] = useState("管理员处理");
  const [refundNo, setRefundNo] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true);
    try {
      if (mode === "reconcile") await apiFetch(`/admin/orders/${order.id}/reconcile`, { method: "POST", body: JSON.stringify({ provider_trade_no: tradeNo, provider_money: providerMoney, reason }) });
      if (mode === "refund") await apiFetch(`/admin/orders/${order.id}/refund`, { method: "POST", body: JSON.stringify({ reason }) });
      if (mode === "complete" && refund) await apiFetch(`/admin/refunds/${refund.id}`, { method: "PATCH", body: JSON.stringify({ status: refundNo ? "SUCCEEDED" : "FAILED", provider_refund_no: refundNo || null, error: refundNo ? null : reason }) });
      setMode(null); await onChanged();
    } catch (failure) { onError(failure instanceof Error ? failure.message : "订单操作失败"); }
    finally { setBusy(false); }
  }
  return <tr><td className="px-4 py-4"><span className="font-mono">{order.id.slice(0, 12)}</span><span className="ml-2 text-[#888]">{order.cycle}</span><div className="mt-1 text-[11px] text-[#999]">{new Date(order.created_at).toLocaleString("zh-CN")}</div></td><td className="px-4 py-4 font-mono">¥{(order.amount_cents / 100).toFixed(2)}</td><td className="px-4 py-4"><Badge tone={statusTone(order.status)}>{order.status}</Badge>{refund && <div className="mt-1 text-[11px] text-[#888]">退款：{refund.status}</div>}</td><td className="px-4 py-4"><div className="flex flex-wrap gap-2">{order.status === "PENDING" && <Button size="sm" variant="outline" onClick={() => setMode(mode === "reconcile" ? null : "reconcile")}>补单</Button>}{order.status === "PAID" && <Button size="sm" variant="danger" onClick={() => setMode(mode === "refund" ? null : "refund")}>申请退款</Button>}{refund?.status === "PENDING" && <Button size="sm" variant="outline" onClick={() => setMode(mode === "complete" ? null : "complete")}>完成退款</Button>}</div>{mode && <form onSubmit={submit} className="mt-3 grid max-w-[360px] gap-2 rounded-[5px] border border-[#e7e7e7] bg-[#fcfcfb] p-3">{mode === "reconcile" && <><input required value={tradeNo} onChange={(event) => setTradeNo(event.target.value)} placeholder="支付平台流水号" className="h-8 rounded-[5px] border border-[#dcdcd9] px-2 text-xs" /><input required pattern="^\\d+(?:\\.\\d{1,2})?$" value={providerMoney} onChange={(event) => setProviderMoney(event.target.value)} placeholder="支付金额" className="h-8 rounded-[5px] border border-[#dcdcd9] px-2 text-xs" /></>}{mode === "complete" && <input value={refundNo} onChange={(event) => setRefundNo(event.target.value)} placeholder="退款平台流水号（留空标记失败）" className="h-8 rounded-[5px] border border-[#dcdcd9] px-2 text-xs" />}<input required value={reason} onChange={(event) => setReason(event.target.value)} placeholder="处理原因" className="h-8 rounded-[5px] border border-[#dcdcd9] px-2 text-xs" /><Button size="sm" type="submit" disabled={busy}>{busy ? <Loader2 size={13} className="animate-spin" /> : "确认"}</Button></form>}</td></tr>;
}

export function AdminConsole() {
  const [section, setSection] = useState<Section>("users");
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [orders, setOrders] = useState<AdminOrder[]>([]);
  const [refunds, setRefunds] = useState<Refund[]>([]);
  const [runs, setRuns] = useState<AdminRun[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  async function load() {
    setRefreshing(true); setError("");
    try {
      const [nextOverview, nextUsers, nextPlans, nextOrders, nextRefunds, nextRuns, nextWorkers, nextLogs] = await Promise.all([
        apiFetch<AdminOverview>("/admin/overview"), apiFetch<AdminUser[]>("/admin/users"), apiFetch<Plan[]>("/admin/plans"),
        apiFetch<AdminOrder[]>("/admin/orders"), apiFetch<Refund[]>("/admin/refunds"), apiFetch<AdminRun[]>("/admin/runs"), apiFetch<Worker[]>("/admin/workers"),
        apiFetch<AuditLog[]>("/admin/audit-logs"),
      ]);
      setOverview(nextOverview); setUsers(nextUsers); setPlans(nextPlans); setOrders(nextOrders); setRefunds(nextRefunds); setRuns(nextRuns); setWorkers(nextWorkers); setLogs(nextLogs);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "管理数据加载失败"); }
    finally { setRefreshing(false); }
  }
  useEffect(() => {
    Promise.all([
      apiFetch<AdminOverview>("/admin/overview"), apiFetch<AdminUser[]>("/admin/users"), apiFetch<Plan[]>("/admin/plans"),
      apiFetch<AdminOrder[]>("/admin/orders"), apiFetch<Refund[]>("/admin/refunds"), apiFetch<AdminRun[]>("/admin/runs"), apiFetch<Worker[]>("/admin/workers"),
      apiFetch<AuditLog[]>("/admin/audit-logs"),
    ]).then(([nextOverview, nextUsers, nextPlans, nextOrders, nextRefunds, nextRuns, nextWorkers, nextLogs]) => {
      setOverview(nextOverview); setUsers(nextUsers); setPlans(nextPlans); setOrders(nextOrders); setRefunds(nextRefunds); setRuns(nextRuns); setWorkers(nextWorkers); setLogs(nextLogs);
    }).catch((reason) => setError(reason instanceof Error ? reason.message : "管理数据加载失败"));
  }, []);
  async function updateRun(run: AdminRun, status: "QUEUED" | "CANCELLED") {
    setError("");
    try { await apiFetch(`/admin/runs/${run.id}`, { method: "PATCH", body: JSON.stringify({ status, reason: status === "QUEUED" ? "管理员重新入队" : "管理员取消运行" }) }); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "运行状态更新失败"); }
  }
  const onlineWorkers = workers.filter((worker) => worker.status === "ONLINE").length;
  return <div className="space-y-6"><div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-sm font-semibold">管理控制台</h2><p className="mt-1 text-xs text-[#909090]">用户、套餐、订单、运行调度与审计均来自受保护的 ADMIN API。</p></div><Button variant="outline" size="sm" onClick={() => void load()} disabled={refreshing}>{refreshing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}刷新</Button></div>{error && <p role="alert" className="border border-[#f0c4be] bg-[#fff7f5] px-3 py-2 text-xs text-[#b43c2d]">{error}</p>}<div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><Card className="p-5"><p className="text-xs text-[#858585]">总用户 / 活跃</p><p className="mt-3 text-2xl font-semibold">{overview?.users.toLocaleString() ?? "—"} <span className="text-sm font-normal text-[#888]">/ {overview?.active_users.toLocaleString() ?? "—"}</span></p></Card><Card className="p-5"><p className="text-xs text-[#858585]">已支付流水</p><p className="mt-3 text-2xl font-semibold">¥{overview ? (overview.gross_cents / 100).toFixed(2) : "—"}</p><p className="mt-1 text-[11px] text-[#888]">{overview?.paid_orders.toLocaleString() ?? "—"} 笔订单</p></Card><Card className="p-5"><p className="text-xs text-[#858585]">订单转化率</p><p className="mt-3 text-2xl font-semibold">{overview ? `${overview.order_conversion_rate.toFixed(2)}%` : "—"}</p><p className="mt-1 text-[11px] text-[#888]">{overview?.paid_orders.toLocaleString() ?? "—"} / {overview?.orders.toLocaleString() ?? "—"} 已支付</p></Card><Card className="p-5"><p className="text-xs text-[#858585]">运行队列 / 失败</p><p className="mt-3 text-2xl font-semibold">{overview?.queued_runs.toLocaleString() ?? "—"} <span className="text-sm font-normal text-[#b43c2d]">/ {overview?.failed_runs.toLocaleString() ?? "—"}</span></p></Card><Card className="p-5"><p className="text-xs text-[#858585]">Worker 在线</p><p className="mt-3 text-2xl font-semibold">{onlineWorkers} <span className="text-sm font-normal text-[#888]">/ {workers.length}</span></p></Card></div><div className="flex flex-wrap gap-1 border-b border-[#e7e7e7]">{sections.map((item) => <button key={item.id} onClick={() => setSection(item.id)} className={cn("border-b-2 px-3 py-3 text-xs font-medium", section === item.id ? "border-[#161616] text-[#161616]" : "border-transparent text-[#888] hover:text-[#161616]")}>{item.label}</button>)}</div>{section === "users" && <Card className="overflow-x-auto"><table className="w-full min-w-[850px] text-left text-xs"><thead className="bg-[#fafaf9] text-[10px] uppercase tracking-[.12em] text-[#989898]"><tr><th className="px-4 py-3">用户</th><th className="px-4 py-3">状态</th><th className="px-4 py-3">订阅到期</th><th className="px-4 py-3">管理员操作</th></tr></thead><tbody className="divide-y divide-[#eeeeec]">{users.map((user) => <UserRow key={user.id} user={user} plans={plans} onChanged={load} />)}{users.length === 0 && <tr><td colSpan={4} className="px-4 py-10 text-center text-xs text-[#999]">暂无用户</td></tr>}</tbody></table></Card>}{section === "plans" && <Card><div className="border-b border-[#e7e7e7] px-5 py-4"><h3 className="text-sm font-semibold">套餐与权益</h3><p className="mt-1 text-xs text-[#888]">金额单位为分，权益标签用逗号分隔。</p></div>{plans.map((plan) => <PlanRow key={plan.id} plan={plan} onChanged={load} />)}</Card>}{section === "orders" && <Card className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-xs"><thead className="bg-[#fafaf9] text-[10px] uppercase tracking-[.12em] text-[#989898]"><tr><th className="px-4 py-3">订单</th><th className="px-4 py-3">金额</th><th className="px-4 py-3">状态</th><th className="px-4 py-3">操作</th></tr></thead><tbody className="divide-y divide-[#eeeeec]">{orders.map((order) => <OrderRow key={order.id} order={order} refund={refunds.find((item) => item.order_id === order.id)} onChanged={load} onError={setError} />)}{orders.length === 0 && <tr><td colSpan={4} className="px-4 py-10 text-center text-xs text-[#999]">暂无订单</td></tr>}</tbody></table></Card>}{section === "runs" && <Card className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-xs"><thead className="bg-[#fafaf9] text-[10px] uppercase tracking-[.12em] text-[#989898]"><tr><th className="px-4 py-3">运行</th><th className="px-4 py-3">状态</th><th className="px-4 py-3">发送数</th><th className="px-4 py-3">操作</th></tr></thead><tbody className="divide-y divide-[#eeeeec]">{runs.map((run) => <tr key={run.id}><td className="px-4 py-4"><span className="font-mono">{run.id.slice(0, 12)}</span><div className="mt-1 text-[11px] text-[#999]">任务 {run.task_id.slice(0, 12)} · {run.trigger_type}</div></td><td className="px-4 py-4"><Badge tone={statusTone(run.status)}>{run.status}</Badge></td><td className="px-4 py-4">{run.sent_count}</td><td className="px-4 py-4"><div className="flex gap-2">{["QUEUED", "CLAIMED", "RUNNING"].includes(run.status) && <Button size="sm" variant="danger" onClick={() => void updateRun(run, "CANCELLED")}><XCircle size={13} />取消</Button>}{["FAILED", "CANCELLED"].includes(run.status) && <Button size="sm" variant="outline" onClick={() => void updateRun(run, "QUEUED")}>重新入队</Button>}</div></td></tr>)}{runs.length === 0 && <tr><td colSpan={4} className="px-4 py-10 text-center text-xs text-[#999]">暂无运行记录</td></tr>}</tbody></table></Card>}{section === "audit" && <Card className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-xs"><thead className="bg-[#fafaf9] text-[10px] uppercase tracking-[.12em] text-[#989898]"><tr><th className="px-4 py-3">时间</th><th className="px-4 py-3">动作</th><th className="px-4 py-3">目标</th><th className="px-4 py-3">详情</th></tr></thead><tbody className="divide-y divide-[#eeeeec]">{logs.map((log) => <tr key={log.id}><td className="whitespace-nowrap px-4 py-4 text-[#777]">{new Date(log.created_at).toLocaleString("zh-CN")}</td><td className="px-4 py-4 font-mono text-[11px]">{log.action}</td><td className="px-4 py-4 font-mono text-[11px]">{log.target_id?.slice(0, 16) ?? "—"}</td><td className="max-w-[360px] truncate px-4 py-4 font-mono text-[11px] text-[#777]">{JSON.stringify(log.detail)}</td></tr>)}{logs.length === 0 && <tr><td colSpan={4} className="px-4 py-10 text-center text-xs text-[#999]">暂无审计日志</td></tr>}</tbody></table></Card>}</div>;
}
