import type { Connection, RowDataPacket } from "mysql2/promise";

type QueryConnection = Pick<Connection, "query">;
type HistoryRow = { id: number; hash: string; created_at: string | number };

export async function readMigrationState(connection: QueryConnection, knownTables: string[]) {
  const [rows] = await connection.query<RowDataPacket[]>(
    "SELECT TABLE_NAME AS name FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()",
  );
  const names = new Set(rows.map((row) => String(row.name)));
  const applicationTables = knownTables.filter((name) => names.has(name)).sort();
  let history: HistoryRow[] = [];
  if (names.has("__drizzle_migrations")) {
    const [records] = await connection.query<RowDataPacket[]>(
      "SELECT id, hash, created_at FROM __drizzle_migrations ORDER BY created_at, id",
    );
    history = records.map((row) => ({ id: row.id, hash: row.hash, created_at: row.created_at }));
  }
  return {
    historyTableExists: names.has("__drizzle_migrations"),
    history,
    applicationTables,
    needsBaselineReview: history.length === 0 && applicationTables.length > 0,
  };
}

export async function readTableDefinitions(connection: QueryConnection, tables: string[]) {
  const definitions: Record<string, string> = {};
  for (const table of tables) {
    const [rows] = await connection.query<RowDataPacket[]>("SHOW CREATE TABLE ??", [table]);
    definitions[table] = String(rows[0]["Create Table"] ?? rows[0]["Create View"]);
  }
  return definitions;
}
