import { readFileSync } from "node:fs";
import { type Connection, type RowDataPacket } from "mysql2/promise";
import { readMigrationFiles } from "drizzle-orm/migrator";

export const REQUIRED_TABLES = [
  "accounts", "announcement_reads", "announcements", "api_keys", "audit_logs",
  "orders", "plans", "rate_limits", "refunds", "run_events", "runs", "sessions",
  "subscriptions", "system_settings", "tasks", "usage", "users", "workers",
];

export type QueryConnection = Pick<Connection, "query" | "beginTransaction" | "commit" | "rollback">;

async function tableExists(connection: QueryConnection, name: string) {
  const [rows] = await connection.query<RowDataPacket[]>(
    "SELECT 1 FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? LIMIT 1",
    [name],
  );
  return rows.length > 0;
}

async function columnExists(connection: QueryConnection, table: string, column: string) {
  const [rows] = await connection.query<RowDataPacket[]>(
    "SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND COLUMN_NAME = ? LIMIT 1",
    [table, column],
  );
  return rows.length > 0;
}

async function addColumn(connection: QueryConnection, table: string, column: string, definition: string) {
  if (!(await columnExists(connection, table, column))) {
    await connection.query(`ALTER TABLE \`${table}\` ADD COLUMN \`${column}\` ${definition}`);
    console.log(`Added ${table}.${column}`);
  }
}

async function repairKnownLegacySchema(connection: QueryConnection) {
  await addColumn(connection, "accounts", "inspection_status", "varchar(16) NULL");
  await addColumn(connection, "accounts", "inspection_message", "varchar(255) NULL");
  await addColumn(connection, "accounts", "checked_at", "datetime(3) NULL");
  await addColumn(connection, "accounts", "friends", "json NULL");

  await addColumn(connection, "plans", "plugin_permissions", "json NULL");
  await addColumn(connection, "plans", "permissions", "json NULL");

  await addColumn(connection, "orders", "months", "int NULL");
  await connection.query(
    "UPDATE `orders` SET `months` = CASE `cycle` WHEN 'monthly' THEN 1 WHEN 'quarterly' THEN 3 WHEN 'yearly' THEN 12 ELSE NULL END WHERE `months` IS NULL",
  );
  const [unknown] = await connection.query<RowDataPacket[]>(
    "SELECT COUNT(*) AS count FROM `orders` WHERE `months` IS NULL",
  );
  if (Number(unknown[0]?.count ?? 0) > 0) {
    throw new Error("orders contains an unknown cycle; months was not made required");
  }
  await connection.query("ALTER TABLE `orders` MODIFY COLUMN `months` int NOT NULL");
  await addColumn(connection, "orders", "payment_config_encrypted", "text NULL");

  await addColumn(connection, "tasks", "plugin_id", "varchar(80) NOT NULL DEFAULT 'douyin_streak'");
  await addColumn(connection, "tasks", "plugin_config", "json NULL");
  await connection.query("ALTER TABLE `tasks` MODIFY COLUMN `account_id` varchar(36) NULL");
}

async function recordMigrations(connection: QueryConnection) {
  const journal = JSON.parse(readFileSync("./drizzle/meta/_journal.json", "utf8")) as {
    entries: { tag: string; when: number }[];
  };
  const migrations = readMigrationFiles({ migrationsFolder: "./drizzle" });
  if (migrations.length !== journal.entries.length) {
    throw new Error("Migration journal and SQL files are inconsistent");
  }
  await connection.query(`
    CREATE TABLE IF NOT EXISTS \`__drizzle_migrations\` (
      \`id\` serial primary key,
      \`hash\` text not null,
      \`created_at\` bigint
    )
  `);
  for (const [index, migration] of migrations.entries()) {
    await connection.query(
      "INSERT INTO `__drizzle_migrations` (`hash`, `created_at`) VALUES (?, ?)",
      [migration.hash, migration.folderMillis],
    );
    console.log(`Recorded ${journal.entries[index].tag}`);
  }
}

export async function adoptExistingDatabase(connection: QueryConnection) {
  for (const table of REQUIRED_TABLES) {
    if (!(await tableExists(connection, table))) {
      throw new Error(`Missing application table: ${table}. Do not adopt this database; restore or perform a separate data migration.`);
    }
  }
  const [history] = await connection.query<RowDataPacket[]>(
    "SELECT id FROM `__drizzle_migrations` ORDER BY created_at DESC LIMIT 1",
  ).catch(() => [[] as RowDataPacket[]]);
  if (history.length) {
    throw new Error("Drizzle migration history is not empty; use npm run db:migrate instead.");
  }

  console.warn("Repairing known legacy columns and recording the current migration baseline.");
  console.warn("Take a database backup first. MySQL DDL may commit independently.");
  await repairKnownLegacySchema(connection);
  await recordMigrations(connection);
}
