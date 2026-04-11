import { useState, useCallback } from "react";
import { getSessionSnapshot } from "../lib/api";
import { TriageResponse } from "../types/triage";

export function useSessionRestore() {
  const [isRestoring, setIsRestoring] = useState(false);

  const restoreSession = useCallback(async (sessionId: string | null): Promise<TriageResponse | null> => {
    if (!sessionId) return null;
    
    setIsRestoring(true);
    try {
      const response = await getSessionSnapshot(sessionId);
      return response;
    } catch (err) {
      console.error("Failed to restore session", err);
      // Clean up bad session ID
      localStorage.removeItem("triage_session_id");
      return null;
    } finally {
      setIsRestoring(false);
    }
  }, []);

  return { isRestoring, restoreSession };
}
