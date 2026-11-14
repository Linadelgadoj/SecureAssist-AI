import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { AuthApiError, endSession, getSession, refreshSession } from "../services/auth";
import type { AuthUser } from "../types/auth";

type AuthState = "loading" | "anonymous" | "authenticated" | "unavailable";
interface AuthContextValue {
  state: AuthState;
  user: AuthUser | null;
  error: string | null;
  accessToken: string | null;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [expiresIn, setExpiresIn] = useState<number | null>(null);
  const refreshPromise = useRef<Promise<void> | null>(null);

  const setSession = useCallback((session: Awaited<ReturnType<typeof getSession>>) => {
    if (!session.authenticated || !session.user || !session.access_token) {
      setState("anonymous"); setUser(null); setAccessToken(null); setExpiresIn(null);
      return;
    }
    setState("authenticated"); setUser(session.user); setAccessToken(session.access_token);
    setExpiresIn(session.expires_in);
  }, []);

  const refresh = useCallback((): Promise<void> => {
    if (!refreshPromise.current) {
      refreshPromise.current = refreshSession()
        .then(setSession)
        .catch((reason: unknown) => {
          setAccessToken(null); setUser(null);
          if (reason instanceof AuthApiError && reason.status === 401) {
            setState("anonymous"); setError("Tu sesión venció. Vuelve a iniciar sesión.");
          } else {
            setState("unavailable"); setError(reason instanceof Error ? reason.message : "No fue posible renovar la sesión.");
          }
        })
        .finally(() => { refreshPromise.current = null; });
    }
    return refreshPromise.current;
  }, [setSession]);

  useEffect(() => {
    let active = true;
    void getSession().then((session) => { if (active) setSession(session); })
      .catch((reason: unknown) => {
        if (!active) return;
        setState("unavailable");
        setError(reason instanceof Error ? reason.message : "No fue posible consultar la sesión.");
      });
    return () => { active = false; };
  }, [setSession]);

  useEffect(() => {
    if (state !== "authenticated" || !expiresIn) return;
    const timer = window.setTimeout(() => { void refresh(); }, Math.max(15, expiresIn - 60) * 1000);
    return () => window.clearTimeout(timer);
  }, [state, expiresIn, refresh]);

  const logout = useCallback(async () => {
    try {
      await endSession();
    } finally {
      setState("anonymous"); setUser(null); setAccessToken(null); setExpiresIn(null);
    }
  }, []);

  const value = useMemo(() => ({ state, user, error, accessToken, refresh, logout }),
    [state, user, error, accessToken, refresh, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth debe usarse dentro de AuthProvider.");
  return value;
}
