import { cn } from "@/lib/utils";

export function Card({ children, className, ...props }: React.HTMLAttributes<HTMLElement>) {
  return <section className={cn("border border-[#e7e7e7] bg-white", className)} {...props}>{children}</section>;
}
