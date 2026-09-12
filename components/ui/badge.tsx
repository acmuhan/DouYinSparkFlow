import { cn } from "@/lib/utils";

export function Badge({ children, tone = "neutral", className }: { children: React.ReactNode; tone?: "neutral" | "green" | "orange" | "red"; className?: string }) {
  return <span className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium", tone === "neutral" && "border-[#dedede] bg-[#f7f7f7] text-[#666]", tone === "green" && "border-[#b9e2c7] bg-[#effbf2] text-[#287b42]", tone === "orange" && "border-[#f3cf9d] bg-[#fff7e9] text-[#a65f0c]", tone === "red" && "border-[#f0c4be] bg-[#fff2f0] text-[#b43c2d]", className)}>{children}</span>;
}
