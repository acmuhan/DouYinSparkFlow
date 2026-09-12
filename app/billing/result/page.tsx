"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, CheckCircle2, Loader2, XCircle } from "lucide-react";
import { AuthGate } from "@/components/auth-gate";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

type Order = { id: string; status: string; amount_cents: number; cycle: string; created_at: string };

function ResultContent() {
  const orderId = typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("order");
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const id = orderId;
    if (!id) return;
    apiFetch<Order[]>("/billing/orders")
      .then((orders) => {
        const found = orders.find((item) => item.id === id);
        if (found) setOrder(found);
        else setError("订单不存在或不属于当前工作区");
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "订单查询失败"));
  }, [orderId]);
  const paid = order?.status === "PAID";
  const failed = order && ["FAILED", "EXPIRED", "REFUNDED"].includes(order.status);
  return <main className="grid min-h-screen place-items-center bg-[#fbfbfa] px-6"><Card className="w-full max-w-[520px] p-8 sm:p-12"><div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#f1f1ef]">{paid ? <CheckCircle2 className="text-[#287b42]" size={20} /> : failed ? <XCircle className="text-[#b43c2d]" size={20} /> : <Loader2 className="animate-spin text-[#777]" size={20} />}</div><p className="mt-8 font-mono text-[10px] uppercase tracking-[.2em] text-[#999]">Payment status</p><h1 className="mt-3 text-2xl font-semibold tracking-[-.05em]">{error || (!orderId ? "缺少订单编号" : paid ? "订阅已激活" : failed ? "订单未完成" : "正在确认支付")}</h1><p className="mt-4 text-sm leading-6 text-[#777]">{error || (order ? `订单 ${order.id.slice(0, 12)} · ¥${(order.amount_cents / 100).toFixed(2)} · ${order.status}` : "支付平台返回后，SparkFlow 会再次校验订单状态。")}</p>{order && !paid && !failed && <p className="mt-3 text-xs text-[#999]">如果刚完成支付，请稍候刷新此页面。</p>}<div className="mt-8 flex gap-2"><Link href="/" className="flex-1"><Button className="w-full"><ArrowLeft size={14} />返回控制台</Button></Link><Link href={orderId ? `/billing/result?order=${encodeURIComponent(orderId)}` : "/billing/result"} className="flex-1"><Button variant="outline" className="w-full">重新查询</Button></Link></div></Card></main>;
}

export default function BillingResultPage() {
  return <AuthGate><ResultContent /></AuthGate>;
}
