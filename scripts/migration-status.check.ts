import assert from "node:assert/strict";
import { test } from "node:test";
import type { Connection } from "mysql2/promise";
import { readMigrationState, readTableDefinitions } from "./migration-status";

function fixture(tables: string[], history: object[] = []) {
  const queries: string[] = [];
  const connection = {
    async query(sql: string, parameters?: unknown[]) {
      queries.push(sql);
      assert.match(sql, /^(SELECT|SHOW) /);
      if (sql.startsWith("SELECT TABLE_NAME")) return [tables.map((name) => ({ name }))];
      if (sql.startsWith("SELECT id")) return [history];
      assert.equal(sql, "SHOW CREATE TABLE ??");
      assert.deepEqual(parameters, ["accounts"]);
      return [[{ "Create Table": "CREATE TABLE `accounts` (`id` varchar(36))" }]];
    },
  } as unknown as Pick<Connection, "query">;
  return { connection, queries };
}

test("fresh database can migrate without writing during inspection", async () => {
  const { connection, queries } = fixture([]);
  const state = await readMigrationState(connection, ["accounts"]);
  assert.equal(state.needsBaselineReview, false);
  assert.equal(state.historyTableExists, false);
  assert.equal(queries.length, 1);
});

test("existing tables with missing or empty journal require review", async () => {
  for (const tables of [["accounts"], ["accounts", "__drizzle_migrations"]]) {
    const { connection } = fixture(tables);
    const state = await readMigrationState(connection, ["accounts"]);
    assert.equal(state.needsBaselineReview, true);
    assert.deepEqual(state.applicationTables, ["accounts"]);
  }
});

test("recorded history is preserved, unrelated tables are excluded", async () => {
  const history = [{ id: 1, hash: "example", created_at: "1789211443494" }];
  const { connection } = fixture(["accounts", "unrelated", "__drizzle_migrations"], history);
  const state = await readMigrationState(connection, ["accounts"]);
  assert.equal(state.needsBaselineReview, false);
  assert.deepEqual(state.history, history);
  assert.deepEqual(state.applicationTables, ["accounts"]);
});

test("table definitions use escaped identifiers and read-only queries", async () => {
  const { connection } = fixture(["accounts"]);
  assert.deepEqual(await readTableDefinitions(connection, ["accounts"]), {
    accounts: "CREATE TABLE `accounts` (`id` varchar(36))",
  });
});
