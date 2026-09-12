"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "solid" | "outline" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
};

export function Button({ className, variant = "solid", size = "md", ...props }: ButtonProps) {
  return <button className={cn(
    "inline-flex items-center justify-center gap-2 rounded-[6px] border text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 disabled:cursor-not-allowed disabled:opacity-50",
    variant === "solid" && "border-[#161616] bg-[#161616] text-white hover:bg-[#333]",
    variant === "outline" && "border-[#d8d8d8] bg-white text-[#161616] hover:border-[#161616]",
    variant === "ghost" && "border-transparent bg-transparent text-[#707070] hover:bg-[#f1f1ef] hover:text-[#161616]",
    variant === "danger" && "border-[#e8b8b0] bg-[#fff8f6] text-[#c53f27] hover:bg-[#fff0ec]",
    size === "sm" && "h-8 px-3 text-xs", size === "md" && "h-10 px-4", size === "lg" && "h-12 px-5",
    className,
  )} {...props} />;
}
