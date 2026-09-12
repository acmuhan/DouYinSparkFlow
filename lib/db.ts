import { drizzle, type MySql2Database } from "drizzle-orm/mysql2";
import mysql from "mysql2/promise";
import * as schema from "./schema";

let database: MySql2Database<typeof schema> | undefined;
export function getDb() {
  if (!database) {
    if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is required");
    database = drizzle(mysql.createPool({ uri: process.env.DATABASE_URL, connectionLimit: 5, timezone: "Z" }) as never, { schema, mode: "default" });
  }
  return database;
}
