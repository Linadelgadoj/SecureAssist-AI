import { useCallback, useEffect, useState } from "react";

import { ApiConnectionError, getHealth } from "../services/api";
import type { HealthResponse } from "../types/health";

export type HealthState =
  | { status: "checking"; result: null; error: null }
  | { status: "connected"; result: HealthResponse; error: null }
  | { status: "unavailable"; result: null; error: string };

export function useBackendHealth() {
  const [state, setState] = useState<HealthState>({
    status: "checking",
    result: null,
    error: null,
  });

  const check = useCallback(async () => {
    setState({ status: "checking", result: null, error: null });
    try {
      const result = await getHealth();
      setState({ status: "connected", result, error: null });
    } catch (error) {
      const message =
        error instanceof ApiConnectionError
          ? error.message
          : "Ocurrió un error al consultar el backend.";
      setState({ status: "unavailable", result: null, error: message });
    }
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  return { ...state, retry: check };
}
