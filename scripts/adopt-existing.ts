import { config } from "dotenv";
import mysql from "mysql2/promise";
import { adoptExistingDatabase } from "./database-adoption";

async function main() {
  config({ path: ".env.local" });
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is required");
  const connection = await mysql.createConnection(process.env.DATABASE_URL);
  try {
    await adoptExistingDatabase(connection);
    console.log("Existing database adopted. Future runs should use npm run db:migrate.");
  } finally {
    await connection.end();
  }
}

main().catch((error: unknown) => {
  console.error("Database adoption failed:", error);
  process.exitCode = 1;
});
