import { sql } from "drizzle-orm";
import { mysqlTable, varchar, int, text, json, datetime, boolean, uniqueIndex, index } from "drizzle-orm/mysql-core";

const id = () => varchar("id", { length: 36 }).primaryKey();
const at = (name: string) => datetime(name, { mode: "date", fsp: 3 });
const created = () => at("created_at").notNull().default(sql`CURRENT_TIMESTAMP(3)`);

export const users = mysqlTable("users", {
  id: id(),
  email: varchar("email", { length: 254 }).notNull().unique(),
  name: varchar("name", { length: 80 }).notNull(),
  passwordHash: varchar("password_hash", { length: 255 }).notNull(),
  role: varchar("role", { length: 16 }).notNull().default("USER"),
  status: varchar("status", { length: 16 }).notNull().default("ACTIVE"),
  lastLoginAt: at("last_login_at"),
  createdAt: created(),
});
export const sessions = mysqlTable("sessions", {
  id: varchar("id", { length: 64 }).primaryKey(),
  userId: varchar("user_id", { length: 36 }).notNull().references(() => users.id),
  expiresAt: at("expires_at").notNull(),
  createdAt: created(),
});
export const plans = mysqlTable("plans", {
  id: id(),
  slug: varchar("slug", { length: 40 }).notNull().unique(),
  name: varchar("name", { length: 80 }).notNull(),
  description: varchar("description", { length: 255 }).notNull(),
  monthlyCents: int("monthly_cents").notNull(),
  quarterlyCents: int("quarterly_cents").notNull(),
  yearlyCents: int("yearly_cents").notNull(),
  accountLimit: int("account_limit").notNull(),
  taskLimit: int("task_limit").notNull(),
  runLimit: int("run_limit").notNull(),
  features: json("features").$type<string[]>().notNull(),
  active: boolean("active").notNull().default(true),
  sortOrder: int("sort_order").notNull().default(0),
  createdAt: created(),
});
export const subscriptions = mysqlTable("subscriptions", {
  id: id(),
  userId: varchar("user_id", { length: 36 }).notNull().unique().references(() => users.id),
  planId: varchar("plan_id", { length: 36 }).notNull().references(() => plans.id),
  snapshot: json("snapshot").notNull(),
  expiresAt: at("expires_at"),
  lastOrderId: varchar("last_order_id", { length: 36 }),
  updatedAt: at("updated_at").notNull(),
});
export const orders = mysqlTable("orders", {
  id: id(),
  userId: varchar("user_id", { length: 36 }).notNull().references(() => users.id),
  planId: varchar("plan_id", { length: 36 }).notNull().references(() => plans.id),
  snapshot: json("snapshot").notNull(),
  cycle: varchar("cycle", { length: 16 }).notNull(),
  months: int("months").notNull(),
  amountCents: int("amount_cents").notNull(),
  status: varchar("status", { length: 16 }).notNull().default("PENDING"),
  providerVersion: varchar("provider_version", { length: 4 }).notNull(),
  providerTradeNo: varchar("provider_trade_no", { length: 128 }).unique(),
  merchantId: varchar("merchant_id", { length: 64 }).notNull(),
  paymentMethod: varchar("payment_method", { length: 16 }).notNull(),
  idempotencyKey: varchar("idempotency_key", { length: 64 }).notNull(),
  checkout: json("checkout"),
  subscriptionBefore: json("subscription_before"),
  expiresAt: at("expires_at").notNull(),
  paidAt: at("paid_at"),
  createdAt: created(),
}, (t) => [uniqueIndex("orders_user_idempotency").on(t.userId, t.idempotencyKey), index("orders_status_expires").on(t.status, t.expiresAt)]);
export const refunds = mysqlTable("refunds", {
  id: id(),
  orderId: varchar("order_id", { length: 36 }).notNull().unique().references(() => orders.id),
  status: varchar("status", { length: 16 }).notNull(),
  amountCents: int("amount_cents").notNull(),
  reason: varchar("reason", { length: 255 }).notNull(),
  providerRefundNo: varchar("provider_refund_no", { length: 128 }),
  error: varchar("error", { length: 255 }),
  createdAt: created(),
  updatedAt: at("updated_at").notNull(),
});
export const accounts = mysqlTable("accounts", {
  id: id(),
  userId: varchar("user_id", { length: 36 }).notNull().references(() => users.id),
  name: varchar("name", { length: 80 }).notNull(),
  uniqueId: varchar("unique_id", { length: 80 }).notNull(),
  cookiesEncrypted: text("cookies_encrypted").notNull(),
  status: varchar("status", { length: 16 }).notNull().default("READY"),
  createdAt: created(),
  updatedAt: at("updated_at").notNull(),
}, (t) => [uniqueIndex("accounts_user_unique").on(t.userId, t.uniqueId)]);
export const tasks = mysqlTable("tasks", {
  id: id(),
  userId: varchar("user_id", { length: 36 }).notNull().references(() => users.id),
  accountId: varchar("account_id", { length: 36 }).notNull().references(() => accounts.id),
  name: varchar("name", { length: 80 }).notNull(),
  targets: json("targets").$type<string[]>().notNull(),
  message: text("message").notNull(),
  hitokotoTypes: json("hitokoto_types").$type<string[]>().notNull(),
  scheduleTime: varchar("schedule_time", { length: 5 }).notNull(),
  timezone: varchar("timezone", { length: 64 }).notNull(),
  enabled: boolean("enabled").notNull().default(false),
  archived: boolean("archived").notNull().default(false),
  nextRunAt: at("next_run_at"),
  createdAt: created(),
  updatedAt: at("updated_at").notNull(),
});
export const runs = mysqlTable("runs", {
  id: id(),
  userId: varchar("user_id", { length: 36 }).notNull().references(() => users.id),
  taskId: varchar("task_id", { length: 36 }).notNull().references(() => tasks.id),
  status: varchar("status", { length: 16 }).notNull().default("QUEUED"),
  triggerType: varchar("trigger_type", { length: 16 }).notNull(),
  snapshot: json("snapshot").notNull(),
  sentCount: int("sent_count").notNull().default(0),
  result: text("result"),
  cancelRequested: boolean("cancel_requested").notNull().default(false),
  workerId: varchar("worker_id", { length: 64 }),
  leaseUntil: at("lease_until"),
  startedAt: at("started_at"),
  finishedAt: at("finished_at"),
  createdAt: created(),
}, (t) => [index("runs_status_created").on(t.status, t.createdAt), index("runs_user_created").on(t.userId, t.createdAt)]);
export const usage = mysqlTable("usage", {
  id: id(),
  userId: varchar("user_id", { length: 36 }).notNull().references(() => users.id),
  period: varchar("period", { length: 7 }).notNull(),
  used: int("used").notNull().default(0),
  adjustment: int("adjustment").notNull().default(0),
}, (t) => [uniqueIndex("usage_user_period").on(t.userId, t.period)]);
export const apiKeys = mysqlTable("api_keys", {
  id: id(),
  userId: varchar("user_id", { length: 36 }).notNull().references(() => users.id),
  name: varchar("name", { length: 80 }).notNull(),
  prefix: varchar("prefix", { length: 16 }).notNull(),
  tokenHash: varchar("token_hash", { length: 64 }).notNull().unique(),
  lastUsedAt: at("last_used_at"),
  expiresAt: at("expires_at").notNull(),
  revokedAt: at("revoked_at"),
  createdAt: created(),
});
export const auditLogs = mysqlTable("audit_logs", {
  id: id(),
  actorId: varchar("actor_id", { length: 36 }),
  action: varchar("action", { length: 80 }).notNull(),
  targetId: varchar("target_id", { length: 128 }),
  detail: json("detail").notNull(),
  createdAt: created(),
}, (t) => [index("audit_created").on(t.createdAt)]);
export const rateLimits = mysqlTable("rate_limits", {
  id: varchar("id", { length: 64 }).primaryKey(),
  attempts: int("attempts").notNull(),
  expiresAt: at("expires_at").notNull(),
});
export const workers = mysqlTable("workers", {
  id: varchar("id", { length: 64 }).primaryKey(),
  heartbeatAt: at("heartbeat_at").notNull(),
  status: varchar("status", { length: 16 }).notNull(),
});
