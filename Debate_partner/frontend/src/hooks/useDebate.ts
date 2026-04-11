import { useEffect } from "react";
import { useDebateState } from "../context/DebateContext";
import { CreateSessionRequest, TurnRequest } from "../types/api";
import { checkHealth, createSession, getSession, sendTurn, ApiError } from "../services/api";

export function useDebate() {
  const { state, dispatch } = useDebateState();

  useEffect(() => {
    // Initial health check
    checkHealth()
      .then(() => dispatch({ type: "SET_HEALTH", payload: true }))
      .catch(() => dispatch({ type: "SET_HEALTH", payload: false }));

    // Try to restore session
    const savedId = localStorage.getItem("debate_session_id");
    if (savedId) {
      getSession(savedId)
        .then((res) => {
          dispatch({ type: "RESTORE_SESSION", payload: res.session });
        })
        .catch((e) => {
          if (e instanceof ApiError && e.code === "SESSION_NOT_FOUND") {
            localStorage.removeItem("debate_session_id");
          }
        });
    }
  }, [dispatch]);

  const initSession = async () => {
    dispatch({ type: "SET_LOADING", payload: true });
    try {
      const payload: CreateSessionRequest = {
        case_background: state.config.caseBackground,
        scenario_hint: state.config.scenarioHint,
        max_rounds: state.config.maxRounds,
      };
      const res = await createSession(payload);
      dispatch({ 
        type: "INIT_SESSION", 
        payload: { sessionId: res.session.session_id, sessionData: res.session } 
      });
    } catch (err: any) {
      if (err instanceof ApiError) {
        dispatch({ type: "SET_ERROR", payload: { error: { code: err.code, message: err.message }, trace_id: err.traceId }});
      } else {
        dispatch({ type: "SET_ERROR", payload: { error: { code: "INTERNAL_ERROR", message: err.message }, trace_id: "" }});
      }
    } finally {
      dispatch({ type: "SET_LOADING", payload: false });
    }
  };

  const handleTurn = async (action: "send" | "end", text?: string) => {
    if (!state.sessionId) return;
    
    if (action === "send" && text) {
      dispatch({ type: "ADD_USER_MSG", payload: { text } });
    }
    
    dispatch({ type: "SET_LOADING", payload: true });
    try {
      const payload: TurnRequest = { action, user_text: text || "" };
      const res = await sendTurn(state.sessionId, payload);
      dispatch({ type: "RESOLVE_TURN", payload: res.session });
    } catch (err: any) {
      if (err instanceof ApiError) {
        dispatch({ type: "FAIL_TURN", payload: { error: { code: err.code, message: err.message }, trace_id: err.traceId }});
      } else {
        dispatch({ type: "FAIL_TURN", payload: { error: { code: "INTERNAL_ERROR", message: String(err) }, trace_id: "" }});
      }
    } finally {
      dispatch({ type: "SET_LOADING", payload: false });
    }
  };

  const setDraft = (text: string) => {
    dispatch({ type: "SET_DRAFT", payload: text });
  };

  const toggleDetail = (index: number) => {
    dispatch({ type: "TOGGLE_DETAIL", payload: index });
  };

  return {
    state,
    initSession,
    handleTurn,
    setDraft,
    toggleDetail
  };
}
