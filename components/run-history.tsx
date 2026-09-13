"use client";

import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { List, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";

type Run = { id: string; task_id: string; status: string; sent_count: number; result: string | null; created_at: string };
type Event = { id: string; code: string; message: string; sent_count: number; created_at: string };
const date = (value: string) => new Date(/[Zz]|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`).toLocaleString("zh-CN");

function RunDetails({ run }: { run: Run }) {
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState<Event[]>([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    if (!open) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const rows = await apiFetch<Event[]>(`/runs/${run.id}/events`);
        if (active) { setEvents(rows); setLoaded(true); setError(""); }
      } catch (reason) { if (active) setError(reason instanceof Error ? reason.message : "日志加载失败"); }
      finally { if (active) timer = setTimeout(() => void load(), 3000); }
    }
    void load();
    return () => { active = false; clearTimeout(timer); };
  }, [open, run.id]);
  return <Dialog.Root open={open} onOpenChange={setOpen}>
    <Dialog.Trigger asChild><Button variant="ghost" size="sm" title="执行详情" aria-label={`查看运行 ${run.id} 日志`}><List size={16} /></Button></Dialog.Trigger>
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-50 bg-black/25" />
      <Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col bg-white p-5 shadow-xl">
        <div className="flex items-center justify-between"><Dialog.Title className="text-base font-semibold">执行详情</Dialog.Title>
          <Dialog.Close asChild><Button variant="ghost" size="sm" title="关闭详情" aria-label="关闭详情"><X size={16} /></Button></Dialog.Close></div>
        <Dialog.Description className="mt-3 break-all font-mono text-xs text-[#777]">{run.id}</Dialog.Description>
        <p className="mt-3 text-sm">{run.status} · {run.sent_count} 次提交</p>
        {run.result && <p className="mt-3 break-words text-sm">{run.result}</p>}
        {error && <p role="alert" className="mt-3 text-xs text-red-700">{error}</p>}
        <ol className="mt-5 min-h-0 flex-1 overflow-y-auto">
          {events.map((event) => <li key={event.id} className="border-t border-[#e7e7e7] py-3">
            <time className="text-xs text-[#777]">{date(event.created_at)}</time>
            <p className="mt-2 text-sm">{event.message}</p>
            <p className="mt-1 text-xs text-[#777]">{event.code} · 累计 {event.sent_count} 次提交</p>
          </li>)}
          {!loaded && !error && <li className="text-sm text-[#777]">加载中</li>}
          {loaded && !events.length && <li className="text-sm text-[#777]">暂无阶段日志；旧运行记录仅保留结果摘要。</li>}
        </ol>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}

export function RunHistory({ refreshKey }: { refreshKey: number }) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const rows = await apiFetch<Run[]>("/runs");
        if (active) { setRuns(rows); setError(""); setLoaded(true); }
      } catch (reason) { if (active) setError(reason instanceof Error ? reason.message : "运行记录加载失败"); }
      finally { if (active) timer = setTimeout(() => void load(), 4000); }
    }
    void load();
    return () => { active = false; clearTimeout(timer); };
  }, [refreshKey]);
  return <section className="border-t border-[#e7e7e7]">
    <h2 className="px-5 py-4 text-sm font-semibold">执行记录</h2>
    {error && <p role="alert" className="px-5 py-3 text-xs text-red-700">{error}</p>}
    <ul className="divide-y divide-[#eeeeec]">{runs.map((run) => <li key={run.id} className="flex flex-wrap items-center gap-3 px-5 py-4 text-xs">
      <div className="min-w-0 flex-1"><p className="break-all font-mono">{run.id}</p><p className="mt-1 text-[#777]">任务 {run.task_id.slice(0, 12)} · {date(run.created_at)}</p>
        {run.result && <p className="mt-2 break-words text-[#666]">{run.result}</p>}</div>
      <span className={run.status === "FAILED" ? "text-red-700" : "text-[#666]"}>{run.status}</span>
      <span>{run.sent_count} 次</span><RunDetails run={run} />
    </li>)}</ul>
    {!loaded && !error && <p className="px-5 py-8 text-xs text-[#777]">加载中</p>}
    {loaded && !runs.length && <p className="px-5 py-8 text-xs text-[#777]">暂无运行记录</p>}
  </section>;
}
