import type { ReactNode } from "react";

import { useAuth } from "../context/AuthContext";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const auth = useAuth();
  if (auth.state === "loading") return <p className="auth-message">Comprobando tu sesión…</p>;
  if (auth.state === "authenticated") return <>{children}</>;
  return null;
}
