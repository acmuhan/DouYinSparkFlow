import { cn } from "@/lib/utils";

export function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <section className={cn("border border-[#e7e7e7] bg-white", className)}>{children}</section>;
}
