import Link from "next/link";
import { Sparkles } from "lucide-react";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return <main className="grid min-h-screen lg:grid-cols-[.85fr_1.15fr]">
    <div className="grid-paper hidden flex-col justify-between border-r border-[#e7e7e7] bg-[#f6f6f4] p-10 lg:flex">
      <Link href="/" className="flex items-center gap-2.5 text-sm font-semibold tracking-[-.03em]"><span className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-[#161616] text-white"><Sparkles size={14}/></span>sparkflow</Link>
      <div className="max-w-[360px]"><p className="font-mono text-[11px] uppercase tracking-[.2em] text-[#8d8d8d]">Automation workspace</p><h1 className="mt-5 text-[38px] font-semibold leading-[1.05] tracking-[-.06em]">让每一次互动，<br/>都准时发生。</h1><p className="mt-5 text-sm leading-6 text-[#6f6f6f]">统一管理账号、任务和订阅，把重复的沟通交给可靠的工作流。</p></div>
      <p className="text-[11px] text-[#999]">© 2026 SparkFlow · Built for focused teams</p>
    </div>
    <div className="flex items-center justify-center bg-white px-6 py-12"><div className="w-full max-w-[390px]">{children}</div></div>
  </main>;
}
