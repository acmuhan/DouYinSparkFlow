import { z } from "zod";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "/api/backend";

export const taskInputSchema = z.object({
  account_id: z.string().min(1).nullable().default(null),
  plugin_id: z.string().default("douyin_streak"),
  name: z.string().min(1).max(80),
  targets: z.array(z.string().min(1)).max(100).default([]),
  message: z.string().max(2000).default(""),
  plugin_config: z.record(z.string(), z.unknown()).optional(),
  hitokoto_types: z.array(z.string()).default([]),
  schedule_time: z.string().regex(/^(?:[01]\d|2[0-3]):[0-5]\d$/),
  timezone: z.string().default("Asia/Shanghai"),
  enabled: z.boolean().default(false),
}).superRefine((value, ctx) => {
  if (value.plugin_id === "douyin_streak" && !value.plugin_config &&
      (!value.account_id || !value.targets.length || !value.message.trim())) {
    ctx.addIssue({ code: "custom", message: "请选择资源、目标好友并填写消息" });
  }
});

export type User = { id: string; email: string; name: string; role: "USER" | "ADMIN"; status: string; last_login_at?: string | null };
export type Plan = {
  id: string; slug: string; name: string; description: string;
  monthly_cents: number; quarterly_cents: number; yearly_cents: number;
  account_limit: number; task_limit: number; run_limit: number; features: string[];
  plugin_permissions: string[] | null;
  permissions: string[] | null;
  active: boolean; sort_order: number;
};
export type Subscription = { id: string; plan_id: string; snapshot: Record<string, unknown>; expires_at: string | null; updated_at: string };
export type Usage = { period: string; used: number; adjustment: number; limit: number; remaining: number };
export type Account = {
  id: string; name: string; unique_id: string; status: string; created_at: string; updated_at: string;
  inspection_status: string | null; inspection_message: string | null; checked_at: string | null;
};
export type Friend = { id: string; name: string; unique_id: string };
export type FriendList = { items: Friend[]; inspection_status: string | null; checked_at: string | null; complete: boolean };
export type ApiKey = { id: string; name: string; prefix: string; expires_at: string; revoked_at: string | null; created_at: string; token?: string | null };

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body?.detail;
    if (Array.isArray(detail)) {
      // Validation payloads can echo secrets in `input`/`ctx`; show messages only.
      throw new Error(detail.map((item) => `${Array.isArray(item.loc) ? item.loc.slice(1).join(".") : ""}: ${typeof item.msg === "string" ? item.msg : "字段无效"}`).join("; "));
    }
    throw new Error(detail?.message ?? (typeof detail === "string" ? detail : "请求失败"));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
