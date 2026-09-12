import { z } from "zod";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "/api/backend";

export const taskInputSchema = z.object({
  account_id: z.string().min(1),
  name: z.string().min(1).max(80),
  targets: z.array(z.string().min(1)).min(1),
  message: z.string().min(1).max(2000),
  hitokoto_types: z.array(z.string()).default([]),
  schedule_time: z.string().regex(/^(?:[01]\d|2[0-3]):[0-5]\d$/),
  timezone: z.string().default("Asia/Shanghai"),
  enabled: z.boolean().default(false),
});

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.detail?.message ?? body?.detail ?? "请求失败");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
