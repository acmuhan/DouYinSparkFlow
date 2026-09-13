import { config } from "dotenv";
import mysql from "mysql2/promise";
import { drizzle } from "drizzle-orm/mysql2";
import { migrate } from "drizzle-orm/mysql2/migrator";
import { readMigrationFiles } from "drizzle-orm/migrator";
import { readFileSync } from "node:fs";
import { readMigrationState, readTableDefinitions } from "./migration-status";

async function main() {
  const args = process.argv.slice(2);
  if (args.length && !(args.length === 1 && args[0] === "--status")) {
    throw new Error("Usage: npm run db:migrate -- [--status]");
  }
  config({ path: ".env.local", quiet: args[0] === "--status" });
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is required");
  const journal = JSON.parse(readFileSync("./drizzle/meta/_journal.json", "utf8")) as {
    entries: { idx: number; tag: string; when: number }[];
  };
  const knownTables = [...new Set(journal.entries.flatMap((entry) => {
    const snapshot = JSON.parse(readFileSync(
      `./drizzle/meta/${String(entry.idx).padStart(4, "0")}_snapshot.json`, "utf8",
    )) as { tables: Record<string, { name: string }> };
    return Object.values(snapshot.tables).map((table) => table.name);
  }))];
  const connection = await mysql.createConnection(process.env.DATABASE_URL);
  try {
    const state = await readMigrationState(connection, knownTables);
    if (args[0] === "--status") {
      const migrations = readMigrationFiles({ migrationsFolder: "./drizzle" });
      console.log(JSON.stringify({
        ...state,
        localMigrations: migrations.map((migration, index) => ({
          tag: journal.entries[index].tag,
          timestamp: migration.folderMillis,
          hash: migration.hash,
          recorded: state.history.some((row) =>
            Number(row.created_at) === migration.folderMillis && row.hash === migration.hash),
        })),
        definitions: await readTableDefinitions(connection, state.applicationTables),
        note: "Read-only report. Existing tables do not prove migrations were applied. No baseline was written.",
      }, null, 2));
      return;
    }
    if (state.needsBaselineReview) {
      throw new Error(
        "Existing application tables have no Drizzle migration history. " +
        "Back up the database, stop API/worker auto-creation, and run " +
        "'npm run db:migrate -- --status' for schema review. " +
        "Do not drop tables or mark migrations applied without verifying their full schema.",
      );
    }
    await migrate(drizzle(connection), { migrationsFolder: "./drizzle" });
    console.log("Database migrations applied.");
  } finally {
    await connection.end();
  }
}

main().catch((error: unknown) => {
  console.error("Database migration failed:", error);
  process.exitCode = 1;
});
