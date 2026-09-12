import { ConsoleShell } from "@/components/console-shell";
import { AuthGate } from "@/components/auth-gate";

export default function Home() {
  return <AuthGate><ConsoleShell /></AuthGate>;
}
